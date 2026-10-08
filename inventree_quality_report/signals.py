"""Capture immutable tested quantity in core TestResult metadata."""

from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation

from django.db.models.signals import post_save
from django.dispatch import receiver
from stock.models import StockItemTestResult

METADATA_KEY = "pervices_quality_report"


def _iso(value):
    if value is None:
        return ""
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _event_fingerprint(result: StockItemTestResult) -> str:
    """Fingerprint fields copied when InvenTree duplicates test history."""
    fields = [
        str(getattr(result, "template_id", "") or ""),
        str(getattr(result, "key", "") or ""),
        str(bool(getattr(result, "result", False))),
        _iso(getattr(result, "date", None)),
        _iso(getattr(result, "started_datetime", None)),
        _iso(getattr(result, "finished_datetime", None)),
        str(getattr(result, "value", "") or ""),
        str(getattr(result, "notes", "") or ""),
    ]
    raw = "\x1f".join(fields).encode("utf-8", errors="replace")
    return "evt-" + hashlib.sha256(raw).hexdigest()[:48]


def _capture_from_metadata(result):
    metadata = getattr(result, "metadata", None) or {}
    value = metadata.get(METADATA_KEY, {})
    return value if isinstance(value, dict) else {}


def _matching_original_capture(result, event_key):
    """Find an earlier row for the same physical event, if one exists.

    This handles stock splits where InvenTree creates a new TestResult row for
    historical test data. The original row already has immutable metadata, so
    the child inherits the original tested quantity rather than its new split
    quantity.
    """
    qs = StockItemTestResult.objects.exclude(pk=result.pk)

    template_id = getattr(result, "template_id", None)
    if template_id is not None:
        qs = qs.filter(template_id=template_id)

    for field in (
        "result",
        "date",
        "started_datetime",
        "finished_datetime",
        "value",
        "notes",
    ):
        if hasattr(result, field):
            qs = qs.filter(**{field: getattr(result, field)})

    for candidate in qs.order_by("pk"):
        capture = _capture_from_metadata(candidate)
        if capture.get("event_key") == event_key and capture.get("tested_quantity") not in (None, ""):
            return capture

    return None


@receiver(
    post_save,
    sender=StockItemTestResult,
    dispatch_uid="quality_report_capture_test_quantity_metadata_v021",
)
def capture_tested_quantity(sender, instance, created, **kwargs):
    """Persist immutable tested quantity using existing core metadata.

    No plugin-owned database table or migration is required. Reporting
    metadata must never block normal InvenTree test entry, so failures here are
    deliberately non-fatal.
    """
    if not created:
        return

    try:
        existing_metadata = dict(getattr(instance, "metadata", None) or {})
        existing_capture = existing_metadata.get(METADATA_KEY)
        if isinstance(existing_capture, dict) and existing_capture.get("tested_quantity") not in (None, ""):
            return

        event_key = _event_fingerprint(instance)
        inherited = _matching_original_capture(instance, event_key)

        if inherited is not None:
            tested_quantity = inherited["tested_quantity"]
        else:
            stock_item = instance.stock_item
            tested_quantity = Decimal(str(stock_item.quantity or 0))
            if tested_quantity < 0:
                return
            tested_quantity = format(tested_quantity, "f")

        existing_metadata[METADATA_KEY] = {
            "schema": 1,
            "event_key": event_key,
            "tested_quantity": str(tested_quantity),
        }

        # Use QuerySet.update to avoid recursively emitting post_save and to
        # modify only the existing core metadata field.
        StockItemTestResult.objects.filter(pk=instance.pk).update(
            metadata=existing_metadata
        )
        instance.metadata = existing_metadata
    except (InvalidOperation, TypeError, ValueError, AttributeError):
        return
    except Exception:
        return

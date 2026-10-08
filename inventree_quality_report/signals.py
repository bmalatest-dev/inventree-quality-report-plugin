"""Synchronous capture of immutable tested quantity."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from django.db.models.signals import post_save
from django.dispatch import receiver
from stock.models import StockItemTestResult

from .models import TestTimingCapture


def _iso(value):
    if value is None:
        return ""
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _event_fingerprint(result: StockItemTestResult) -> str:
    """Fingerprint fields copied when InvenTree duplicates test history on split.

    The stock-item id and test-result id are intentionally excluded. A copied
    historical result therefore maps to the original physical work event.
    """
    fields = [
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


@receiver(post_save, sender=StockItemTestResult, dispatch_uid="quality_report_capture_test_quantity")
def capture_tested_quantity(sender, instance, created, **kwargs):
    """Capture quantity immediately when a test-result row is created.

    When InvenTree copies test history during a stock split, the copied row has
    the same event fingerprint. It is linked to the same event and does not add
    another production-work observation.
    """
    if not created:
        return

    try:
        stock_item = instance.stock_item
        quantity = Decimal(str(stock_item.quantity or 0))
        event_key = _event_fingerprint(instance)

        existing = (
            TestTimingCapture.objects
            .filter(event_key=event_key)
            .order_by("test_result_id")
            .first()
        )

        if existing is not None:
            quantity = existing.tested_quantity

        TestTimingCapture.objects.get_or_create(
            test_result_id=instance.pk,
            defaults={
                "event_key": event_key,
                "tested_quantity": quantity,
            },
        )
    except Exception:
        # Never allow reporting metadata to block normal InvenTree test entry.
        return

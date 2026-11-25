"""Compatibility adapter for legacy stock tracking and centralized audit logs."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class TrackingRecord:
    pk: int
    item_id: int
    date: datetime
    deltas: dict[str, Any]


def merge_audit_deltas(changes, additional_data):
    """Retain both old/new field values and named event deltas."""
    extra = additional_data.get('deltas') if isinstance(additional_data, dict) else None
    merged = dict(extra) if isinstance(extra, dict) else {}
    if isinstance(changes, dict):
        merged.update(changes)
    return merged


def load_tracking(part, stock_ids):
    """Return tracking records for the selected part and its current stock."""
    if not stock_ids:
        return []
    from stock import models as stock_models

    legacy = getattr(stock_models, 'StockItemTracking', None)
    if legacy is not None:
        rows = legacy.objects.filter(part=part, item_id__in=stock_ids).only(
            'pk', 'item_id', 'deltas', 'date'
        ).order_by('item_id', 'date', 'pk')
        return [TrackingRecord(r.pk, r.item_id, r.date, r.deltas) for r in rows]

    from audit.models import AuditLogEntry
    from django.contrib.contenttypes.models import ContentType

    rows = AuditLogEntry.objects.filter(
        content_type=ContentType.objects.get_for_model(stock_models.StockItem),
        parent_content_type=ContentType.objects.get_for_model(part),
        parent_object_pk=str(part.pk),
        object_pk__in=[str(pk) for pk in stock_ids],
    ).values_list('pk', 'object_pk', 'timestamp', 'changes', 'additional_data').order_by(
        'object_pk', 'timestamp', 'pk'
    )
    return [TrackingRecord(pk, int(item), date, merge_audit_deltas(changes, extra))
            for pk, item, date, changes, extra in rows]

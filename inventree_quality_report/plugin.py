"""Part Quality Report plugin for InvenTree."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from django.core.exceptions import ValidationError

from InvenTree.helpers import generateTestKey
from part.models import Part
from plugin import InvenTreePlugin
from plugin.mixins import ActionMixin, UserInterfaceMixin
from stock.models import StockItem, StockItemTestResult, StockItemTracking
from stock.status_codes import StockStatus


class QualityReportPlugin(ActionMixin, UserInterfaceMixin, InvenTreePlugin):
    """Generate an on-demand quality report for a single Part."""

    NAME = "Part Quality Report"
    SLUG = "part-quality-report"
    TITLE = "Part Quality Report"
    DESCRIPTION = (
        "On-demand Part quality report for current stock status, first-pass yield, "
        "test duration, and historical rework rate."
    )
    VERSION = "0.1.0"
    AUTHOR = "Per Vices Corporation"
    LICENSE = "MIT"

    ACTION_NAME = "part_quality_report"

    SNAPSHOT_ORDER = (
        ("pass_vi", "Pass VI"),
        ("pass_bu", "Pass BU"),
        ("pass_sw", "Pass SW"),
        ("failed_vi", "Failed VI"),
        ("failed_bu", "Failed BU"),
        ("failed_sw", "Failed SW"),
        ("rework", "Rework"),
        ("other", "Other"),
    )

    STATUS_ALIASES = {
        "passvi": "pass_vi",
        "passedvi": "pass_vi",
        "passbu": "pass_bu",
        "passedbu": "pass_bu",
        "passsw": "pass_sw",
        "passsoftware": "pass_sw",
        "failedvi": "failed_vi",
        "failvi": "failed_vi",
        "failedbu": "failed_bu",
        "failbu": "failed_bu",
        "failedsw": "failed_sw",
        "failsw": "failed_sw",
        "failedsoftware": "failed_sw",
        "rework": "rework",
    }

    REWORK_TEST_KEYS = {generateTestKey("Rework")}

    def get_ui_panels(self, request, context, **kwargs):
        context = context or {}
        if context.get("target_model") != "part":
            return []
        try:
            part = Part.objects.get(pk=context.get("target_id"))
        except (Part.DoesNotExist, TypeError, ValueError):
            return []
        return [{
            "key": "part-quality-report-panel",
            "title": "Quality Report",
            "description": "Current stock status, FPY, test timing, and rework.",
            "icon": "ti:chart-bar:outline",
            "source": self.plugin_static_file("quality_report.js:renderQualityReportPanel"),
            "context": {
                "part_id": part.pk,
                "part_name": part.name,
                "part_ipn": part.IPN or "",
                "plugin_version": self.VERSION,
            },
        }]

    def perform_action(self, user=None, data=None):
        data = data or {}
        self._last_result = self._build_report(self._parse_part_pk(data.get("part")))

    def get_info(self, user=None, data=None):
        return {
            "action": self.ACTION_NAME,
            "description": self.DESCRIPTION,
            "version": self.VERSION,
            "required_data": {"part": "Numeric Part primary key"},
        }

    def get_result(self, user=None, data=None):
        return getattr(self, "_last_result", {"status": "no_result"})

    @staticmethod
    def _parse_part_pk(value: Any) -> int:
        if value in (None, ""):
            raise ValidationError({"part": "This field is required."})
        try:
            pk = int(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError({"part": "Must be a numeric Part primary key."}) from exc
        if pk <= 0:
            raise ValidationError({"part": "Must be a positive Part primary key."})
        return pk

    def _build_report(self, part_pk: int) -> dict[str, Any]:
        try:
            part = Part.objects.get(pk=part_pk)
        except Part.DoesNotExist as exc:
            raise ValidationError({"part": f"Part {part_pk} does not exist."}) from exc

        stock_items = list(
            StockItem.objects.filter(part=part)
            .only("pk", "part_id", "status", "serial", "quantity")
            .order_by("pk")
        )
        stock_ids = [item.pk for item in stock_items]

        results = list(
            StockItemTestResult.objects.filter(stock_item_id__in=stock_ids)
            .select_related("template", "stock_item")
        )

        tracking = list(
            StockItemTracking.objects.filter(part=part, item_id__in=stock_ids)
            .only("pk", "item_id", "deltas", "date")
            .order_by("item_id", "date", "pk")
        )

        return {
            "part": {"pk": part.pk, "name": part.name, "ipn": part.IPN or ""},
            "stock_item_count": len(stock_items),
            "snapshot": self._current_snapshot(stock_items),
            "fpy": self._first_pass_yield(part, results),
            "timing": self._test_timing(part, results),
            "rework": self._rework(stock_items, results, tracking),
        }

    @staticmethod
    def _normalize(value: Any) -> str:
        if value is None:
            return ""
        return "".join(ch for ch in str(value).lower() if ch.isalnum())

    @classmethod
    def _status_bucket(cls, label: str) -> str:
        return cls.STATUS_ALIASES.get(cls._normalize(label), "other")

    @staticmethod
    def _status_label(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str) and not value.strip().lstrip("-").isdigit():
            return value
        try:
            numeric = int(value)
        except (TypeError, ValueError):
            return str(value)
        try:
            choices = dict(StockItem._meta.get_field("status").flatchoices)
            label = choices.get(numeric)
            if label:
                return str(label)
        except Exception:
            pass
        try:
            return str(StockStatus.text(numeric))
        except Exception:
            return str(value)

    @classmethod
    def _current_snapshot(cls, stock_items: list[StockItem]) -> dict[str, Any]:
        counts = {key: 0 for key, _ in cls.SNAPSHOT_ORDER}
        details = []
        for item in stock_items:
            try:
                label = str(item.get_status_display())
            except Exception:
                label = cls._status_label(item.status)
            bucket = cls._status_bucket(label)
            counts[bucket] += 1
            details.append({
                "stock_item": item.pk,
                "serial": item.serial or "",
                "status": label,
                "bucket": bucket,
            })
        rows = [{"key": key, "status": label, "count": counts[key]} for key, label in cls.SNAPSHOT_ORDER]
        return {"rows": rows, "total": len(stock_items), "details": details}

    @classmethod
    def _test_catalog(cls, part: Part, results: list[StockItemTestResult]):
        catalog = {}
        try:
            templates = part.getTestTemplates()
        except Exception:
            templates = []
        for template in templates:
            catalog[template.key] = {
                "key": template.key,
                "name": template.test_name,
                "enabled": bool(template.enabled),
            }
        for result in results:
            if result.key not in catalog:
                catalog[result.key] = {
                    "key": result.key,
                    "name": result.test_name,
                    "enabled": bool(getattr(result.template, "enabled", False)),
                }
        return catalog

    @staticmethod
    def _attempt_sort_key(result: StockItemTestResult):
        stamp = result.started_datetime or result.finished_datetime or result.date
        if stamp is None:
            stamp = datetime.min.replace(tzinfo=timezone.utc)
        elif stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return stamp, result.pk

    @classmethod
    def _first_pass_yield(cls, part: Part, results: list[StockItemTestResult]):
        catalog = cls._test_catalog(part, results)
        grouped = defaultdict(lambda: defaultdict(list))
        for result in results:
            grouped[result.key][result.stock_item_id].append(result)
        rows = []
        for key, meta in catalog.items():
            item_attempts = grouped.get(key, {})
            tested = len(item_attempts)
            first_pass = 0
            failed_items = []
            for stock_id, attempts in item_attempts.items():
                first = sorted(attempts, key=cls._attempt_sort_key)[0]
                if bool(first.result):
                    first_pass += 1
                else:
                    failed_items.append(stock_id)
            rows.append({
                "key": key,
                "test": meta["name"],
                "enabled": meta["enabled"],
                "first_pass": first_pass,
                "tested": tested,
                "percentage": (first_pass / tested * 100.0) if tested else None,
                "failed_stock_items": sorted(failed_items),
            })
        rows.sort(key=lambda r: (r["test"].lower(), r["key"]))
        return rows

    @classmethod
    def _test_timing(cls, part: Part, results: list[StockItemTestResult]):
        catalog = cls._test_catalog(part, results)
        grouped = defaultdict(list)
        for result in results:
            grouped[result.key].append(result)
        rows = []
        for key, meta in catalog.items():
            attempts = grouped.get(key, [])
            durations = []
            excluded = 0
            for result in attempts:
                start = result.started_datetime
                finish = result.finished_datetime
                if not start or not finish:
                    excluded += 1
                    continue
                seconds = (finish - start).total_seconds()
                if seconds <= 0:
                    excluded += 1
                    continue
                durations.append(seconds)
            rows.append({
                "key": key,
                "test": meta["name"],
                "enabled": meta["enabled"],
                "attempts": len(attempts),
                "timed_results": len(durations),
                "excluded": excluded,
                "average_seconds": (sum(durations) / len(durations)) if durations else None,
                "min_seconds": min(durations) if durations else None,
                "max_seconds": max(durations) if durations else None,
            })
        rows.sort(key=lambda r: (r["test"].lower(), r["key"]))
        return rows

    @classmethod
    def _tracking_indicates_rework(cls, entry: StockItemTracking) -> bool:
        deltas = entry.deltas or {}
        if not isinstance(deltas, dict):
            return False
        values = []
        for field in ("status", "new_status", "stock_status"):
            if field in deltas:
                values.append(deltas.get(field))
        for value in values:
            if cls._normalize(cls._status_label(value)) == "rework":
                return True
            if cls._normalize(value) == "rework":
                return True
        return False

    @classmethod
    def _rework(cls, stock_items, results, tracking):
        all_ids = {item.pk for item in stock_items}
        tracking_ids = {
            entry.item_id for entry in tracking
            if entry.item_id in all_ids and cls._tracking_indicates_rework(entry)
        }
        test_ids = {
            result.stock_item_id for result in results
            if result.key in cls.REWORK_TEST_KEYS
        }
        both = tracking_ids & test_ids
        tracking_only = tracking_ids - test_ids
        test_only = test_ids - tracking_ids
        unique = tracking_ids | test_ids
        total = len(all_ids)
        return {
            "stock_items_evaluated": total,
            "unique_reworked": len(unique),
            "rate_percentage": (len(unique) / total * 100.0) if total else None,
            "tracking_only": len(tracking_only),
            "test_only": len(test_only),
            "both": len(both),
            "tracking_detected_total": len(tracking_ids),
            "test_detected_total": len(test_ids),
            "stock_items": sorted(unique),
            "tracking_only_items": sorted(tracking_only),
            "test_only_items": sorted(test_only),
            "both_items": sorted(both),
        }

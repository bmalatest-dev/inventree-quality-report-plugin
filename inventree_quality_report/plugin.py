"""Part Quality Report plugin for InvenTree."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
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
    VERSION = "0.1.3"
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
            "source": self.plugin_static_file(
                "quality_report_v013.js:renderQualityReportPanel"
            ),
            "context": {
                "part_id": part.pk,
                "part_name": part.name,
                "part_ipn": part.IPN or "",
                "plugin_version": self.VERSION,
            },
        }]

    def perform_action(self, user=None, data=None):
        data = data or {}
        self._last_result = self._build_report(
            self._parse_part_pk(data.get("part"))
        )

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
            raise ValidationError(
                {"part": "Must be a numeric Part primary key."}
            ) from exc

        if pk <= 0:
            raise ValidationError(
                {"part": "Must be a positive Part primary key."}
            )
        return pk

    @staticmethod
    def _normalize(value: Any) -> str:
        if value is None:
            return ""
        return "".join(
            ch for ch in str(value).lower()
            if ch.isalnum()
        )

    @classmethod
    def _status_bucket(cls, *values: Any) -> str:
        for value in values:
            bucket = cls.STATUS_ALIASES.get(cls._normalize(value))
            if bucket:
                return bucket
        return "other"

    @staticmethod
    def _custom_status_maps() -> dict[int, dict[str, Any]]:
        """Resolve configured custom Stock Statuses dynamically."""
        by_key: dict[int, dict[str, Any]] = {}

        try:
            for status in StockStatus.custom_queryset():
                by_key[int(status.key)] = {
                    "key": int(status.key),
                    "name": str(status.name or ""),
                    "label": str(status.label or status.name or ""),
                    "logical_key": int(status.logical_key),
                }
        except Exception:
            pass

        return by_key

    @staticmethod
    def _logical_status_label(value: Any) -> str:
        try:
            return str(StockStatus.text(int(value)))
        except Exception:
            return str(value or "")

    @classmethod
    def _resolved_current_status(
        cls,
        item: StockItem,
        custom_map: dict[int, dict[str, Any]],
    ) -> dict[str, Any]:
        custom_key = getattr(item, "status_custom_key", None)

        if custom_key is not None:
            try:
                custom = custom_map.get(int(custom_key))
            except (TypeError, ValueError):
                custom = None

            if custom:
                return {
                    "custom": True,
                    "key": custom["key"],
                    "name": custom["name"],
                    "label": custom["label"],
                    "logical_key": custom["logical_key"],
                    "bucket": cls._status_bucket(
                        custom["name"],
                        custom["label"],
                    ),
                }

        label = cls._logical_status_label(item.status)

        return {
            "custom": False,
            "key": int(item.status),
            "name": label,
            "label": label,
            "logical_key": int(item.status),
            "bucket": cls._status_bucket(label),
        }

    def _build_report(self, part_pk: int) -> dict[str, Any]:
        try:
            part = Part.objects.get(pk=part_pk)
        except Part.DoesNotExist as exc:
            raise ValidationError(
                {"part": f"Part {part_pk} does not exist."}
            ) from exc

        stock_items = list(
            StockItem.objects.filter(part=part)
            .only(
                "pk",
                "part_id",
                "status",
                "status_custom_key",
                "serial",
                "quantity",
            )
            .order_by("pk")
        )

        stock_ids = [item.pk for item in stock_items]

        results = list(
            StockItemTestResult.objects
            .filter(stock_item_id__in=stock_ids)
            .select_related("template", "stock_item")
        )

        tracking = list(
            StockItemTracking.objects
            .filter(part=part, item_id__in=stock_ids)
            .only("pk", "item_id", "deltas", "date")
            .order_by("item_id", "date", "pk")
        )

        custom_map = self._custom_status_maps()

        return {
            "part": {
                "pk": part.pk,
                "name": part.name,
                "ipn": part.IPN or "",
            },
            "stock_item_count": len(stock_items),
            "snapshot": self._current_snapshot(
                stock_items,
                custom_map,
            ),
            "fpy": self._first_pass_yield(part, results),
            "timing": self._test_timing(part, results),
            "rework": self._rework(
                stock_items,
                results,
                tracking,
                custom_map,
            ),
        }

    @classmethod
    def _current_snapshot(
        cls,
        stock_items: list[StockItem],
        custom_map: dict[int, dict[str, Any]],
    ) -> dict[str, Any]:
        counts = {
            key: 0
            for key, _ in cls.SNAPSHOT_ORDER
        }

        details = []

        for item in stock_items:
            resolved = cls._resolved_current_status(
                item,
                custom_map,
            )
            counts[resolved["bucket"]] += 1

            details.append({
                "stock_item": item.pk,
                "serial": item.serial or "",
                "status": resolved["label"],
                "status_name": resolved["name"],
                "status_custom_key": getattr(
                    item,
                    "status_custom_key",
                    None,
                ),
                "logical_status": item.status,
                "bucket": resolved["bucket"],
            })

        rows = [
            {
                "key": key,
                "status": label,
                "count": counts[key],
            }
            for key, label in cls.SNAPSHOT_ORDER
        ]

        return {
            "rows": rows,
            "total": len(stock_items),
            "details": details,
        }

    @classmethod
    def _test_catalog(
        cls,
        part: Part,
        results: list[StockItemTestResult],
    ):
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
                    "enabled": bool(
                        getattr(
                            result.template,
                            "enabled",
                            False,
                        )
                    ),
                }

        return catalog

    @staticmethod
    def _attempt_sort_key(
        result: StockItemTestResult,
    ):
        stamp = (
            result.started_datetime
            or result.finished_datetime
            or result.date
        )

        if stamp is None:
            stamp = datetime.min.replace(
                tzinfo=timezone.utc
            )
        elif stamp.tzinfo is None:
            stamp = stamp.replace(
                tzinfo=timezone.utc
            )

        return stamp, result.pk

    @classmethod
    def _first_pass_yield(
        cls,
        part: Part,
        results: list[StockItemTestResult],
    ):
        catalog = cls._test_catalog(
            part,
            results,
        )

        grouped = defaultdict(
            lambda: defaultdict(list)
        )

        for result in results:
            grouped[result.key][
                result.stock_item_id
            ].append(result)

        rows = []

        for key, meta in catalog.items():
            item_attempts = grouped.get(
                key,
                {},
            )
            tested = len(item_attempts)
            first_pass = 0
            failed_items = []

            for stock_id, attempts in item_attempts.items():
                first = sorted(
                    attempts,
                    key=cls._attempt_sort_key,
                )[0]

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
                "percentage": (
                    first_pass / tested * 100.0
                    if tested
                    else None
                ),
                "failed_stock_items": sorted(
                    failed_items
                ),
            })

        rows.sort(
            key=lambda r: (
                r["test"].lower(),
                r["key"],
            )
        )
        return rows

    @staticmethod
    def _iso(value):
        if value is None:
            return None
        try:
            return value.isoformat()
        except Exception:
            return str(value)

    @classmethod
    def _timing_result_record(
        cls,
        result: StockItemTestResult,
        seconds: float,
    ) -> dict[str, Any]:
        stock_item = getattr(
            result,
            "stock_item",
            None,
        )

        return {
            "result_id": result.pk,
            "stock_item": result.stock_item_id,
            "serial": (
                getattr(
                    stock_item,
                    "serial",
                    "",
                )
                or ""
            ),
            "test": result.test_name,
            "result": bool(result.result),
            "date": cls._iso(
                getattr(result, "date", None)
            ),
            "started_datetime": cls._iso(
                result.started_datetime
            ),
            "finished_datetime": cls._iso(
                result.finished_datetime
            ),
            "duration_seconds": seconds,
        }

    @classmethod
    def _test_timing(
        cls,
        part: Part,
        results: list[StockItemTestResult],
    ):
        """Return test duration statistics.

        Missing, zero and negative durations are excluded. Median is used
        instead of arithmetic mean so accidental long-running timestamps do
        not distort the representative test duration. Min / max retain links
        to every tied underlying test result.
        """
        catalog = cls._test_catalog(
            part,
            results,
        )

        grouped = defaultdict(list)

        for result in results:
            grouped[result.key].append(
                result
            )

        rows = []

        for key, meta in catalog.items():
            attempts = grouped.get(
                key,
                [],
            )

            observations = []
            excluded = 0

            for result in attempts:
                start = result.started_datetime
                finish = result.finished_datetime

                if not start or not finish:
                    excluded += 1
                    continue

                seconds = (
                    finish - start
                ).total_seconds()

                if seconds <= 0:
                    excluded += 1
                    continue

                observations.append(
                    (
                        seconds,
                        cls._timing_result_record(
                            result,
                            seconds,
                        ),
                    )
                )

            durations = [
                seconds
                for seconds, _ in observations
            ]

            if durations:
                minimum = min(durations)
                maximum = max(durations)
                min_results = [
                    record
                    for seconds, record in observations
                    if seconds == minimum
                ]
                max_results = [
                    record
                    for seconds, record in observations
                    if seconds == maximum
                ]
                median_seconds = float(
                    median(durations)
                )
            else:
                minimum = None
                maximum = None
                min_results = []
                max_results = []
                median_seconds = None

            rows.append({
                "key": key,
                "test": meta["name"],
                "enabled": meta["enabled"],
                "attempts": len(attempts),
                "timed_results": len(durations),
                "excluded": excluded,
                "median_seconds": median_seconds,
                "min_seconds": minimum,
                "max_seconds": maximum,
                "min_results": min_results,
                "max_results": max_results,
            })

        rows.sort(
            key=lambda r: (
                r["test"].lower(),
                r["key"],
            )
        )
        return rows

    @classmethod
    def _custom_status_is_rework(
        cls,
        value: Any,
        custom_map: dict[int, dict[str, Any]],
    ) -> bool:
        if value is None:
            return False

        if cls._normalize(value) == "rework":
            return True

        try:
            key = int(value)
        except (TypeError, ValueError):
            return False

        custom = custom_map.get(key)

        if not custom:
            return False

        return (
            cls._normalize(
                custom["name"]
            )
            == "rework"
            or cls._normalize(
                custom["label"]
            )
            == "rework"
        )

    @classmethod
    def _tracking_indicates_rework(
        cls,
        entry: StockItemTracking,
        custom_map: dict[int, dict[str, Any]],
    ) -> bool:
        deltas = entry.deltas or {}

        if not isinstance(deltas, dict):
            return False

        candidate_fields = (
            "status_custom_key",
            "custom_status",
            "status_custom",
            "new_status_custom_key",
            "status",
            "new_status",
            "stock_status",
        )

        candidates = [
            deltas[field]
            for field in candidate_fields
            if field in deltas
        ]

        def flatten(value):
            if isinstance(value, dict):
                ordered = []

                for key in (
                    "new",
                    "to",
                    "value",
                    "after",
                ):
                    if key in value:
                        ordered.append(
                            value[key]
                        )

                ordered.extend(
                    v
                    for k, v in value.items()
                    if k not in {
                        "new",
                        "to",
                        "value",
                        "after",
                    }
                )
                return ordered

            if isinstance(
                value,
                (list, tuple, set),
            ):
                return list(value)

            return [value]

        for candidate in candidates:
            for value in flatten(candidate):
                if cls._custom_status_is_rework(
                    value,
                    custom_map,
                ):
                    return True

        return False

    @classmethod
    def _rework(
        cls,
        stock_items: list[StockItem],
        results: list[StockItemTestResult],
        tracking: list[StockItemTracking],
        custom_map: dict[int, dict[str, Any]],
    ) -> dict[str, Any]:
        all_ids = {
            item.pk
            for item in stock_items
        }

        current_status_ids = set()

        for item in stock_items:
            resolved = cls._resolved_current_status(
                item,
                custom_map,
            )
            if resolved["bucket"] == "rework":
                current_status_ids.add(
                    item.pk
                )

        tracking_history_ids = {
            entry.item_id
            for entry in tracking
            if (
                entry.item_id in all_ids
                and cls._tracking_indicates_rework(
                    entry,
                    custom_map,
                )
            )
        }

        status_ids = (
            current_status_ids
            | tracking_history_ids
        )

        test_ids = {
            result.stock_item_id
            for result in results
            if result.key in cls.REWORK_TEST_KEYS
        }

        both = status_ids & test_ids
        status_only = status_ids - test_ids
        test_only = test_ids - status_ids
        unique = status_ids | test_ids
        total = len(all_ids)

        return {
            "stock_items_evaluated": total,
            "unique_reworked": len(unique),
            "rate_percentage": (
                len(unique) / total * 100.0
                if total
                else None
            ),
            "status_only": len(status_only),
            "test_only": len(test_only),
            "both": len(both),
            "current_status_detected": len(
                current_status_ids
            ),
            "tracking_history_detected": len(
                tracking_history_ids
            ),
            "status_detected_total": len(
                status_ids
            ),
            "test_detected_total": len(
                test_ids
            ),
            "stock_items": sorted(unique),
            "status_only_items": sorted(
                status_only
            ),
            "test_only_items": sorted(
                test_only
            ),
            "both_items": sorted(both),
        }

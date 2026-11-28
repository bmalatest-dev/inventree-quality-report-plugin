"""Global test throughput report, available only to InvenTree superusers."""

import csv
import math
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from stock.models import StockItemTestResult

TORONTO = ZoneInfo("America/Toronto")
METRICS = (
    "units", "runs", "hours", "timed_units", "units_per_hour",
    "first_attempt_units", "retest_units", "untimed_runs", "legacy_runs",
)


def can_view_throughput(user):
    return bool(user.is_authenticated and user.is_active and user.is_superuser)


class ThroughputPermission(BasePermission):
    message = "InvenTree superuser access is required."

    def has_permission(self, request, view):
        return can_view_throughput(request.user)


@never_cache
@api_view(["GET"])
@permission_classes([ThroughputPermission])
def throughput_view(request, *, legacy_event_key, download=False):
    today = datetime.now(TORONTO).date()
    try:
        start = date.fromisoformat(request.GET.get("start") or str(today - timedelta(days=29)))
        end = date.fromisoformat(request.GET.get("end") or str(today))
        if end < start:
            raise ValueError
        end_exclusive = datetime.combine(end + timedelta(days=1), time.min, TORONTO)
        user = request.GET.get("user", "")
        if user and not 0 < int(user) <= 2**63 - 1:
            raise ValueError
        outcome = request.GET.get("outcome", "")
        if outcome not in ("", "pass", "fail"):
            raise ValueError
    except (ValueError, OverflowError):
        return JsonResponse({"error": "Enter a valid date range, user and result."}, status=400)

    history = StockItemTestResult.objects.annotate(
        work_time=Coalesce("started_datetime", "finished_datetime", "date")
    )
    matches = history.filter(
        work_time__gte=datetime.combine(start, time.min, TORONTO),
        work_time__lt=end_exclusive,
    )
    test = request.GET.get("test", "")
    part = request.GET.get("part", "").strip()
    if user:
        matches = matches.filter(user_id=int(user))
    if part:
        part_filter = (
            Q(stock_item__part__IPN__iexact=part)
            | Q(stock_item__part__name__icontains=part)
        )
        if part.isascii() and part.isdecimal() and len(part) <= 10:
            part_filter |= Q(stock_item__part_id=int(part))
        matches = matches.filter(part_filter)

    # Use the full history for attempt classification, including other users,
    # earlier dates and failed attempts hidden by the current filters.
    earlier_attempt = history.filter(
        stock_item_id=OuterRef("stock_item_id"), template__key=OuterRef("template__key"),
    ).filter(
        Q(work_time__lt=OuterRef("work_time"))
        | Q(work_time=OuterRef("work_time"), pk__lt=OuterRef("pk"))
    )
    rows = matches
    if test:
        rows = rows.filter(template__key=test)
    if outcome:
        rows = rows.filter(result=outcome == "pass")
    rows = rows.annotate(retest=Exists(earlier_attempt)).select_related(
        "stock_item__part", "template", "user"
    ).order_by("work_time", "pk")

    runs = list(physical_runs(rows.iterator(chunk_size=2000), legacy_event_key))
    summary = summarize(runs, single_test=bool(test))
    if download:
        return export_csv(summary, runs)

    tests = {}
    for key, name in matches.order_by().values_list(
        "template__key", "template__test_name"
    ).distinct():
        tests[key] = min(tests.get(key, name), name)

    return JsonResponse({
        "start": str(start),
        "end": str(end),
        "users": list(get_user_model().objects.order_by("username").values_list("pk", "username")),
        "tests": sorted(tests.items(), key=lambda item: item[1].casefold()),
        "summary": summary,
    })


def physical_runs(rows, legacy_event_key):
    """Combine split copies using captured event IDs or the part report's legacy fingerprint."""
    events = defaultdict(list)
    for row in rows:
        capture = (row.metadata or {}).get("pervices_quality_report", {})
        if not isinstance(capture, dict):
            capture = {}
        event = capture.get("event_key")
        quantity = capture.get("tested_quantity")
        legacy = not event or quantity in (None, "")
        event = legacy_event_key(row) if legacy else event
        events[(row.user_id, row.stock_item.part_id, row.key, event)].append(
            (row, legacy, quantity)
        )

    for copies in events.values():
        row, legacy, quantity = copies[0]
        items = {copy.stock_item_id: copy.stock_item for copy, _, _ in copies}
        if legacy:
            quantity = sum(item.quantity or 0 for item in items.values())
        try:
            units = float(quantity)
            if not math.isfinite(units) or units <= 0:
                units = None
        except (TypeError, ValueError, OverflowError):
            units = None

        start, finish = row.started_datetime, row.finished_datetime
        seconds = (finish - start).total_seconds() if start and finish else 0
        part = row.stock_item.part
        yield {
            "user_id": row.user_id,
            "user": row.user.get_username() if row.user_id else "Unassigned",
            "part_id": part.pk,
            "part": part.IPN or part.name,
            "revision": part.revision,
            "test": row.test_name,
            "test_key": row.key,
            "date": row.work_time.astimezone(TORONTO).date().isoformat(),
            "result_ids": ", ".join(str(copy.pk) for copy, _, _ in copies),
            "stock_items": ", ".join(map(str, items)),
            "serials": ", ".join(str(item.serial) for item in items.values() if item.serial),
            "result": "Pass" if row.result else "Fail",
            "attempt": "Retest" if row.retest else "First attempt",
            "started": start.astimezone(TORONTO).isoformat() if start else "",
            "finished": finish.astimezone(TORONTO).isoformat() if finish else "",
            "recorded": row.date.astimezone(TORONTO).isoformat() if row.date else "",
            "quantity_source": "Estimated from current stock" if legacy else "Captured",
            "units": units,
            "hours": seconds / 3600 if seconds > 0 else None,
        }


def add_metrics(summary, run):
    units = run["units"] or 0
    hours = run["hours"]
    summary["runs"] += 1
    summary["units"] += units
    summary["legacy_runs"] += int(run["quantity_source"] != "Captured")
    attempt_key = "retest_units" if run["attempt"] == "Retest" else "first_attempt_units"
    summary[attempt_key] += units
    if hours is None:
        summary["untimed_runs"] += 1
    else:
        summary["hours"] += hours
        if run["units"] is not None:
            summary["timed_units"] += units
            summary["rate_hours"] += hours


def summarize(runs, single_test):
    levels = {}
    for run in runs:
        user = (run["user_id"],)
        part = (*user, run["part_id"])
        test = (*part, run["test_key"])
        day = (*test, run["date"])
        for identity, level, fields in (
            (user, "User total", ("user_id", "user")),
            (part, "Part total", ("user_id", "user", "part_id", "part", "revision")),
            (test, "Part and test", ("user_id", "user", "part_id", "part", "revision", "test", "test_key")),
            (day, "Daily", ("user_id", "user", "part_id", "part", "revision", "test", "test_key", "date")),
        ):
            if identity not in levels:
                levels[identity] = dict.fromkeys((*METRICS, "rate_hours"), 0)
                levels[identity].update({field: run[field] for field in fields}, level=level)
            add_metrics(levels[identity], run)

    for row in levels.values():
        rate_hours = row.pop("rate_hours")
        show_rate = row["level"] in ("Part and test", "Daily") or single_test
        row["units_per_hour"] = row["timed_units"] / rate_hours if show_rate and rate_hours else None
    return sorted(levels.values(), key=lambda row: (
        row["user"].casefold(), row.get("part", ""), row.get("revision") or "",
        row.get("test", ""), row.get("date", ""),
    ))


def export_csv(summary, runs):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="test-throughput-by-user.csv"'
    fields = (
        "level", "user", "user_id", "part", "part_id", "revision", "test", "date",
        *METRICS, "result_ids", "stock_items", "serials", "result", "attempt",
        "started", "finished", "recorded", "quantity_source",
    )
    writer = csv.writer(response)
    writer.writerow(fields)
    for row in [*summary, *({"level": "Run", **run} for run in runs)]:
        cells = [row.get(field) for field in fields]
        writer.writerow([
            "'" + value if isinstance(value, str)
            and (value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")))
            else value
            for value in cells
        ])
    return response

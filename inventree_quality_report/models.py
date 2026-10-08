"""Persistent production-timing metadata for the Quality Report plugin."""

from django.db import models


class TestTimingCapture(models.Model):
    """Immutable quantity captured when a StockItemTestResult is created.

    ``event_key`` groups InvenTree test-result rows which are copies of the same
    physical work event (for example when a StockItem split copies test history).
    The report counts each event_key once.
    """

    test_result_id = models.PositiveBigIntegerField(unique=True, db_index=True)
    event_key = models.CharField(max_length=96, db_index=True)
    tested_quantity = models.DecimalField(max_digits=20, decimal_places=6)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["test_result_id"]

    def __str__(self):
        return f"TestResult {self.test_result_id}: qty {self.tested_quantity}"

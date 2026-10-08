from django.apps import AppConfig


class InventreeQualityReportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "inventree_quality_report"

    def ready(self):
        from . import signals  # noqa: F401

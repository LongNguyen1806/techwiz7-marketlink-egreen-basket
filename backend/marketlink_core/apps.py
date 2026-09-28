from django.apps import AppConfig


class MarketlinkCoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "marketlink_core"

    def ready(self):
        from marketlink_core import signals  # noqa: F401

from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    verbose_name = 'Alerts'

    def ready(self):
        """Import signal handlers and configure services when Django starts."""
        # Import notification cache signal handlers
        import app.utils.notification_cache  # noqa: F401
        # Import Slack sync signal handlers
        import app.signals.slack_sync_signals  # noqa: F401
        # Import Telegram sync signal handlers
        import app.signals.telegram_sync_signals  # noqa: F401
        # Import Alert Group sync signal handlers
        import app.signals.group_sync_signals  # noqa: F401
        # Import alert runtime Redis projection signal handlers
        import app.signals.alert_runtime_sync_signals  # noqa: F401
        # Import alert cache signal handlers (alerts:address:* indexes)
        import app.signals.alert_cache_signals  # noqa: F401

        # NLP compilation runs in background tasks; no web-worker startup initialization required.

from django.apps import AppConfig


class HrmsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.hrms'

    def ready(self):
        import apps.hrms.signals  # noqa: F401

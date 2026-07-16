from django.apps import AppConfig


class BranchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.branch'
    label = 'branch'

    def ready(self):
        import apps.branch.signals  # noqa: F401

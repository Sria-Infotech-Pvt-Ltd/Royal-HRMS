from django.apps import AppConfig


class TrainingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.training'
    label = 'training'
    verbose_name = 'Training & Learning'

    def ready(self):
        from apps.training import signals  # noqa: F401

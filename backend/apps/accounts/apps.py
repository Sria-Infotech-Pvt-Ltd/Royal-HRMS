from django.apps import AppConfig


def _sync_permissions(sender, **kwargs):
    """Phase 4 Task A.2 — same post_migrate-sync convention as every
    platform_core registry (sync_entity_registry/sync_policy_types/
    sync_event_types/sync_job_types)."""
    from django.core.management import call_command
    call_command('sync_permissions', verbosity=0)


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    label = 'accounts'
    verbose_name = 'Accounts'

    def ready(self):
        import apps.accounts.signals  # noqa: F401

        from django.db.models.signals import post_migrate
        post_migrate.connect(_sync_permissions, sender=self)

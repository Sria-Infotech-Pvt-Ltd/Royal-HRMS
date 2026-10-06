from django.apps import AppConfig


def _sync_entity_registry(sender, **kwargs):
    """post_migrate hook — ensures a fresh install (or a test run that
    builds the DB from scratch) always has the Phase 2 core
    EntityDefinition rows, without a manual management-command step."""
    from django.core.management import call_command
    call_command('sync_entity_registry', verbosity=0)


class PlatformCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.platform_core'
    label = 'platform_core'
    verbose_name = 'Platform Core'

    def ready(self):
        from apps.platform_core import signals
        signals.connect()

        from django.db.models.signals import post_migrate
        post_migrate.connect(_sync_entity_registry, sender=self)

        from apps.platform_core import history
        from apps.platform_core.models import (
            AuthorisedSignatory, CustomRecord, EntityBankAccount, EntityDefinition,
            EntityIdentifier, FeatureFlag, FieldDefinition, FormLayout, LegalEntity,
            LookupType, LookupValue, NumberSeries,
        )
        # Registered on platform_core's own models only, as a proof the
        # capture mechanism works end-to-end — NOT yet on any existing
        # production model (User, EmployeeProfile, Role, SMTPSettings,
        # Branch, OrgUnit, Position, Candidate, etc.). Wiring those in is
        # deliberately deferred; see PHASE1_REPORT.md / PHASE2_REPORT.md.
        history.register(LegalEntity, exclude=['logo'])
        # Binary ciphertext fields are marked sensitive (not merely
        # excluded) so a "changed/not changed" fingerprint still shows in
        # history, rather than showing nothing at all — and because raw
        # `bytes` isn't JSON-serializable, so these MUST go through
        # _mask_value's string conversion rather than being stored as-is.
        history.register(EntityIdentifier, sensitive=['value', 'value_hash', 'value_encrypted'])
        history.register(EntityBankAccount, sensitive=['account_number_hash', 'account_number_encrypted', 'ifsc_encrypted'])
        history.register(AuthorisedSignatory, sensitive=['din_pan_encrypted'])
        history.register(LookupType)
        history.register(LookupValue)
        history.register(NumberSeries)
        history.register(FeatureFlag)
        # Phase 2 additions:
        history.register(EntityDefinition)
        history.register(FieldDefinition)
        history.register(FormLayout)
        history.register(CustomRecord, exclude=['data'])  # data's own field-level changes are logged by services_attributes/services_custom_objects instead of a whole-blob diff

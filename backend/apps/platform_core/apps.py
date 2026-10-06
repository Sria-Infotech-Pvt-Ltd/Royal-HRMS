from django.apps import AppConfig


class PlatformCoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.platform_core'
    label = 'platform_core'
    verbose_name = 'Platform Core'

    def ready(self):
        from apps.platform_core import signals
        signals.connect()

        from apps.platform_core import history
        from apps.platform_core.models import (
            AuthorisedSignatory, EntityBankAccount, EntityIdentifier,
            FeatureFlag, LegalEntity, LookupType, LookupValue, NumberSeries,
        )
        # Registered on the new platform_core models only, as a proof that
        # the capture mechanism works end-to-end — NOT yet on any existing
        # production model (User, EmployeeProfile, Role, SMTPSettings,
        # etc.). Wiring those in is deliberately deferred; see
        # PHASE1_REPORT.md.
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

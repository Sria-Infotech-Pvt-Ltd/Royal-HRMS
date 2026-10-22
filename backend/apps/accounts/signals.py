import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='accounts.ApprovalWorkflowRule')
@receiver(post_delete, sender='accounts.ApprovalWorkflowRule')
def on_approval_workflow_rule_change(sender, instance, **kwargs):
    from core.cache_service import ApprovalWorkflowCacheService
    ApprovalWorkflowCacheService.invalidate(instance.workflow_type)


@receiver(post_save, sender='accounts.Company')
def on_company_change(sender, instance, **kwargs):
    from core.cache_service import CompanyCacheService, FinancialYearCacheService
    FinancialYearCacheService.invalidate()
    CompanyCacheService.invalidate()


# ─── Phase 2 Task J: write-through mirror onto the new form engine ─────────
# The old onboarding config endpoints stay the source of truth while
# feature flag forms.v2 is OFF; every save here also syncs the mirrored
# FieldDefinition/FormLayout rows, so turning the flag on later loses
# nothing. See services_onboarding_sync.py for what is/isn't mirrored.

@receiver(post_save, sender='accounts.OnboardingFieldConfig')
def on_onboarding_field_config_change(sender, instance, **kwargs):
    from apps.platform_core import services_onboarding_sync
    try:
        services_onboarding_sync.sync_field_config(instance)
    except Exception:
        logger.warning('forms.v2 mirror sync failed for OnboardingFieldConfig %s', instance.field_key, exc_info=True)


@receiver(post_save, sender='accounts.OnboardingSection')
def on_onboarding_section_change(sender, instance, **kwargs):
    from apps.platform_core import services_onboarding_sync
    try:
        services_onboarding_sync.sync_section(instance)
    except Exception:
        logger.warning('forms.v2 mirror sync failed for OnboardingSection %s', instance.pk, exc_info=True)


# ─── Phase 4 Task K.1: bump the new authz effective-permissions cache whenever what a position (or
# everyone) may do changes. PositionAssignment/FieldPermission changes bump it from apps/platform_core/signals.py.

@receiver(post_save, sender='accounts.PositionPermission')
@receiver(post_delete, sender='accounts.PositionPermission')
@receiver(post_save, sender='accounts.BaselinePermission')
@receiver(post_delete, sender='accounts.BaselinePermission')
def on_access_permission_change(sender, instance, **kwargs):
    from apps.platform_core import cache as metadata_cache
    metadata_cache.bump_version('authz')

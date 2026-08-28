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

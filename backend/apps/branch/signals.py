import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='branch.Branch')
@receiver(post_delete, sender='branch.Branch')
def on_branch_change(sender, instance, **kwargs):
    from core.cache_service import BranchCacheService
    BranchCacheService.invalidate_all()

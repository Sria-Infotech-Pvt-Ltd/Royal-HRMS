import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='hrms.Holiday')
@receiver(post_delete, sender='hrms.Holiday')
def on_holiday_change(sender, instance, **kwargs):
    from core.cache_service import HolidayCacheService
    year = instance.date.year
    if instance.branch_id is None:
        HolidayCacheService.invalidate_year(year)
    else:
        branch_name = ''
        try:
            branch_name = instance.branch.branch_name
        except Exception:
            pass
        HolidayCacheService.invalidate_branch(branch_name, year)


@receiver(post_save, sender='hrms.LeavePolicy')
@receiver(post_delete, sender='hrms.LeavePolicy')
def on_leave_policy_change(sender, instance, **kwargs):
    from core.cache_service import LeavePolicyCacheService
    LeavePolicyCacheService.invalidate(instance.leave_type)

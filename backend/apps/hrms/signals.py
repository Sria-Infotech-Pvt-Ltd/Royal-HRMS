import logging
from django.db.models.signals import post_save, post_delete, pre_save
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


@receiver(pre_save, sender='hrms.LeavePolicy')
def keep_policy_note_numbers_in_step(sender, instance, **kwargs):
    """When a limit changes in the Leave Policy settings, the matching number in the policy note ("Max 3 consecutive days") follows."""
    if instance.pk is None:
        return
    from apps.hrms.models import LeavePolicy
    from apps.hrms.services_leave_policy_note import CARRY_FORWARD, CONSECUTIVE, NOTICE, sync_policy_note

    before = LeavePolicy.objects.filter(pk=instance.pk).values(
        'maximum_consecutive_days', 'minimum_notice_period', 'can_carry_forward', 'max_carry_forward_days',
    ).first()
    if not before:
        return
    changed = set()
    if (before['maximum_consecutive_days'] or 0) != (instance.maximum_consecutive_days or 0):
        changed.add(CONSECUTIVE)
    if (before['minimum_notice_period'] or 0) != (instance.minimum_notice_period or 0):
        changed.add(NOTICE)
    if (before['can_carry_forward'], float(before['max_carry_forward_days'] or 0)) != (instance.can_carry_forward, float(instance.max_carry_forward_days or 0)):
        changed.add(CARRY_FORWARD)
    if changed:
        sync_policy_note(instance, only=frozenset(changed))

"""
New joiners: when an employee's onboarding is approved (onboarding_status
moves to 'complete' — apps.accounts.views onboarding approval), assign the
courses marked "assign to new joiners". Only that transition triggers it, so
existing employees are never assigned retroactively.
"""
import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _completes_onboarding(instance, update_fields) -> bool:
    if getattr(instance, 'onboarding_status', None) != 'complete' or not instance.pk:
        return False
    return update_fields is None or 'onboarding_status' in update_fields


@receiver(pre_save, sender='accounts.User')
def _capture_onboarding_status(sender, instance, update_fields=None, **kwargs):
    instance._training_was_complete = True
    if _completes_onboarding(instance, update_fields):
        old = sender.objects.filter(pk=instance.pk).values_list('onboarding_status', flat=True).first()
        instance._training_was_complete = old == 'complete'


@receiver(post_save, sender='accounts.User')
def _assign_new_joiner_training(sender, instance, created, update_fields=None, **kwargs):
    if created or getattr(instance, '_training_was_complete', True):
        return
    if not _completes_onboarding(instance, update_fields):
        return
    instance._training_was_complete = True

    def run():
        try:
            from apps.training.services import assign_new_joiner
            n = assign_new_joiner(instance)
            if n:
                logger.info('Assigned %s new-joiner training course(s) to %s', n, instance.pk)
        except Exception:
            logger.exception('New-joiner training assignment failed for %s', instance.pk)

    transaction.on_commit(run)

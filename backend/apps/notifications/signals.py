import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

_LEAVE_LABELS = {
    'casual':    'Casual Leave',
    'earned':    'Earned Leave',
    'sick':      'Sick Leave',
    'lwp':       'Leave Without Pay',
    'maternity': 'Maternity Leave',
    'paternity': 'Paternity Leave',
}


def _leave_display(leave_type: str) -> str:
    return _LEAVE_LABELS.get(leave_type, leave_type.replace('_', ' ').title())


def _notify(user, title: str, message: str, notification_type: str,
            module: str, reference_id: str = '', created_by=None) -> None:
    """Create a single Notification row. Swallows all exceptions so a notification
    failure never breaks the business transaction that triggered it."""
    if not user:
        return
    try:
        from .models import Notification
        Notification.objects.create(
            user=user, title=title, message=message,
            notification_type=notification_type, module=module,
            reference_id=reference_id, created_by=created_by,
        )
    except Exception:
        logger.exception('Failed to create notification for user %s', getattr(user, 'id', None))


# ─── Leave Request ─────────────────────────────────────────────────────────────

@receiver(pre_save, sender='hrms.LeaveRequest')
def _capture_leave_status(sender, instance, **kwargs):
    instance._old_status = None
    if instance.pk:
        try:
            instance._old_status = (
                sender.objects.values_list('status', flat=True).get(pk=instance.pk)
            )
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='hrms.LeaveRequest')
def _on_leave_save(sender, instance, created, **kwargs):
    employee = instance.employee
    label    = _leave_display(instance.leave_type)
    ref_id   = str(instance.id)
    start    = instance.start_date.strftime('%d %b')
    end      = instance.end_date.strftime('%d %b')

    if created:
        _notify(employee, 'Leave Request Submitted',
                f'Your {label} request has been submitted successfully.',
                'leave_applied', 'leave', ref_id, employee)
        # L1 approver if assigned, or L2 when manager submits (goes straight to l2_pending)
        approver = instance.l1_approver or (
            instance.l2_approver if instance.status == 'l2_pending' else None
        )
        if approver:
            _notify(approver, 'New Leave Request',
                    f'{employee.full_name} has submitted a {label} request from {start} to {end}.',
                    'leave_applied', 'leave', ref_id, employee)
        return

    old_status = getattr(instance, '_old_status', None)
    if old_status == instance.status:
        return
    _dispatch_leave_status(instance, employee, label, ref_id, old_status, instance.status)


def _dispatch_leave_status(instance, employee, label, ref_id, old_st, new_st):
    if old_st == 'pending' and new_st == 'l2_pending':
        _notify(employee, 'Leave Forwarded to HR',
                f'Your {label} request has been forwarded to HR for approval.',
                'leave_manager_approved', 'leave', ref_id)
        if instance.l2_approver:
            _notify(instance.l2_approver, 'Leave Awaiting Approval',
                    f'Leave request of {employee.full_name} is awaiting your approval.',
                    'leave_manager_approved', 'leave', ref_id)

    elif old_st == 'pending' and new_st == 'approved':
        name = instance.l1_approver.full_name if instance.l1_approver else 'Manager'
        _notify(employee, 'Leave Approved',
                f'Your {label} request has been approved by {name}.',
                'leave_manager_approved', 'leave', ref_id)

    elif old_st == 'pending' and new_st == 'rejected':
        name = instance.l1_approver.full_name if instance.l1_approver else 'Manager'
        _notify(employee, 'Leave Rejected',
                f'Your {label} request has been rejected by {name} (Reporting Manager).',
                'leave_manager_rejected', 'leave', ref_id)

    elif old_st == 'l2_pending' and new_st == 'approved':
        name = instance.l2_approver.full_name if instance.l2_approver else 'HR'
        _notify(employee, 'Leave Approved',
                f'Your {label} request has been approved by {name} (HR).',
                'leave_hr_approved', 'leave', ref_id)

    elif old_st == 'l2_pending' and new_st == 'rejected':
        name = instance.l2_approver.full_name if instance.l2_approver else 'HR'
        _notify(employee, 'Leave Rejected',
                f'Your {label} request has been rejected by {name} (HR).',
                'leave_hr_rejected', 'leave', ref_id)

    elif new_st == 'cancelled':
        _notify(employee, 'Leave Cancelled',
                f'Your {label} request has been cancelled.',
                'leave_cancelled', 'leave', ref_id)


# ─── Attendance Correction (Regularization) ────────────────────────────────────

@receiver(pre_save, sender='attendance.AttendanceCorrection')
def _capture_correction_status(sender, instance, **kwargs):
    instance._old_status = None
    if instance.pk:
        try:
            instance._old_status = (
                sender.objects.values_list('status', flat=True).get(pk=instance.pk)
            )
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='attendance.AttendanceCorrection')
def _on_correction_save(sender, instance, created, **kwargs):
    employee = instance.employee
    ref_id   = str(instance.id)

    if created:
        _notify(employee, 'Regularization Submitted',
                'Your attendance regularization request has been submitted.',
                'regularization', 'attendance', ref_id, employee)
        hr = getattr(employee, 'hr', None)
        if hr:
            _notify(hr, 'Regularization Request Pending',
                    f'Attendance regularization request from {employee.full_name} is pending approval.',
                    'regularization', 'attendance', ref_id)
        return

    old_status = getattr(instance, '_old_status', None)
    if old_status == instance.status:
        return

    if instance.status == 'approved':
        _notify(employee, 'Regularization Approved',
                'Your attendance regularization request has been approved.',
                'regularization', 'attendance', ref_id)
    elif instance.status == 'rejected':
        _notify(employee, 'Regularization Rejected',
                'Your attendance regularization request has been rejected.',
                'regularization', 'attendance', ref_id)


# ─── Announcements ─────────────────────────────────────────────────────────────

@receiver(post_save, sender='announcements.Announcement')
def _on_announcement_save(sender, instance, created, **kwargs):
    if not created:
        return
    from apps.accounts.models import User
    from .models import Notification

    users = User.objects.filter(is_active=True)
    if instance.visibility == 'branch' and instance.target_branch_id:
        users = users.filter(branch=instance.target_branch.branch_name)
    elif instance.visibility == 'department' and instance.target_department_id:
        users = users.filter(department=instance.target_department.name)

    Notification.objects.bulk_create([
        Notification(
            user=user,
            title='New Announcement',
            message=instance.title,
            notification_type='announcement',
            module='announcement',
            reference_id=str(instance.id),
            created_by=instance.posted_by,
        )
        for user in users
    ], ignore_conflicts=True)

import logging

from django.db import transaction
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
        notification = Notification.objects.create(
            user=user, title=title, message=message,
            notification_type=notification_type, module=module,
            reference_id=reference_id, created_by=created_by,
        )
        _push_live(notification)
    except Exception:
        logger.exception('Failed to create notification for user %s', getattr(user, 'id', None))


def _push_live(notification) -> None:
    """
    Push the just-created notification over WebSocket to any open tab for
    this user (apps.notifications.consumers.NotificationConsumer). Best
    effort only — the DB row above is the source of truth; a dead channel
    layer or no open socket just means the 60s poll fallback picks it up.
    """
    try:
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        from .serializers import NotificationSerializer

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            f'notifications_{notification.user_id}',
            {'type': 'notification.push', 'notification': NotificationSerializer(notification).data},
        )
    except Exception:
        logger.warning('Live notification push failed for user %s', notification.user_id)


def _company_name() -> str:
    try:
        from apps.accounts.models import Company
        company = Company.objects.first()
        return company.company_name if company else ''
    except Exception:
        return ''


def _send_leave_email(user, template_name: str, context: dict) -> None:
    """
    Fire-and-forget leave lifecycle email, sent alongside the in-app
    Notification above. Queued to Celery (via transaction.on_commit) rather
    than sent inline — a failed/slow email must never break the leave save
    transaction. Queuing failure is logged, not raised, for the same reason.
    """
    if not user or not getattr(user, 'email', ''):
        return
    from apps.notifications.tasks import send_lifecycle_email_task

    def _dispatch(user_id=user.id, tpl=template_name, ctx=dict(context)):
        try:
            # retry=False + ignore_result=True — bounds broker/backend
            # retries so a down Redis can't block this request; see the
            # referral-submission dispatch in recruitment/views.py.
            send_lifecycle_email_task.apply_async(
                args=[user_id, tpl, ctx], retry=False, ignore_result=True,
            )
        except Exception as exc:
            logger.error(
                'Failed to queue leave email "%s" for user %s: %s',
                tpl, user_id, exc, exc_info=True,
            )

    transaction.on_commit(_dispatch)


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
        _send_leave_email(employee, 'leave_request_submitted', {
            'employee_name': employee.full_name or employee.email,
            'leave_type':    label,
            'start_date':    start,
            'end_date':      end,
            'total_days':    str(instance.total_days),
            'reason':        instance.reason,
        })
        # L1 approver if assigned, or L2 when manager submits (goes straight to l2_pending)
        approver = instance.l1_approver or (
            instance.l2_approver if instance.status == 'l2_pending' else None
        )
        if approver:
            _notify(approver, 'New Leave Request',
                    f'{employee.full_name} has submitted a {label} request from {start} to {end}.',
                    'leave_applied', 'leave', ref_id, employee)
            _send_leave_email(approver, 'leave_request_pending_approval', {
                'approver_name': approver.full_name or approver.email,
                'employee_name': employee.full_name or employee.email,
                'leave_type':    label,
                'start_date':    start,
                'end_date':      end,
                'total_days':    str(instance.total_days),
                'reason':        instance.reason,
            })
        return

    old_status = getattr(instance, '_old_status', None)
    if old_status == instance.status:
        return
    _dispatch_leave_status(instance, employee, label, ref_id, old_status, instance.status)


def _dispatch_leave_status(instance, employee, label, ref_id, old_st, new_st):
    start = instance.start_date.strftime('%d %b')
    end   = instance.end_date.strftime('%d %b')

    if old_st == 'pending' and new_st == 'l2_pending':
        approver_name = instance.l1_approver.full_name if instance.l1_approver else 'Manager'
        _notify(employee, 'Leave Forwarded to HR',
                f'Your {label} request has been forwarded to HR for approval.',
                'leave_manager_approved', 'leave', ref_id)
        _send_leave_email(employee, 'leave_forwarded_to_hr', {
            'employee_name': employee.full_name or employee.email,
            'approver_name': approver_name,
            'leave_type':    label,
            'start_date':    start,
            'end_date':      end,
        })
        if instance.l2_approver:
            _notify(instance.l2_approver, 'Leave Awaiting Approval',
                    f'Leave request of {employee.full_name} is awaiting your approval.',
                    'leave_manager_approved', 'leave', ref_id)
            _send_leave_email(instance.l2_approver, 'leave_request_pending_approval', {
                'approver_name': instance.l2_approver.full_name or instance.l2_approver.email,
                'employee_name': employee.full_name or employee.email,
                'leave_type':    label,
                'start_date':    start,
                'end_date':      end,
                'total_days':    str(instance.total_days),
                'reason':        instance.reason,
            })

    elif old_st == 'pending' and new_st == 'approved':
        name = instance.l1_approver.full_name if instance.l1_approver else 'Manager'
        _notify(employee, 'Leave Approved',
                f'Your {label} request has been approved by {name}.',
                'leave_manager_approved', 'leave', ref_id)
        _send_leave_email(employee, 'leave_approved', {
            'employee_name': employee.full_name or employee.email,
            'leave_type':    label,
            'start_date':    start,
            'end_date':      end,
            'total_days':    str(instance.total_days),
            'approver_name': name,
            'approver_role': 'Manager',
        })

    elif old_st == 'pending' and new_st == 'rejected':
        name = instance.l1_approver.full_name if instance.l1_approver else 'Manager'
        _notify(employee, 'Leave Rejected',
                f'Your {label} request has been rejected by {name} (Reporting Manager).',
                'leave_manager_rejected', 'leave', ref_id)
        _send_leave_email(employee, 'leave_rejected', {
            'employee_name': employee.full_name or employee.email,
            'leave_type':    label,
            'start_date':    start,
            'end_date':      end,
            'approver_name': name,
            'approver_role': 'Manager',
            'remarks':       instance.l1_remarks or '—',
        })

    elif old_st == 'l2_pending' and new_st == 'approved':
        name = instance.l2_approver.full_name if instance.l2_approver else 'HR'
        _notify(employee, 'Leave Approved',
                f'Your {label} request has been approved by {name} (HR).',
                'leave_hr_approved', 'leave', ref_id)
        _send_leave_email(employee, 'leave_approved', {
            'employee_name': employee.full_name or employee.email,
            'leave_type':    label,
            'start_date':    start,
            'end_date':      end,
            'total_days':    str(instance.total_days),
            'approver_name': name,
            'approver_role': 'HR',
        })

    elif old_st == 'l2_pending' and new_st == 'rejected':
        name = instance.l2_approver.full_name if instance.l2_approver else 'HR'
        _notify(employee, 'Leave Rejected',
                f'Your {label} request has been rejected by {name} (HR).',
                'leave_hr_rejected', 'leave', ref_id)
        _send_leave_email(employee, 'leave_rejected', {
            'employee_name': employee.full_name or employee.email,
            'leave_type':    label,
            'start_date':    start,
            'end_date':      end,
            'approver_name': name,
            'approver_role': 'HR',
            'remarks':       instance.l2_remarks or '—',
        })

    elif new_st == 'cancelled':
        _notify(employee, 'Leave Cancelled',
                f'Your {label} request has been cancelled.',
                'leave_cancelled', 'leave', ref_id)
        _send_leave_email(employee, 'leave_cancelled', {
            'employee_name': employee.full_name or employee.email,
            'leave_type':    label,
            'start_date':    start,
            'end_date':      end,
        })


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

    # Notification.id is a client-side uuid4 default, so each instance
    # already has its real pk before bulk_create — safe to push_live below
    # even though ignore_conflicts=True normally suppresses pk retrieval.
    notifications = [
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
    ]
    Notification.objects.bulk_create(notifications, ignore_conflicts=True)
    for notification in notifications:
        _push_live(notification)


# ─── Promotion ──────────────────────────────────────────────────────────────────

@receiver(post_save, sender='accounts.PromotionRecord')
def _on_promotion_record_created(sender, instance, created, **kwargs):
    if not created or instance.previous_designation == instance.new_designation:
        # Role-only changes (no designation change) aren't a "promotion" in
        # the sense this notification is about — only notify when the
        # designation itself actually moved.
        return

    effective = instance.effective_date.strftime('%d %B %Y')
    message = f'Congratulations! You have been promoted to {instance.new_designation}. Your new designation is effective from {effective}.'
    if instance.remarks:
        message += f' {instance.remarks}'

    # Deferred to transaction.on_commit: PromotionRecord.objects.create()
    # runs inside EmployeeDetailView.put()'s own transaction.atomic() block —
    # queuing the notification only after that transaction actually commits
    # means a promotion that later rolls back (for any reason) can never
    # have already notified the employee about a change that didn't happen.
    employee, promoted_by = instance.employee, instance.promoted_by
    reference_id = str(instance.id)

    def _send():
        # _notify() already swallows its own exceptions internally — this
        # extra try/except is defense-in-depth so that even a broken/mocked
        # notification path can never surface past the promotion transaction,
        # which has already committed successfully by the time this runs.
        try:
            _notify(
                employee, 'Congratulations on Your Promotion!', message,
                'promotion', 'promotion', reference_id, promoted_by,
            )
        except Exception:
            logger.exception('Failed to send promotion notification for employee %s', employee.id)

    transaction.on_commit(_send)

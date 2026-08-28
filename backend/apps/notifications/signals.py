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


# Maps a Notification.module value to the NotificationSettings category it's
# gated by, when the recipient is the subject of the event (e.g. their own
# leave request). Approver-facing notifications ("this needs your approval")
# pass category='approval' explicitly at the call site instead, since the
# same module/notification_type is reused for both the subject and the
# approver today.
_MODULE_DEFAULT_CATEGORY = {
    'leave':          'leave',
    'attendance':     'attendance',
    'regularization': 'attendance',
    'permission':     'attendance',
    'expense':        'expense',
    'separation':     'separation',
}


def _category_enabled(user, category: str | None) -> bool:
    """True if `user` has this notification category enabled. Categories with
    no mapping (e.g. birthday, promotion, announcement) are never gated —
    they fall through as always-enabled. A user with no NotificationSettings
    row yet also defaults to enabled, matching the model's field defaults."""
    if not category:
        return True
    try:
        from .models import NotificationSettings
        field = f'is_{category}_enabled'
        settings_row = NotificationSettings.objects.filter(user=user).only(field).first()
        if settings_row is None:
            return True
        return getattr(settings_row, field)
    except Exception:
        return True


def _category_enabled_user_ids(user_ids: list, category: str) -> list:
    """Bulk version of _category_enabled for a broadcast notification (e.g.
    a new Document Center upload going to many users at once) — one query
    instead of one per recipient. Same "no row = enabled" default as the
    single-user check above."""
    try:
        from .models import NotificationSettings
        field = f'is_{category}_enabled'
        disabled_ids = set(
            NotificationSettings.objects
            .filter(user_id__in=user_ids, **{field: False})
            .values_list('user_id', flat=True)
        )
        return [uid for uid in user_ids if uid not in disabled_ids]
    except Exception:
        return user_ids


def _notify(user, title: str, message: str, notification_type: str,
            module: str, reference_id: str = '', created_by=None,
            category: str | None = None) -> None:
    """Create a single Notification row. Swallows all exceptions so a notification
    failure never breaks the business transaction that triggered it."""
    if not user:
        return
    category = category or _MODULE_DEFAULT_CATEGORY.get(module)
    if not _category_enabled(user, category):
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

        from core.notification_groups import notification_group_name

        from .serializers import NotificationSerializer

        channel_layer = get_channel_layer()
        if channel_layer is None:
            return
        async_to_sync(channel_layer.group_send)(
            notification_group_name(notification.user_id),
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
                    'leave_applied', 'leave', ref_id, employee, category='approval')
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
                    'leave_manager_approved', 'leave', ref_id, category='approval')
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
                    'regularization', 'attendance', ref_id, category='approval')
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
    elif instance.visibility == 'department' and instance.target_org_unit_id:
        from apps.accounts.services_approval import filter_users_by_org_unit
        users = filter_users_by_org_unit(users, instance.target_org_unit)

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


# ─── Expense ────────────────────────────────────────────────────────────────────

def _resolve_expense_approver(employee):
    """One specific person to ping about a new expense, mirroring the priority
    apps.hrms.views.expenses._can_access_expense already uses to decide who
    may act on it: the reporting manager first, then assigned HR — but only
    if that specific person actually holds expenses.approve, since
    can_manage_team/HR-assignment alone don't imply approval rights (see that
    view's own ExpenseListCreateView.get scoping). Returns None rather than
    guessing when neither resolves, same as leave's l1_approver-less case."""
    from core.permissions import has_perm
    manager = employee.reporting_manager
    if manager and has_perm(manager, 'expenses.approve'):
        return manager
    hr = employee.hr
    if hr and has_perm(hr, 'expenses.approve'):
        return hr
    return None


@receiver(pre_save, sender='hrms.Expense')
def _capture_expense_status(sender, instance, **kwargs):
    instance._old_status = None
    if instance.pk:
        try:
            instance._old_status = (
                sender.objects.values_list('status', flat=True).get(pk=instance.pk)
            )
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='hrms.Expense')
def _on_expense_save(sender, instance, created, **kwargs):
    employee = instance.employee
    ref_id   = str(instance.id)

    if created:
        _notify(employee, 'Expense Submitted',
                f'Your expense "{instance.title}" has been submitted for approval.',
                'expense_submitted', 'expense', ref_id, employee)
        approver = _resolve_expense_approver(employee)
        if approver:
            _notify(approver, 'New Expense Pending Approval',
                    f'{employee.full_name} submitted an expense — "{instance.title}".',
                    'expense_submitted', 'expense', ref_id, employee, category='approval')
        return

    old_status = getattr(instance, '_old_status', None)
    if old_status == instance.status:
        return
    if instance.status == 'approved':
        _notify(employee, 'Expense Approved',
                f'Your expense "{instance.title}" has been approved.',
                'expense_status', 'expense', ref_id)
    elif instance.status == 'rejected':
        _notify(employee, 'Expense Rejected',
                f'Your expense "{instance.title}" has been rejected.',
                'expense_status', 'expense', ref_id)


# ─── Separation ─────────────────────────────────────────────────────────────────

@receiver(pre_save, sender='hrms.SeparationRequest')
def _capture_separation_status(sender, instance, **kwargs):
    instance._old_status = None
    if instance.pk:
        try:
            instance._old_status = (
                sender.objects.values_list('status', flat=True).get(pk=instance.pk)
            )
        except sender.DoesNotExist:
            pass


@receiver(post_save, sender='hrms.SeparationRequest')
def _on_separation_save(sender, instance, created, **kwargs):
    if created:
        # The approval chain (instance.approval_stages) is bulk_created right
        # after SeparationRequest.objects.create() in the same atomic block
        # (see SeparationRequestListCreateView.post) — querying it now, before
        # that block commits, would always find zero stages. Deferred to
        # on_commit, same reasoning as the PromotionRecord notification above.
        transaction.on_commit(lambda pk=instance.pk: _notify_separation_created(pk))
        return

    old_status = getattr(instance, '_old_status', None)
    if old_status == instance.status:
        return
    _dispatch_separation_status(instance, instance.employee, str(instance.id), instance.status)


def _notify_separation_created(sep_request_id) -> None:
    from apps.hrms.models import SeparationRequest
    try:
        sep_request = (
            SeparationRequest.objects
            .select_related('employee')
            .prefetch_related('approval_stages')
            .get(pk=sep_request_id)
        )
    except SeparationRequest.DoesNotExist:
        return
    employee, ref_id = sep_request.employee, str(sep_request.id)
    _notify(employee, 'Separation Request Submitted',
            'Your separation request has been submitted successfully.',
            'separation_submitted', 'separation', ref_id, employee)
    first_stage = sep_request.approval_stages.order_by('sequence').first()
    if first_stage and first_stage.approver:
        _notify(first_stage.approver, 'Separation Request Pending Your Approval',
                f'{employee.full_name}’s separation request needs your approval.',
                'separation_submitted', 'separation', ref_id, employee, category='approval')


def _dispatch_separation_status(instance, employee, ref_id, new_status) -> None:
    from apps.hrms.models import APPROVAL_PENDING, SEP_APPROVED, SEP_REJECTED, SEP_STAGE2_PENDING

    if new_status == SEP_STAGE2_PENDING:
        _notify(employee, 'Separation Request — Stage Approved',
                'Your separation request has moved to the next approval stage.',
                'separation_status', 'separation', ref_id)
        next_stage = instance.approval_stages.filter(status=APPROVAL_PENDING).order_by('sequence').first()
        if next_stage and next_stage.approver:
            _notify(next_stage.approver, 'Separation Request Pending Your Approval',
                    f'{employee.full_name}’s separation request needs your approval.',
                    'separation_status', 'separation', ref_id, employee, category='approval')
    elif new_status == SEP_APPROVED:
        _notify(employee, 'Separation Request Approved',
                'Your separation request has been fully approved.',
                'separation_status', 'separation', ref_id)
    elif new_status == SEP_REJECTED:
        _notify(employee, 'Separation Request Rejected',
                'Your separation request has been rejected.',
                'separation_status', 'separation', ref_id)


# ─── Document Center ────────────────────────────────────────────────────────────

@receiver(post_save, sender='accounts.Document')
def _on_document_save(sender, instance, created, **kwargs):
    """Broadcasts a new Document Center upload — same shape as the
    Announcement broadcast above, but gated by is_document_enabled since,
    unlike an announcement, a document upload is exactly the kind of
    notification the settings page already promises users control over."""
    if not created:
        return
    from apps.accounts.models import User
    from .models import Notification

    users = User.objects.filter(is_active=True)
    if instance.branch_id:
        users = users.filter(branch=instance.branch.branch_name)
    user_ids = _category_enabled_user_ids(list(users.values_list('id', flat=True)), 'document')

    notifications = [
        Notification(
            user_id=uid,
            title='New Document Available',
            message=f'"{instance.title}" was added to the Document Center.',
            notification_type='document_uploaded',
            module='documents',
            reference_id=str(instance.id),
            created_by=instance.uploaded_by,
        )
        for uid in user_ids
    ]
    Notification.objects.bulk_create(notifications, ignore_conflicts=True)
    for notification in notifications:
        _push_live(notification)

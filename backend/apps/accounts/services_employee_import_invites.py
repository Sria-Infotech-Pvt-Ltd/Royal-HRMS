"""
Activation invitations for a bulk employee import: a durable, retry-safe pipeline instead of an in-memory thread.

Flow: the commit writes one EmployeeImportInvite row per new employee INSIDE the employees' transaction (create_invites);
afterwards dispatch_invites queues one Celery task per pending row (if Redis is down the rows stay pending and requeue_stale(),
a beat task, picks them up); process_invite() claims a row under a database lock, sends through the existing
send_activation_invite (token via PasswordResetToken, attempt in EmailLog) and records sent / retry / failed / skipped.

Honest limits: delivery is AT-LEAST-ONCE, never exactly-once (a crash after the mail server accepted a message but before it was
recorded may cause one repeat; `ambiguous_attempts` counts such cases, and an EmailLog entry showing acceptance prevents a resend).
At most one open invitation per employee across ALL batches. Retries are bounded, only for transient errors; failure reasons are
short codes, never an address or exception text.
"""
from __future__ import annotations

import collections
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.accounts.models import AuditLog, EmailLog, EmployeeImportInvite, PasswordResetToken, User
from apps.accounts.models_import_invite import (
    OPEN_STATUSES, STATUS_FAILED, STATUS_PENDING, STATUS_PROCESSING, STATUS_SENT, STATUS_SKIPPED,
)
from apps.accounts.services_employee_import_invite_policy import (  # noqa: F401 - re-exported: the pipeline's single public surface
    BACKOFF_SECONDS, FAILURE_REASON, INVITE_TEMPLATE, PROGRESS_ACTION, REASONS, UNQUEUED_GRACE_SECONDS, InviteSendingHeld, backoff as _backoff, classify,
    invites_enabled, max_attempts, stale_after,
)
from apps.accounts.utils import send_activation_invite

logger = logging.getLogger(__name__)


def _is_stale(invite: EmployeeImportInvite, now) -> bool:
    return invite.processing_started_at is None or invite.processing_started_at <= now - stale_after()


# ── creating the to-do list (inside the commit transaction) ──────────────────────────────────────────────────────────────

def _has_delivered_valid_invite(user: User, now) -> bool:
    token = PasswordResetToken.objects.filter(
        user=user, purpose=PasswordResetToken.PURPOSE_INVITE, is_used=False, expires_at__gt=now).order_by('-created_at').first()
    return bool(token) and EmailLog.objects.filter(
        recipient_email__iexact=user.email, template_name=INVITE_TEMPLATE, status=EmailLog.STATUS_SENT, created_at__gte=token.created_at).exists()


def _delivered_user_ids(users: list[User], now) -> set:
    """Users who hold a valid, unused invitation link AND whose email log shows it was accepted by the mail server. Two queries in all."""
    tokens: dict = {}
    for user_id, created_at in PasswordResetToken.objects.filter(
            user__in=users, purpose=PasswordResetToken.PURPOSE_INVITE, is_used=False, expires_at__gt=now).values_list('user_id', 'created_at'):
        tokens[user_id] = max(created_at, tokens.get(user_id, created_at))
    if not tokens:
        return set()
    by_email = {u.email.lower(): u.pk for u in users if u.pk in tokens}
    logs = EmailLog.objects.annotate(recipient_lower=Lower('recipient_email')).filter(
        recipient_lower__in=list(by_email), template_name=INVITE_TEMPLATE, status=EmailLog.STATUS_SENT).values_list('recipient_lower', 'created_at')
    return {by_email[email] for email, sent_at in logs if sent_at >= tokens[by_email[email]]}


def _insert_invites(rows: list[EmployeeImportInvite]) -> None:
    try:
        with transaction.atomic():
            EmployeeImportInvite.objects.bulk_create(rows)
    except IntegrityError:                                           # a racing batch just opened one for some employee: sort it out row by row
        for invite in rows:
            try:
                with transaction.atomic():
                    invite.save(force_insert=True)
            except IntegrityError:
                invite.status, invite.reason_code = STATUS_SKIPPED, 'duplicate_open_invite'
                EmployeeImportInvite.objects.get_or_create(batch_id=invite.batch_id, user_id=invite.user_id, defaults={
                    'created_by_id': invite.created_by_id, 'row_number': invite.row_number, 'status': invite.status, 'reason_code': invite.reason_code})


def create_invites(importer: User, batch_id, items: list[tuple[int, str, str]]) -> dict:
    """items are (Excel row, user pk, employee id). Idempotent per (batch, employee). Call inside the transaction that creates the
    employees. A handful of queries for the whole list, not several per employee. Returns the counts and the ids still to be queued."""
    batch, now = uuid.UUID(str(batch_id)), timezone.now()
    wanted = [uuid.UUID(str(pk)) for _r, pk, _e in items]
    users = {u.pk: u for u in User.objects.filter(pk__in=wanted).only('pk', 'email', 'account_activated_at')}
    existing = set(EmployeeImportInvite.objects.filter(batch_id=batch, user_id__in=wanted).values_list('user_id', flat=True))
    open_elsewhere = set(EmployeeImportInvite.objects.filter(user_id__in=wanted, status__in=OPEN_STATUSES).exclude(batch_id=batch).values_list('user_id', flat=True))
    delivered = _delivered_user_ids([users[pk] for pk in wanted if pk not in existing and users[pk].pk not in open_elsewhere], now)
    rows = []
    for row, user_pk, _employee_id in items:
        user = users[uuid.UUID(str(user_pk))]
        if user.pk in existing:
            continue
        reason = ('already_activated' if user.account_activated_at else 'duplicate_open_invite' if user.pk in open_elsewhere
                  else 'already_invited' if user.pk in delivered else '')
        rows.append(EmployeeImportInvite(batch_id=batch, user_id=user.pk, created_by=importer, row_number=row,
                                         status=STATUS_SKIPPED if reason else STATUS_PENDING, reason_code=reason))
    _insert_invites(rows)
    pending = list(EmployeeImportInvite.objects.filter(batch_id=batch, user_id__in=[r.user_id for r in rows], status=STATUS_PENDING).values_list('pk', flat=True))
    return {'created': len(rows), 'existing': len(existing), 'pending_ids': pending}


# ── sending ──────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _finish(pk, status: str, reason: str = '') -> None:
    EmployeeImportInvite.objects.filter(pk=pk).update(
        status=status, reason_code=reason, processing_started_at=None, next_attempt_at=None,
        sent_at=timezone.now() if status == STATUS_SENT else None, updated_at=timezone.now())


def _mail_accepted_since(invite: EmployeeImportInvite) -> bool:
    """True when the EmailLog shows an invitation was accepted by the mail server after the stuck attempt began."""
    if invite.processing_started_at is None:
        return False
    return EmailLog.objects.filter(recipient_email__iexact=invite.user.email, template_name=INVITE_TEMPLATE,
                                   status=EmailLog.STATUS_SENT, created_at__gte=invite.processing_started_at).exists()


def _claim(invite_id, now):
    """Take the invitation under a row lock. Returns (outcome, invite): outcome is None when THIS call now owns the invitation."""
    with transaction.atomic():
        invite = (EmployeeImportInvite.objects.select_for_update(skip_locked=True, of=('self',))
                  .select_related('user').filter(pk=invite_id).first())
        if invite is None:
            return 'busy_or_missing', None
        if invite.status not in OPEN_STATUSES:
            return invite.status, None                               # already finished: running a task twice is harmless
        if invite.status == STATUS_PROCESSING and not _is_stale(invite, now):
            return 'in_progress', None
        if invite.status == STATUS_PENDING and invite.next_attempt_at and invite.next_attempt_at > now:
            return 'not_due', None
        if invite.status == STATUS_PROCESSING:                       # an earlier attempt never finished (worker died or was restarted)
            if _mail_accepted_since(invite):
                _finish(invite.pk, STATUS_SENT)
                return STATUS_SENT, None
            invite.ambiguous_attempts += 1
        if invite.attempts >= max_attempts():
            _finish(invite.pk, STATUS_FAILED, invite.reason_code or 'max_attempts')
            return STATUS_FAILED, None
        invite.status, invite.attempts, invite.processing_started_at = STATUS_PROCESSING, invite.attempts + 1, now
        invite.save(update_fields=['status', 'attempts', 'ambiguous_attempts', 'processing_started_at', 'updated_at'])
        return None, invite


def _skip_reason(user: User, now) -> str:
    if not user.is_active:
        return 'employee_inactive'
    if user.account_activated_at:
        return 'already_activated'
    return 'already_invited' if _has_delivered_valid_invite(user, now) else ''


def _deliver(invite: EmployeeImportInvite) -> str:
    now = timezone.now()
    reason = _skip_reason(invite.user, now)
    if reason:
        _finish(invite.pk, STATUS_SKIPPED, reason)
        return STATUS_SKIPPED
    try:
        # issues the token via PasswordResetToken, writes EmailLog; bulk_import=True makes the function itself honour the hold switch
        send_activation_invite(invite.user, created_by=invite.created_by, bulk_import=True)
    except InviteSendingHeld:                    # switched off after this invitation was claimed: put it back exactly as it was
        EmployeeImportInvite.objects.filter(pk=invite.pk).update(
            status=STATUS_PENDING, attempts=max(invite.attempts - 1, 0), processing_started_at=None, updated_at=timezone.now())
        return 'held'
    except Exception as exc:                                                 # noqa: BLE001 - classified and recorded, never raised
        code, transient = classify(exc)
        logger.warning('Import invitation %s failed (%s) on attempt %s', invite.pk, code, invite.attempts)   # no address, no exception text
        if transient and invite.attempts < max_attempts():
            EmployeeImportInvite.objects.filter(pk=invite.pk).update(
                status=STATUS_PENDING, reason_code=code, processing_started_at=None,
                next_attempt_at=now + _backoff(invite.attempts), updated_at=timezone.now())
            return 'retry'
        _finish(invite.pk, STATUS_FAILED, code)
        return STATUS_FAILED
    _finish(invite.pk, STATUS_SENT)
    return STATUS_SENT


def process_invite(invite_id) -> str:
    """Send one invitation. Safe to call any number of times, from any number of workers, at any time."""
    if not invites_enabled():                    # the hold: touch nothing (no claim, no attempt counted, no token, no mail)
        return 'held'
    outcome, invite = _claim(invite_id, timezone.now())
    return outcome if invite is None else _deliver(invite)


def retry_delay_seconds(invite_id) -> int:
    due = EmployeeImportInvite.objects.filter(pk=invite_id).values_list('next_attempt_at', flat=True).first()
    return max(0, int((due - timezone.now()).total_seconds())) if due else 0


# ── queueing ─────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _enqueue(ids) -> int:
    from apps.accounts.tasks import send_import_invite

    if not invites_enabled():                    # the hold: put nothing on the broker, the rows stay pending for when it is lifted
        logger.info('Bulk-import invitations are held (EMPLOYEE_IMPORT_INVITES_ENABLED is off); nothing was queued')
        return 0
    queued = 0
    for pk in ids:
        try:
            send_import_invite.delay(str(pk))
        except Exception:                                                    # noqa: BLE001 - broker (Redis) unreachable
            logger.warning('Could not queue import invitations (broker unavailable); %s remain pending for the recovery sweep', len(ids) - queued)
            break
        queued += 1
    return queued


def _due_pending(batch: uuid.UUID | None = None):
    qs = EmployeeImportInvite.objects.filter(status=STATUS_PENDING).filter(Q(next_attempt_at__isnull=True) | Q(next_attempt_at__lte=timezone.now()))
    return qs.filter(batch_id=batch) if batch else qs


def enqueue_batch(batch_id) -> int:
    return _enqueue(list(_due_pending(uuid.UUID(str(batch_id))).values_list('pk', flat=True)))


def enqueue_ids(ids) -> int:
    """Queue exactly these invitations (the ones a chunk just created), after that chunk's transaction has committed."""
    ids = list(ids)
    if not invites_enabled():
        return 0
    if getattr(settings, 'RUNNING_TESTS', False):                            # deterministic, no broker, under the test runner
        for pk in ids:
            process_invite(pk)
        return len(ids)
    return _enqueue(ids)


def drain_batch(batch_id) -> int:
    """Process the batch right here, without Celery or Redis (tests, and the command's --inline fallback)."""
    if not invites_enabled():
        return 0
    ids = list(_due_pending(uuid.UUID(str(batch_id))).values_list('pk', flat=True))
    for pk in ids:
        process_invite(pk)
    return len(ids)


def dispatch_invites(importer: User, batch_id, items, ip_address=None) -> dict:
    """Hand the batch to the workers after the employees are committed. Returns the progress so far."""
    if getattr(settings, 'RUNNING_TESTS', False):
        drain_batch(batch_id)
    else:
        enqueue_batch(batch_id)
    return batch_progress(batch_id)


def requeue_stale() -> dict:
    """Recovery sweep (beat task): queue invitations whose worker died, whose retry is due, or that were never queued."""
    if not invites_enabled():                    # the hold: the sweep reads and changes nothing while invitations are switched off
        return {'held': True, 'stale_processing': 0, 'pending_due': 0, 'queued': 0}
    now = timezone.now()
    stuck = list(EmployeeImportInvite.objects.filter(status=STATUS_PROCESSING, processing_started_at__lte=now - stale_after()).values_list('pk', flat=True))
    # Pending and due: a retry whose time has come, or a fresh invitation nobody queued (broker was down) for longer than the grace period.
    due = list(_due_pending().filter(Q(next_attempt_at__isnull=False) | Q(updated_at__lte=now - timedelta(seconds=UNQUEUED_GRACE_SECONDS)))
               .values_list('pk', flat=True))
    return {'stale_processing': len(stuck), 'pending_due': len(due), 'queued': _enqueue(stuck + due)}


# ── progress and manual retry ────────────────────────────────────────────────────────────────────────────────────────────

def batch_progress(batch_id) -> dict:
    rows = list(EmployeeImportInvite.objects.filter(batch_id=uuid.UUID(str(batch_id))).values('row_number', 'status', 'reason_code', 'user__employee_id'))
    counts = collections.Counter(r['status'] for r in rows)
    failed = [{'row': r['row_number'], 'employee_id': r['user__employee_id'], 'reason': REASONS.get(r['reason_code'], FAILURE_REASON)}
              for r in rows if r['status'] == STATUS_FAILED]
    still_working = counts[STATUS_PENDING] + counts[STATUS_PROCESSING]
    return {'batch_id': str(batch_id), 'held': not invites_enabled(), 'state': 'sending' if still_working else 'done', 'total': len(rows), 'sent': counts[STATUS_SENT],
            'pending': counts[STATUS_PENDING], 'processing': counts[STATUS_PROCESSING], 'skipped': counts[STATUS_SKIPPED], 'failed': failed}


def invite_progress(importer: User, batch_id) -> dict | None:
    if EmployeeImportInvite.objects.filter(batch_id=uuid.UUID(str(batch_id)), created_by=importer).exists():
        return batch_progress(batch_id)
    entry = AuditLog.objects.filter(user=importer, action=PROGRESS_ACTION, module='accounts', changes__batch_id=str(batch_id)).order_by('-created_at').first()
    if entry is None:                                                         # batches imported before the invitation table existed
        return None
    changes = entry.changes
    finished = changes['sent'] + len(changes['failed']) >= changes['total']
    return {'batch_id': str(batch_id), 'state': 'done' if finished else 'sending', 'total': changes['total'], 'sent': changes['sent'], 'failed': changes['failed']}


def retry_batch(importer: User, batch_id, *, inline: bool = False) -> dict:
    """Put FAILED invitations back to pending and queue them. Idempotent: a second call finds nothing failed. Never touches employees."""
    batch, requeued = uuid.UUID(str(batch_id)), 0
    for invite in EmployeeImportInvite.objects.filter(batch_id=batch, created_by=importer, status=STATUS_FAILED):
        try:
            with transaction.atomic():
                EmployeeImportInvite.objects.filter(pk=invite.pk, status=STATUS_FAILED).update(
                    status=STATUS_PENDING, attempts=0, reason_code='', next_attempt_at=None, updated_at=timezone.now())
            requeued += 1
        except IntegrityError:                                                # this employee already has another open invitation
            continue
    pending = drain_batch(batch) if inline else enqueue_batch(batch)
    return {'requeued': requeued, 'dispatched': pending}

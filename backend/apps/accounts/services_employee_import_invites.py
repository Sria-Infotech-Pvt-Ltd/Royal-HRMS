"""
Activation invitations for a bulk employee import.

Each invite is an SMTP send and takes several seconds, so 50 of them must not hold the commit request open. The commit
returns as soon as the employees exist; this module then sends the invites one by one in a background thread and keeps a
progress record (batch id, counts, failed rows with employee ids and a generic reason, never names or addresses) that the
screen polls. Under the test runner the work runs inline so tests stay deterministic.
"""
from __future__ import annotations

import logging
import threading

from django.conf import settings
from django.db import connections

from apps.accounts.models import AuditLog, User
from apps.accounts.utils import send_activation_invite

logger = logging.getLogger(__name__)

PROGRESS_ACTION = 'employee_bulk_import_invites'
FAILURE_REASON = 'The activation email could not be sent. Use Resend Invite on the employee.'


def start_progress(importer: User, batch_id: str, total: int, ip_address: str | None) -> int:
    entry = AuditLog.objects.create(
        user=importer, action=PROGRESS_ACTION, module='accounts', object_id=batch_id,
        changes={'batch_id': batch_id, 'total': total, 'sent': 0, 'failed': []},
        branch=importer.branch, ip_address=ip_address,
    )
    return entry.pk


def _work(importer_pk, progress_pk: int, items: list[tuple[int, str, str]]) -> dict:
    """items are (Excel row, user pk, employee id). Updates the progress record after every invite."""
    importer = User.objects.get(pk=importer_pk)
    changes = AuditLog.objects.get(pk=progress_pk).changes
    for row, user_pk, employee_id in items:
        try:
            send_activation_invite(User.objects.get(pk=user_pk), created_by=importer)
            changes['sent'] += 1
        except Exception as exc:  # noqa: BLE001 - delivery problems of any kind are reported per employee, never abort the rest
            logger.warning('Bulk import invite failed for row %s (%s)', row, type(exc).__name__)
            changes['failed'].append({'row': row, 'employee_id': employee_id, 'reason': FAILURE_REASON})
        AuditLog.objects.filter(pk=progress_pk).update(changes=changes)
    return changes


def _work_in_thread(importer_pk, progress_pk: int, items) -> None:
    try:
        _work(importer_pk, progress_pk, items)
    except Exception:  # noqa: BLE001 - last resort for the background thread; the progress record keeps what was done
        logger.exception('Bulk import invite worker stopped unexpectedly')
    finally:
        connections.close_all()


def dispatch_invites(importer: User, batch_id: str, items: list[tuple[int, str, str]], ip_address: str | None) -> dict:
    """Start sending. Returns the progress so far: complete when run inline, `sent: 0` when it was handed to a thread."""
    progress_pk = start_progress(importer, batch_id, len(items), ip_address)
    if getattr(settings, 'RUNNING_TESTS', False):
        return _work(importer.pk, progress_pk, items)
    threading.Thread(target=_work_in_thread, args=(importer.pk, progress_pk, items), daemon=True, name=f'import-invites-{batch_id}').start()
    return AuditLog.objects.get(pk=progress_pk).changes


def invite_progress(importer: User, batch_id: str) -> dict | None:
    entry = AuditLog.objects.filter(user=importer, action=PROGRESS_ACTION, module='accounts', changes__batch_id=batch_id).order_by('-created_at').first()
    if entry is None:
        return None
    changes = entry.changes
    finished = changes['sent'] + len(changes['failed']) >= changes['total']
    return {'batch_id': batch_id, 'state': 'done' if finished else 'sending', 'total': changes['total'], 'sent': changes['sent'], 'failed': changes['failed']}

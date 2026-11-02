"""
Audit entries for payroll configuration changes (settings, statutory and
branch config, salary structures/components, employee salary revisions,
structure imports). One AuditLog row per change, module='payroll', with a
field-level {field: {from, to}} diff.

Salary amounts in an employee's revision are recorded as "changed" only,
never their values — the audit log is readable by audit.view holders who
aren't necessarily allowed to see salaries.
"""
from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

from apps.accounts.models import AuditLog
from core.responses import get_client_ip

_SKIP = frozenset({'id', 'created_at', 'updated_at'})


def _plain(value):
    if isinstance(value, (Decimal, uuid.UUID)):
        return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if hasattr(value, 'name') and hasattr(value, 'storage'):   # FieldFile
        return value.name or None
    return value


def snapshot(instance) -> dict:
    """Concrete field values of a model instance, JSON-safe (FKs as ids)."""
    return {
        f.name: _plain(getattr(instance, f.attname))
        for f in instance._meta.concrete_fields if f.name not in _SKIP
    }


def log_change(request, action: str, object_id, before: dict | None, after: dict | None,
               *, redact=(), extra: dict | None = None) -> None:
    """before=None → created (records after); after=None → removed (records
    before); otherwise only fields whose value changed. A no-op update with
    nothing changed writes nothing."""
    redact = set(redact)

    def shown(key, value):
        return '(changed)' if key in redact else value

    if before is None:
        changes = {k: shown(k, v) for k, v in (after or {}).items()}
    elif after is None:
        changes = {k: shown(k, v) for k, v in before.items()}
    else:
        changes = {
            k: ({'changed': True} if k in redact else {'from': before.get(k), 'to': v})
            for k, v in after.items() if before.get(k) != v
        }
        if not changes:
            return
    if extra:
        changes.update(extra)
    AuditLog.objects.create(
        user=request.user, action=action, module='payroll', object_id=str(object_id),
        changes=changes, ip_address=get_client_ip(request),
    )

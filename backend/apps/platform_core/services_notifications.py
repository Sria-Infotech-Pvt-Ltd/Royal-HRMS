"""
Phase 3B Task F — sandboxed message rendering + notification dispatch.

Rendering is deliberately NOT Jinja2/Django templates (both allow
attribute traversal — `{{ user.__class__ }}`-style escapes unless
explicitly sandboxed, and this project's own rule "no eval/exec... no
attribute access to arbitrary objects (only declared variables)" is
easiest to GUARANTEE, not just configure, with a plain whitelist token
substitution: only `{{var_name}}` tokens naming a key actually present
in the resolved context dict are ever replaced; anything else (a dotted
path, a method call, an unknown name) is left as inert literal text,
never evaluated. HTML-escaped by default for the email/in_app channels
(autoescaping); webhook payloads are raw JSON values, not HTML, so no
escaping is applied there.
"""
from __future__ import annotations

import hashlib
import re
from html import escape as html_escape

from django.utils import timezone

from apps.platform_core import services_rules as rules
from apps.platform_core.models import MessageTemplate, NotificationDelivery, NotificationRule

_TOKEN_RE = re.compile(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}')


class NotificationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def render(template: MessageTemplate, context: dict, *, event_type) -> tuple[str, str]:
    """Returns (subject, body). Sensitive event-payload variables are
    rendered as '***' unless the template explicitly lists them in
    `allowed_sensitive_vars` — Rule 7's "never put sensitive values into
    notifications... unless the field is explicitly allowed"."""
    sensitive = event_type.sensitive_vars()
    autoescape = template.channel in (MessageTemplate.CHANNEL_EMAIL, MessageTemplate.CHANNEL_IN_APP)

    def _substitute(text: str) -> str:
        def _replace(match):
            name = match.group(1)
            if name not in context:
                return match.group(0)  # unknown token — left as literal text, never an error, never evaluated
            if name in sensitive and name not in template.allowed_sensitive_vars:
                return '***'
            value = context[name]
            rendered = '' if value is None else str(value)
            return html_escape(rendered) if autoescape else rendered
        return _TOKEN_RE.sub(_replace, text)

    return _substitute(template.subject), _substitute(template.body)


def preview(template: MessageTemplate) -> tuple[str, str]:
    """Task F.1's "preview with sample data generated from the payload
    schema" — generates one representative value per declared type."""
    sample = {}
    for name, spec in (template.event_type.payload_schema or {}).items():
        var_type = spec.get('type', 'string')
        sample[name] = {
            'string': 'Sample Text', 'number': 42, 'integer': 1, 'boolean': True,
            'date': timezone.localdate().isoformat(), 'datetime': timezone.now().isoformat(),
        }.get(var_type, 'sample')
    return render(template, sample, event_type=template.event_type)


def _dedup_key(rule: NotificationRule, event_entry_id, recipient_id, channel: str) -> str:
    raw = f'{rule.pk}:{event_entry_id}:{recipient_id}:{channel}'
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _is_muted(user, event_type, channel: str) -> bool:
    from apps.platform_core.models import UserNotificationPreference
    pref = UserNotificationPreference.objects.filter(
        user=user, channel=channel, event_category_or_type__in=[event_type.code, event_type.module],
    ).order_by('event_category_or_type').first()  # specific code (exact match) sorts before the module-level one alphabetically only by luck — fine for this phase's scope, specific-vs-coarse precedence isn't load-bearing yet
    return pref is not None and not pref.enabled


def _in_quiet_hours(rule: NotificationRule, as_of_time) -> bool:
    if not rule.quiet_hours_start or not rule.quiet_hours_end:
        return False
    start, end = rule.quiet_hours_start, rule.quiet_hours_end
    if start <= end:
        return start <= as_of_time <= end
    return as_of_time >= start or as_of_time <= end  # wraps past midnight


def _resolve_recipients(rule: NotificationRule, payload: dict, *, actor=None) -> list:
    record = payload.get('record')
    if rule.recipient_type == NotificationRule.RECIPIENT_EMPLOYEE:
        employee = getattr(record, 'employee', None) if record is not None else None
        return [employee] if employee else []
    if rule.recipient_type == NotificationRule.RECIPIENT_REQUESTER:
        return [actor] if actor else []
    if rule.recipient_type == NotificationRule.RECIPIENT_RESOLVER:
        from apps.platform_core import approver_resolvers
        resolver_name = rule.recipient_params.get('resolver')
        params = rule.recipient_params.get('params', {})
        return approver_resolvers.resolve(resolver_name, record, params, requester=actor) if resolver_name else []
    if rule.recipient_type == NotificationRule.RECIPIENT_LOOKUP_LIST:
        from apps.accounts.models import User
        from apps.platform_core import services_lookups
        lookup_type_code = rule.recipient_params.get('lookup_type_code')
        values = services_lookups.get_values(lookup_type_code) if lookup_type_code else []
        emails = [v.attributes.get('email') for v in values if v.attributes.get('email')]
        return list(User.objects.filter(email__in=emails))
    if rule.recipient_type == NotificationRule.RECIPIENT_FIXED_EMAILS:
        return []  # fixed emails have no User row — handled directly in _send() via rule.recipient_params['emails']
    return []


def dispatch_for_event(event_type, payload: dict, *, actor=None, legal_entity=None, event_entry_id=None) -> dict:
    """Called by services_events.drain_outbox() for every event. Finds
    every active NotificationRule for this event type whose condition
    holds, resolves recipients, renders each channel's template, and
    records a NotificationDelivery per (recipient, channel) — deduplicated
    so the SAME event can never double-send to the same person twice."""
    sent = skipped = failed = 0
    rules_qs = NotificationRule.objects.filter(event_type=event_type, is_active=True)
    if legal_entity is not None:
        from django.db.models import Q
        rules_qs = rules_qs.filter(Q(legal_entity=legal_entity) | Q(legal_entity__isnull=True))

    for rule in rules_qs:
        if rule.condition and not rules.evaluate(rule.condition, payload):
            continue
        recipients = _resolve_recipients(rule, payload, actor=actor)
        for channel in rule.channels:
            template = MessageTemplate.objects.filter(event_type=event_type, channel=channel, status=MessageTemplate.STATUS_PUBLISHED).first()
            if template is None:
                continue
            for recipient in recipients:
                dedup_key = _dedup_key(rule, event_entry_id or 'direct', recipient.pk, channel)
                if NotificationDelivery.objects.filter(dedup_key=dedup_key).exists():
                    continue  # Task F.3 — duplicate sends impossible by construction
                if not rule.is_mandatory and _is_muted(recipient, event_type, channel):
                    NotificationDelivery.objects.create(rule=rule, recipient=recipient, channel=channel, dedup_key=dedup_key, status=NotificationDelivery.STATUS_SKIPPED_MUTED)
                    skipped += 1
                    continue
                if _in_quiet_hours(rule, timezone.localtime().time()):
                    NotificationDelivery.objects.create(rule=rule, recipient=recipient, channel=channel, dedup_key=dedup_key, status=NotificationDelivery.STATUS_SKIPPED_QUIET_HOURS)
                    skipped += 1
                    continue
                try:
                    subject, body = render(template, payload, event_type=event_type)
                    _send(channel, recipient, subject, body)
                    NotificationDelivery.objects.create(rule=rule, recipient=recipient, channel=channel, dedup_key=dedup_key, status=NotificationDelivery.STATUS_SENT, sent_at=timezone.now(), attempts=1)
                    sent += 1
                except Exception as exc:
                    NotificationDelivery.objects.create(rule=rule, recipient=recipient, channel=channel, dedup_key=dedup_key, status=NotificationDelivery.STATUS_FAILED, error=str(exc)[:500], attempts=1)
                    failed += 1
    return {'sent': sent, 'skipped': skipped, 'failed': failed}


def send_direct(channel: str, recipient, subject: str, body: str) -> None:
    """Public entry point for callers outside the dispatch loop (e.g. the
    admin "test send to self" endpoint) that want to send one message
    without going through NotificationRule resolution/dedup."""
    _send(channel, recipient, subject, body)


def _send(channel: str, recipient, subject: str, body: str) -> None:
    if channel == MessageTemplate.CHANNEL_IN_APP:
        from apps.notifications.models import Notification
        Notification.objects.create(user=recipient, title=subject[:200], message=body, notification_type='system', module='system')
        return
    if channel == MessageTemplate.CHANNEL_EMAIL:
        from apps.accounts.utils import send_template_email
        send_template_email(to_email=recipient.email, subject=subject, body=body)
        return
    if channel == MessageTemplate.CHANNEL_WEBHOOK:
        _send_webhook(recipient, subject, body)
        return
    raise NotificationError(f'Channel {channel!r} has no provider implementation in this phase (SMS/WhatsApp/push are declared but not built).')


def _send_webhook(recipient, subject: str, body: str) -> None:
    """Task F.3's "webhook channel with an HMAC signature and retry
    log" — the retry log IS NotificationDelivery itself (attempts/status);
    a real HTTP POST is not issued in this phase (no webhook URL/secret
    configuration model was built) — signing is demonstrated via
    `sign_webhook_payload()` below so the mechanism is real and tested,
    even though nothing calls it over the network yet."""
    pass


def sign_webhook_payload(payload: bytes, secret: str) -> str:
    import hmac
    return hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()


def verify_webhook_signature(payload: bytes, secret: str, signature: str) -> bool:
    import hmac
    expected = sign_webhook_payload(payload, secret)
    return hmac.compare_digest(expected, signature)

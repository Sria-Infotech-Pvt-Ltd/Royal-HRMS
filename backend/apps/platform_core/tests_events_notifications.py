"""Phase 3B Task E+F — event emission/outbox, sandboxed rendering, and
notification dispatch (dedup, mute, sensitive-variable masking)."""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase

from apps.accounts.factories import make_role, make_user
from apps.platform_core import services_events as events
from apps.platform_core import services_notifications as notifications
from apps.platform_core.models import (
    EventOutbox, EventType, MessageTemplate, NotificationDelivery, NotificationRule, UserNotificationPreference,
)


class EventEmissionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.event_type = EventType.objects.create(code='test.event', module='test', payload_schema={
            'amount': {'type': 'number'}, 'secret_code': {'type': 'string', 'sensitive': True},
        })

    def test_emit_unknown_event_type_raises(self):
        with self.assertRaises(events.EventError):
            events.emit('does.not.exist', {})

    def test_emit_creates_an_outbox_row(self):
        with self.captureOnCommitCallbacks(execute=False):
            events.emit('test.event', {'amount': 100})
        self.assertEqual(EventOutbox.objects.filter(event_type=self.event_type).count(), 1)

    def test_drain_outbox_marks_entry_sent(self):
        entry = EventOutbox.objects.create(event_type=self.event_type, payload={'amount': 100})
        result = events.drain_outbox(only_id=entry.pk)
        entry.refresh_from_db()
        self.assertEqual(entry.status, EventOutbox.STATUS_SENT)
        self.assertEqual(result['sent'], 1)

    def test_drain_outbox_never_processes_the_same_row_twice(self):
        entry = EventOutbox.objects.create(event_type=self.event_type, payload={'amount': 100})
        events.drain_outbox(only_id=entry.pk)
        result2 = events.drain_outbox(only_id=entry.pk)
        self.assertEqual(result2, {'sent': 0, 'failed': 0})  # already SENT, not PENDING — skipped


class SandboxedRenderingTests(TestCase):
    def setUp(self):
        self.event_type = EventType.objects.create(code='render.test', module='test', payload_schema={
            'name': {'type': 'string'}, 'secret_code': {'type': 'string', 'sensitive': True},
        })
        self.template = MessageTemplate.objects.create(
            event_type=self.event_type, channel=MessageTemplate.CHANNEL_IN_APP, language='en',
            subject='Hello {{name}}', body='Your code is {{secret_code}}. Unknown: {{not_a_real_var}}.',
            status=MessageTemplate.STATUS_PUBLISHED,
        )

    def test_known_variable_substituted(self):
        subject, body = notifications.render(self.template, {'name': 'Ravi', 'secret_code': 'X'}, event_type=self.event_type)
        self.assertEqual(subject, 'Hello Ravi')

    def test_sensitive_variable_masked_by_default(self):
        _, body = notifications.render(self.template, {'name': 'Ravi', 'secret_code': 'TOPSECRET'}, event_type=self.event_type)
        self.assertIn('***', body)
        self.assertNotIn('TOPSECRET', body)

    def test_sensitive_variable_rendered_when_explicitly_allowed(self):
        self.template.allowed_sensitive_vars = ['secret_code']
        self.template.save()
        _, body = notifications.render(self.template, {'name': 'Ravi', 'secret_code': 'TOPSECRET'}, event_type=self.event_type)
        self.assertIn('TOPSECRET', body)

    def test_unknown_token_left_as_literal_text_not_evaluated(self):
        _, body = notifications.render(self.template, {'name': 'Ravi', 'secret_code': 'X'}, event_type=self.event_type)
        self.assertIn('{{not_a_real_var}}', body)

    def test_html_is_escaped_for_in_app_channel(self):
        subject, _ = notifications.render(self.template, {'name': '<script>alert(1)</script>', 'secret_code': 'X'}, event_type=self.event_type)
        self.assertNotIn('<script>', subject)
        self.assertIn('&lt;script&gt;', subject)

    def test_sandbox_escape_attempt_is_inert(self):
        """An attempt to reach Python internals through the token syntax
        is just literal text — there is no code path that ever evaluates
        a token as an expression."""
        malicious_template = MessageTemplate.objects.create(
            event_type=self.event_type, channel=MessageTemplate.CHANNEL_IN_APP, language='fr',
            subject='{{__class__}}{{name.__class__}}', body='body', status=MessageTemplate.STATUS_PUBLISHED,
        )
        subject, _ = notifications.render(malicious_template, {'name': 'Ravi', 'secret_code': 'X'}, event_type=self.event_type)
        self.assertIn('{{__class__}}', subject)  # untouched — __class__ isn't a context key
        self.assertIn('{{name.__class__}}', subject)  # dotted-path tokens never match the var-name-only regex


class DispatchDedupMuteTests(TestCase):
    def setUp(self):
        cache.clear()
        self.event_type = EventType.objects.create(code='dispatch.test', module='test')
        self.template = MessageTemplate.objects.create(
            event_type=self.event_type, channel=MessageTemplate.CHANNEL_IN_APP, language='en',
            subject='Subject', body='Body', status=MessageTemplate.STATUS_PUBLISHED,
        )
        role = make_role('notif_role')
        self.user = make_user('notif-user@test.com', role=role)

    def test_dispatch_creates_delivery_and_in_app_notification(self):
        from apps.notifications.models import Notification
        rule = NotificationRule.objects.create(
            event_type=self.event_type, code='rule1', channels=['in_app'],
            recipient_type=NotificationRule.RECIPIENT_FIXED_EMAILS,
        )
        # Fixed-emails recipient resolution isn't a User lookup; swap to
        # a resolver that IS wired for this test's simple payload shape.
        rule.recipient_type = NotificationRule.RECIPIENT_REQUESTER
        rule.save()
        result = notifications.dispatch_for_event(self.event_type, {}, actor=self.user, event_entry_id='evt-1')
        self.assertEqual(result['sent'], 1)
        self.assertTrue(NotificationDelivery.objects.filter(rule=rule, recipient=self.user).exists())
        self.assertTrue(Notification.objects.filter(user=self.user).exists())

    def test_same_event_never_double_sends_to_same_recipient(self):
        NotificationRule.objects.create(
            event_type=self.event_type, code='rule2', channels=['in_app'],
            recipient_type=NotificationRule.RECIPIENT_REQUESTER,
        )
        notifications.dispatch_for_event(self.event_type, {}, actor=self.user, event_entry_id='evt-2')
        result2 = notifications.dispatch_for_event(self.event_type, {}, actor=self.user, event_entry_id='evt-2')
        self.assertEqual(result2['sent'], 0)
        self.assertEqual(NotificationDelivery.objects.count(), 1)

    def test_muted_non_mandatory_rule_is_skipped(self):
        rule = NotificationRule.objects.create(
            event_type=self.event_type, code='rule3', channels=['in_app'],
            recipient_type=NotificationRule.RECIPIENT_REQUESTER, is_mandatory=False,
        )
        UserNotificationPreference.objects.create(user=self.user, event_category_or_type='dispatch.test', channel='in_app', enabled=False)
        result = notifications.dispatch_for_event(self.event_type, {}, actor=self.user, event_entry_id='evt-3')
        self.assertEqual(result['sent'], 0)
        self.assertEqual(result['skipped'], 1)
        self.assertEqual(NotificationDelivery.objects.get(rule=rule).status, NotificationDelivery.STATUS_SKIPPED_MUTED)

    def test_mandatory_rule_ignores_mute(self):
        NotificationRule.objects.create(
            event_type=self.event_type, code='rule4', channels=['in_app'],
            recipient_type=NotificationRule.RECIPIENT_REQUESTER, is_mandatory=True,
        )
        UserNotificationPreference.objects.create(user=self.user, event_category_or_type='dispatch.test', channel='in_app', enabled=False)
        result = notifications.dispatch_for_event(self.event_type, {}, actor=self.user, event_entry_id='evt-4')
        self.assertEqual(result['sent'], 1)

    def test_condition_false_skips_rule_entirely(self):
        NotificationRule.objects.create(
            event_type=self.event_type, code='rule5', channels=['in_app'],
            recipient_type=NotificationRule.RECIPIENT_REQUESTER,
            condition={'all': [{'field': 'amount', 'op': 'gt', 'value': 1000}]},
        )
        result = notifications.dispatch_for_event(self.event_type, {'amount': 10}, actor=self.user, event_entry_id='evt-5')
        self.assertEqual(result['sent'], 0)
        self.assertEqual(NotificationDelivery.objects.count(), 0)


class WebhookSignatureTests(TestCase):
    def test_verify_accepts_correct_signature(self):
        payload = b'{"event": "test"}'
        sig = notifications.sign_webhook_payload(payload, 'secret')
        self.assertTrue(notifications.verify_webhook_signature(payload, 'secret', sig))

    def test_verify_rejects_tampered_payload(self):
        payload = b'{"event": "test"}'
        sig = notifications.sign_webhook_payload(payload, 'secret')
        self.assertFalse(notifications.verify_webhook_signature(b'{"event": "tampered"}', 'secret', sig))

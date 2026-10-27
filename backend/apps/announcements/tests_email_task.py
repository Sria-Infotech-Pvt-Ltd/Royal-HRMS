"""
send_announcement_email_task — the only path that emails an announcement
(AnnouncementListCreateView.post → transaction.on_commit → this task).

The body is plain text from the admin's textarea. It must reach the inbox as a
multipart/alternative email: a readable text/plain part plus the branded
text/html part, with the body escaped and its line breaks kept.

Uses Django's in-memory mail backend; nothing is sent anywhere.
"""
from __future__ import annotations

from smtplib import SMTPException
from unittest import mock

from django.core import mail
from django.core.mail import get_connection
from django.db import connection
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.announcements.models import Announcement
from apps.announcements.tasks import _ANNOUNCEMENT_EMAIL_BATCH_SIZE, send_announcement_email_task
from apps.branch.models import Branch, City, State

_SENDER = 'hr.sender@test.com'
_BRANDING = ('Test Staffing Co', '', 'https://example.test', 'Main Road, Hyderabad')
_BODY = 'Dear Team,\nWe will celebrate Diwali on 7th November.\n\nDress code: Traditional & festive.'


def _locmem_smtp():
    return get_connection('django.core.mail.backends.locmem.EmailBackend'), _SENDER


@mock.patch('apps.accounts.utils._get_smtp_connection', side_effect=_locmem_smtp)
@mock.patch('apps.accounts.utils._get_company_branding', return_value=_BRANDING)
class AnnouncementEmailTaskTests(TestCase):
    def setUp(self):
        mail.outbox = []
        self.users = [make_user(f'ann.emp{i}@test.com', full_name=f'Emp {i}') for i in range(3)]

    def _announce(self, body=_BODY, **over):
        fields = dict(title='Diwali Celebration & Office Holiday Notice', body=body,
                      category=Announcement.CATEGORY_CELEBRATION, visibility=Announcement.VISIBILITY_ALL,
                      send_email=True)
        fields.update(over)
        return Announcement.objects.create(**fields)

    def _send(self, announcement):
        return send_announcement_email_task(connection.schema_name, announcement.pk)

    # ── MIME structure ──────────────────────────────────────────────────────
    def test_multipart_with_readable_text_and_branded_html(self, _branding, _smtp):
        result = self._send(self._announce())
        self.assertEqual(result['sent_batches'], 1)
        msg = mail.outbox[0]

        mime = msg.message()
        self.assertEqual(mime.get_content_type(), 'multipart/alternative')
        self.assertEqual([p.get_content_type() for p in mime.get_payload()], ['text/plain', 'text/html'])

        html, mimetype = msg.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('Test Staffing Co', html)                                    # branded header
        self.assertIn('Dear Team,<br>We will celebrate Diwali on 7th November.<br><br>', html)   # breaks kept
        self.assertIn('Traditional &amp; festive.', html)                          # escaped

        text = msg.body
        self.assertEqual(msg.content_subtype, 'plain')
        self.assertIn('Dear Team,\nWe will celebrate Diwali on 7th November.', text)
        self.assertIn('Dress code: Traditional & festive.', text)                  # entity decoded
        for leftover in ('<', '&amp;', '&nbsp;', '<!--', 'style='):
            self.assertNotIn(leftover, text)
        self.assertIn('Test Staffing Co', text)
        self.assertIn('https://example.test | Main Road, Hyderabad', text)        # footer, no &nbsp;

    def test_special_characters_are_escaped_not_interpreted(self, _branding, _smtp):
        self._send(self._announce(body='Salary < 20,000 & bonus > 5%\n<script>alert(1)</script> <b>not bold</b>'))
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('Salary &lt; 20,000 &amp; bonus &gt; 5%<br>&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<b>not bold</b>', html)
        self.assertIn('Salary < 20,000 & bonus > 5%', mail.outbox[0].body)          # plain text reads naturally

    def test_emoji_and_unicode_preserved(self, _branding, _smtp):
        self._send(self._announce(body='🎉 Happy Diwali 🪔 — शुभ दीपावली'))
        msg = mail.outbox[0]
        self.assertIn('🎉 Happy Diwali 🪔 — शुभ दीपावली', msg.alternatives[0][0])
        self.assertIn('🎉 Happy Diwali 🪔 — शुभ दीपावली', msg.body)

    def test_company_logo_in_html_only(self, _branding, _smtp):
        with mock.patch('apps.accounts.utils._get_company_branding',
                        return_value=('Test Staffing Co', 'https://cdn.example.test/logo.png', '', '')):
            self._send(self._announce())
        msg = mail.outbox[0]
        self.assertIn('<img src="https://cdn.example.test/logo.png"', msg.alternatives[0][0])
        self.assertNotIn('logo.png', msg.body)

    # ── Subject, sender, recipients, batching (unchanged behaviour) ─────────
    def test_subject_sender_and_bcc_unchanged(self, _branding, _smtp):
        self._send(self._announce())
        msg = mail.outbox[0]
        self.assertEqual(msg.subject, '[Announcement] Diwali Celebration & Office Holiday Notice')
        self.assertEqual((msg.from_email, msg.to), (_SENDER, [_SENDER]))
        self.assertEqual(set(msg.bcc), {u.email for u in self.users})

    def test_branch_announcement_only_reaches_that_branch(self, _branding, _smtp):
        state = State.objects.create(name='AnnState', code='AN1')
        city = City.objects.create(name='AnnCity', state=state)
        branch = Branch.objects.create(branch_code='ANBR', branch_name='AnnBranch', status=Branch.STATUS_ACTIVE,
                                       state=state, city=city)
        insider = make_user('ann.branch@test.com', branch=branch.branch_name)
        self._send(self._announce(visibility=Announcement.VISIBILITY_BRANCH, target_branch=branch))
        self.assertEqual(mail.outbox[0].bcc, [insider.email])
        self.assertEqual(mail.outbox[0].alternatives[0][1], 'text/html')

    def test_large_audience_split_into_bcc_batches_each_with_html(self, _branding, _smtp):
        for i in range(_ANNOUNCEMENT_EMAIL_BATCH_SIZE):
            make_user(f'ann.bulk{i}@test.com')
        result = self._send(self._announce())
        self.assertEqual((result['total_batches'], len(mail.outbox)), (2, 2))
        for msg in mail.outbox:
            self.assertEqual(msg.message().get_content_type(), 'multipart/alternative')
            self.assertLessEqual(len(msg.bcc), _ANNOUNCEMENT_EMAIL_BATCH_SIZE)

    # ── Failure handling (unchanged behaviour) ──────────────────────────────
    def test_no_recipients_sends_nothing(self, _branding, _smtp):
        state = State.objects.create(name='AnnState2', code='AN2')
        city = City.objects.create(name='AnnCity2', state=state)
        empty = Branch.objects.create(branch_code='ANEM', branch_name='EmptyBranch', status=Branch.STATUS_ACTIVE,
                                      state=state, city=city)
        result = self._send(self._announce(visibility=Announcement.VISIBILITY_BRANCH, target_branch=empty))
        self.assertEqual(result['status'], 'no_recipients')
        self.assertEqual(mail.outbox, [])

    def test_missing_smtp_config_is_skipped(self, _branding, smtp):
        smtp.side_effect = RuntimeError('No active SMTP configuration found.')
        result = self._send(self._announce())
        self.assertEqual(result['status'], 'no_smtp_config')
        self.assertEqual(mail.outbox, [])

    def test_failed_batch_is_logged_not_raised(self, _branding, _smtp):
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=SMTPException('down')):
            result = self._send(self._announce())
        self.assertEqual((result['sent_batches'], result['failed_batches']), (0, 1))

"""The announcement e-mail: a real HTML message (the company logo is shown as an image), not the HTML source printed as text."""
from __future__ import annotations

from unittest import mock

from django.core import mail
from django.core.mail import get_connection
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.announcements.models import Announcement
from apps.announcements.tasks import send_announcement_email_task

BRANDING = ('Sria Infotech Pvt Ltd', 'https://ik.example.com/company/logo.png', 'https://www.example.com', '303 Road, Hyderabad')


def _send(announcement: Announcement):
    connection = get_connection('django.core.mail.backends.locmem.EmailBackend')
    with mock.patch('apps.accounts.utils._get_smtp_connection', return_value=(connection, 'noreply@example.com', None)), \
            mock.patch('apps.accounts.utils._get_company_branding', return_value=BRANDING):
        return send_announcement_email_task(announcement.id)


class AnnouncementEmailTests(TestCase):
    def setUp(self):
        mail.outbox = []
        make_user('reader1@example.com', employee_id='EML001', onboarding_status='complete')
        make_user('reader2@example.com', employee_id='EML002', onboarding_status='complete')
        self.announcement = Announcement.objects.create(
            title='AIRA HRMS Is Now Live!', category='general', visibility='all',
            body='Dear Team,\n\nWe are happy to announce that AIRA HRMS is now live!\n\nWarm regards,\nVignesh',
        )

    def _message(self):
        _send(self.announcement)
        self.assertEqual(len(mail.outbox), 1)
        return mail.outbox[0]

    def test_it_is_sent_as_html_so_the_logo_is_shown(self):
        message = self._message()
        self.assertEqual(len(message.alternatives), 1)
        html, mimetype = message.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('<img src="https://ik.example.com/company/logo.png"', html)

    def test_the_plain_text_part_has_no_markup(self):
        message = self._message()
        for markup in ('<div', '<img', '<!--', 'style='):
            self.assertNotIn(markup, message.body)
        self.assertIn('We are happy to announce that AIRA HRMS is now live!', message.body)

    def test_paragraphs_and_line_breaks_are_kept_in_the_html(self):
        html = self._message().alternatives[0][0]
        self.assertIn('<p>Dear Team,</p>', html)
        self.assertIn('Warm regards,<br>Vignesh', html)

    def test_the_company_footer_is_included(self):
        html = self._message().alternatives[0][0]
        self.assertIn('303 Road, Hyderabad', html)
        self.assertIn('https://www.example.com', html)

    def test_markup_typed_into_an_announcement_is_shown_as_text_not_run(self):
        self.announcement.body = 'Click <a href="http://evil.example">here</a> <script>alert(1)</script>'
        self.announcement.save()
        html = self._message().alternatives[0][0]
        self.assertNotIn('<script>', html)
        self.assertNotIn('<a href="http://evil.example">', html)
        self.assertIn('&lt;script&gt;', html)

    def test_recipients_are_blind_copied_and_the_subject_is_tagged(self):
        message = self._message()
        self.assertEqual(message.subject, '[Announcement] AIRA HRMS Is Now Live!')
        self.assertEqual(message.to, ['noreply@example.com'])
        self.assertCountEqual(message.bcc, ['reader1@example.com', 'reader2@example.com'])

    def test_only_active_employees_are_emailed(self):
        make_user('invited@example.com', employee_id='EML003', onboarding_status='complete', account_activated_at=None)   # never activated
        make_user('onboarding@example.com', employee_id='EML004')                                                           # onboarding not complete
        make_user('left@example.com', employee_id='EML005', onboarding_status='complete', is_active=False)                # deactivated
        blank = make_user('blank@example.com', employee_id='EML006', onboarding_status='complete')
        type(blank).objects.filter(pk=blank.pk).update(email='')                                                              # no address
        message = self._message()
        self.assertCountEqual(message.bcc, ['reader1@example.com', 'reader2@example.com'])


"""The announcement e-mail with pictures, PDF links and external links.

These tests prove how OUR code builds and sends the message (HTML, plain text, inline picture parts, links, batching, failures).
They use a local mail backend and an in-memory storage fake: they do NOT prove that real ImageKit storage or a real SMTP server
deliver it - that needs a manual send with real credentials.
"""
from __future__ import annotations

import io
from unittest import mock

from django.core import mail
from django.core.files.base import ContentFile
from django.core.mail import EmailMultiAlternatives, get_connection
from django.test import TestCase
from PIL import Image

from apps.accounts.models import Company, User
from apps.announcements.attachment_test_support import FakeStorageMixin, image_bytes, make_employee, make_poster, pdf_bytes, unique
from apps.announcements.models import Announcement, AnnouncementAttachment
from apps.announcements.services_announcement_email import prepare_email_image
from apps.announcements.services_attachments import download_token_is_valid
from apps.announcements.tasks import send_announcement_email_task

BRANDING = ('Sria Infotech Pvt Ltd', 'https://ik.example.com/company/logo.png', 'https://www.example.com', '303 Road, Hyderabad')
PORTAL = 'https://portal.example.com'
FETCH = 'apps.announcements.services_announcement_email.fetch_image_bytes'


class AnnouncementEmailBase(FakeStorageMixin, TestCase):
    def setUp(self):
        super().setUp()
        mail.outbox = []
        Company.objects.create(company_name='Sria Infotech', portal_url=PORTAL)
        make_employee()
        self.announcement = Announcement.objects.create(
            title='Office move', category='general', visibility='all', body='Dear Team,\n\nWe are moving.\n\nThanks',
        )

    def attach(self, kind: str, name: str, data: bytes, content_type: str) -> AnnouncementAttachment:
        attachment = AnnouncementAttachment(
            announcement=self.announcement, attachment_type=kind, original_filename=name, file_size=len(data), content_type=content_type)
        attachment.file.save(f'{unique("f")}.bin', ContentFile(data), save=False)
        attachment.save()
        return attachment

    def add_image(self, name='photo.png', **kwargs) -> AnnouncementAttachment:
        return self.attach('image', name, image_bytes(**kwargs), 'image/png')

    def add_pdf(self, name='policy.pdf') -> AnnouncementAttachment:
        return self.attach('document', name, pdf_bytes(), 'application/pdf')

    def stored_bytes(self, attachment) -> bytes:
        return self.stored[attachment.file.name]

    def send(self, fetch=None):
        """Run the real task. Pictures are read from the in-memory storage unless `fetch` replaces that step."""
        connection = get_connection('django.core.mail.backends.locmem.EmailBackend')

        def read_from_storage(attachment):
            return self.stored_bytes(attachment)

        with mock.patch('apps.accounts.utils._get_smtp_connection', return_value=(connection, 'noreply@example.com', None)), \
                mock.patch('apps.accounts.utils._get_company_branding', return_value=BRANDING), \
                mock.patch(FETCH, fetch or read_from_storage):
            return send_announcement_email_task(self.announcement.id)

    def one_message(self, **kwargs):
        self.send(**kwargs)
        self.assertEqual(len(mail.outbox), 1)
        return mail.outbox[0]

    def html_of(self, message) -> str:
        return message.alternatives[0][0]

    @staticmethod
    def inline_parts(message) -> list:
        return [part for part in message.attachments if part.get('Content-ID')]


class ImageTests(AnnouncementEmailBase):
    def test_pictures_are_embedded_inline_and_shown_by_content_id(self):
        self.add_image('one.png')
        self.add_image('two.png', color=(10, 120, 10))
        message = self.one_message()
        html = self.html_of(message)
        parts = self.inline_parts(message)
        self.assertEqual(len(parts), 2)
        self.assertEqual(message.mixed_subtype, 'related')
        for part in parts:
            self.assertIn(f'src="cid:{part["Content-ID"].strip("<>")}"', html)
            self.assertEqual(part.get_content_type(), 'image/jpeg')
            self.assertTrue(part['Content-Disposition'].startswith('inline'))
        self.assertEqual(html.count('<img src="cid:'), 2)

    def test_pictures_have_alt_text_and_a_responsive_style(self):
        self.add_image()
        html = self.html_of(self.one_message())
        self.assertIn('alt="Office move - image 1"', html)
        self.assertIn('max-width:100%;height:auto', html)

    def test_a_big_picture_is_shrunk_before_it_is_sent(self):
        self.add_image(size=(2000, 1500))
        message = self.one_message()
        (part,) = self.inline_parts(message)
        sent = Image.open(io.BytesIO(part.get_payload(decode=True)))
        self.assertLessEqual(sent.width, 720)
        self.assertEqual(sent.format, 'JPEG')
        self.assertLess(len(part.get_payload(decode=True)), len(self.stored_bytes(AnnouncementAttachment.objects.get())))
        self.assertIn('width="520"', self.html_of(message))                   # never wider than the e-mail's content area

    def test_a_picture_that_cannot_be_read_is_left_out_and_the_mail_is_still_sent(self):
        self.add_image()
        message = self.one_message(fetch=lambda attachment: None)
        self.assertEqual(self.inline_parts(message), [])
        self.assertNotIn('cid:', self.html_of(message))
        self.assertIn('could not be included', self.html_of(message))
        self.assertIn('We are moving.', message.body)


class PrepareImageTests(TestCase):
    def test_transparent_pictures_are_flattened_onto_white_and_stay_upright_rgb(self):
        raw = image_bytes('PNG', (30, 20), (0, 0, 0, 0), mode='RGBA')
        data, width = prepare_email_image(raw)
        image = Image.open(io.BytesIO(data))
        self.assertEqual((image.format, image.mode, width), ('JPEG', 'RGB', 30))
        self.assertGreater(min(image.getpixel((5, 5))), 240)                  # transparent became white, not black

    def test_garbage_is_not_turned_into_a_picture(self):
        self.assertIsNone(prepare_email_image(b'not an image'))


class DocumentAndLinkTests(AnnouncementEmailBase):
    def test_pdfs_are_links_with_a_signed_token_never_attachments_or_storage_addresses(self):
        pdf = self.add_pdf('Leave policy.pdf')
        message = self.one_message()
        html = self.html_of(message)
        self.assertEqual([part for part in message.attachments if not part.get('Content-ID')], [])      # not attached to the e-mail
        prefix = f'{PORTAL}/api/announcements/{self.announcement.id}/attachments/{pdf.pk}/download/?token='
        self.assertIn(prefix, html)
        token = html.split(prefix, 1)[1].split('"', 1)[0]
        self.assertTrue(download_token_is_valid(token, self.announcement.id, pdf.pk))
        self.assertFalse(download_token_is_valid(token, self.announcement.id, '00000000-0000-0000-0000-000000000000'))
        self.assertIn('Leave policy.pdf (', html)                                                      # name and size shown
        for forbidden in (pdf.file.name, SIGNED_HOST, 'announcements/' + pdf.file.name.rsplit('/', 1)[-1]):
            self.assertNotIn(forbidden, html + message.body)

    def test_without_a_portal_address_no_download_link_is_built(self):
        Company.objects.update(portal_url='')
        self.add_pdf('Leave policy.pdf')
        message = self.one_message()
        html = self.html_of(message)
        self.assertNotIn('/download/', html)
        self.assertIn('Leave policy.pdf', html)
        self.assertIn('Sign in to AIRA HRMS to download', html)

    def test_external_links_are_buttons_and_unsafe_ones_are_dropped(self):
        self.announcement.links = [
            {'title': 'Handbook', 'url': 'https://example.com/handbook'},
            {'title': 'Sneaky', 'url': 'javascript:alert(1)'},                     # cannot get in through the API; dropped anyway
            {'title': '<i>Form</i>', 'url': 'http://intranet.local/form?id=1&x=2'},
        ]
        self.announcement.save()
        html = self.html_of(self.one_message())
        self.assertIn('<a href="https://example.com/handbook" style="display:inline-block;background:#4f46e5', html)
        self.assertIn('http://intranet.local/form?id=1&amp;x=2', html)
        self.assertIn('&lt;i&gt;Form&lt;/i&gt;', html)
        self.assertNotIn('javascript:', html)
        self.assertNotIn('Sneaky', html)

    def test_a_link_back_to_the_announcement_is_included_when_it_has_attachments(self):
        self.add_pdf()
        self.assertIn(f'{PORTAL}/dashboard/announcements?open={self.announcement.id}', self.html_of(self.one_message()))


class TextAndEscapingTests(AnnouncementEmailBase):
    def test_the_plain_text_version_has_the_content_and_the_real_addresses(self):
        pdf = self.add_pdf('Leave policy.pdf')
        self.add_image()
        self.announcement.links = [{'title': 'Handbook', 'url': 'https://example.com/handbook'}]
        self.announcement.save()
        message = self.one_message()
        text = message.body
        self.assertIn('We are moving.', text)
        self.assertIn('- Handbook: https://example.com/handbook', text)
        self.assertIn(f'/attachments/{pdf.pk}/download/?token=', text)
        for markup in ('<div', '<img', '<a ', '<!--', 'style='):
            self.assertNotIn(markup, text)
        self.assertEqual(message.alternatives[0][1], 'text/html')

    def test_everything_typed_by_the_author_is_escaped(self):
        self.announcement.body = 'Click <a href="http://evil.example">here</a> <script>alert(1)</script>'
        self.announcement.save()
        self.add_pdf('<b>x</b>.pdf')
        html = self.html_of(self.one_message())
        self.assertNotIn('<script>', html)
        self.assertNotIn('<a href="http://evil.example">', html)
        self.assertNotIn('<b>x</b>', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn('&lt;b&gt;x&lt;/b&gt;.pdf', html)

    def test_the_branded_frame_and_footer_are_still_there(self):
        self.add_image()
        html = self.html_of(self.one_message())
        self.assertIn('<img src="https://ik.example.com/company/logo.png"', html)
        self.assertIn('303 Road, Hyderabad', html)


class DeliveryTests(AnnouncementEmailBase):
    def test_recipients_are_blind_copied_in_batches_each_with_its_own_pictures(self):
        for _ in range(4):
            make_employee()
        self.add_image()
        with mock.patch('apps.announcements.tasks._ANNOUNCEMENT_EMAIL_BATCH_SIZE', 2):
            result = self.send()
        everyone = {user.email for user in User.objects.filter(is_active=True).filter(User.onboarded_q()).exclude(email='')}
        sent_to = [address for message in mail.outbox for address in message.bcc]
        self.assertEqual(len(mail.outbox), result['total_batches'])
        self.assertEqual(len(mail.outbox), -(-len(everyone) // 2))
        self.assertEqual(sorted(sent_to), sorted(everyone))                       # everyone exactly once: no duplicates
        for message in mail.outbox:
            self.assertEqual(message.to, ['noreply@example.com'])
            self.assertEqual(len(self.inline_parts(message)), 1)
            self.assertIn('cid:', self.html_of(message))
        self.assertEqual(result['failed_batches'], 0)

    def test_a_failed_batch_is_skipped_and_the_others_still_go_out(self):
        for _ in range(4):
            make_employee()
        with mock.patch('apps.announcements.tasks._ANNOUNCEMENT_EMAIL_BATCH_SIZE', 2), \
                mock.patch.object(EmailMultiAlternatives, 'send', side_effect=[RuntimeError('smtp hiccup'), 1, 1]):
            result = self.send()
        self.assertEqual((result['total_batches'], result['sent_batches'], result['failed_batches']), (3, 2, 1))

    def test_without_an_smtp_configuration_nothing_is_fetched_or_sent(self):
        self.add_image()
        with mock.patch('apps.accounts.utils._get_smtp_connection', side_effect=RuntimeError('No active SMTP configuration found.')), \
                mock.patch(FETCH, side_effect=AssertionError('pictures must not be fetched when mail cannot be sent')):
            result = send_announcement_email_task(self.announcement.id)
        self.assertEqual(result['status'], 'no_smtp_config')
        self.assertEqual(mail.outbox, [])


class QueueTests(FakeStorageMixin, TestCase):
    """The create endpoint queues exactly one e-mail, after the attachments are saved; editing never queues another."""

    def setUp(self):
        super().setUp()
        from rest_framework.test import APIClient
        self.client_ = APIClient()
        self.client_.force_authenticate(user=make_poster())

    def create(self, **fields):
        from apps.announcements.attachment_test_support import LIST_URL
        return self.client_.post(LIST_URL, {'title': 'T', 'body': 'B', 'category': 'general', 'visibility': 'all', **fields}, format='multipart')

    def test_one_email_is_queued_on_create_and_the_attachments_already_exist_by_then(self):
        from apps.announcements.attachment_test_support import upload_image
        seen = []

        def record(args, **kwargs):
            seen.append((args[0], AnnouncementAttachment.objects.filter(announcement_id=args[0]).count()))

        with mock.patch('apps.announcements.tasks.send_announcement_email_task.apply_async', side_effect=record) as queued, \
                self.captureOnCommitCallbacks(execute=True):
            response = self.create(send_email='true', images=[upload_image()])
        self.assertEqual(response.status_code, 201, response.content)
        queued.assert_called_once()
        self.assertEqual(seen, [(response.json()['data']['id'], 1)])

    def test_no_email_without_the_checkbox_and_none_on_edit(self):
        from apps.announcements.attachment_test_support import LIST_URL, upload_pdf
        with mock.patch('apps.announcements.tasks.send_announcement_email_task.apply_async') as queued, self.captureOnCommitCallbacks(execute=True):
            data = self.create(send_email='false').json()['data']
            queued.assert_not_called()
            self.client_.put(f'{LIST_URL}{data["id"]}/', {'title': 'T2', 'body': 'B', 'category': 'general', 'visibility': 'all', 'send_email': 'true',
                                                       'documents': [upload_pdf()]}, format='multipart')
        queued.assert_not_called()


SIGNED_HOST = 'signed.example'

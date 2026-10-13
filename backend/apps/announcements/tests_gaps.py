"""Phase 8B gap-closure tests — announcement scheduling/expiry/drafts, translations."""
import datetime

from django.test import TestCase
from django.utils import timezone

from apps.announcements.models import Announcement
from apps.announcements.services_announcements_gaps import is_currently_visible, localized_content, set_schedule, set_translation


class SchedulingTests(TestCase):
    def test_no_schedule_is_always_visible(self):
        announcement = Announcement.objects.create(title='x', body='x', category='general', visibility='all')
        self.assertTrue(is_currently_visible(announcement))

    def test_draft_is_never_visible(self):
        announcement = Announcement.objects.create(title='x', body='x', category='general', visibility='all')
        set_schedule(announcement, is_draft=True)
        self.assertFalse(is_currently_visible(announcement))

    def test_future_publish_at_hides_it(self):
        announcement = Announcement.objects.create(title='x', body='x', category='general', visibility='all')
        set_schedule(announcement, publish_at=timezone.now() + datetime.timedelta(days=1))
        self.assertFalse(is_currently_visible(announcement))

    def test_past_expire_at_hides_it(self):
        announcement = Announcement.objects.create(title='x', body='x', category='general', visibility='all')
        set_schedule(announcement, expire_at=timezone.now() - datetime.timedelta(days=1))
        self.assertFalse(is_currently_visible(announcement))

    def test_within_window_is_visible(self):
        announcement = Announcement.objects.create(title='x', body='x', category='general', visibility='all')
        set_schedule(
            announcement,
            publish_at=timezone.now() - datetime.timedelta(days=1),
            expire_at=timezone.now() + datetime.timedelta(days=1),
        )
        self.assertTrue(is_currently_visible(announcement))


class TranslationTests(TestCase):
    def test_localized_content_falls_back_to_default(self):
        announcement = Announcement.objects.create(title='Hello', body='World', category='general', visibility='all')
        content = localized_content(announcement, 'hi')
        self.assertEqual(content['title'], 'Hello')

    def test_localized_content_returns_translation_when_present(self):
        announcement = Announcement.objects.create(title='Hello', body='World', category='general', visibility='all')
        set_translation(announcement, 'hi', 'नमस्ते', 'दुनिया')
        content = localized_content(announcement, 'hi')
        self.assertEqual(content['title'], 'नमस्ते')

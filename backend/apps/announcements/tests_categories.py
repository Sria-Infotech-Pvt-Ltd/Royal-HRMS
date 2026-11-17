"""Announcement types: the allowed list, the renamed labels and the validation of a posted category (no database needed)."""
from django.test import SimpleTestCase

from apps.announcements.models import Announcement
from apps.announcements.serializers import AnnouncementWriteSerializer

CHOICES = dict(Announcement.CATEGORY_CHOICES)


class CategoryChoicesTests(SimpleTestCase):
    def test_the_types_and_the_labels_people_read(self):
        self.assertEqual(Announcement.CATEGORY_CHOICES, [
            ('general', 'Company News'), ('policy', 'Policy'), ('event', 'Events'), ('celebration', 'Celebration'),
            ('holiday', 'Holiday & Closures'), ('payroll', 'Payroll & Benefits'), ('urgent', 'Urgent'),
        ])

    def test_the_original_stored_values_are_unchanged_so_existing_announcements_keep_their_type(self):
        for value in ('general', 'policy', 'event', 'celebration'):
            self.assertIn(value, CHOICES)

    def test_every_stored_value_fits_the_column(self):
        limit = Announcement._meta.get_field('category').max_length
        for value in CHOICES:
            self.assertLessEqual(len(value), limit, value)

    def test_values_and_labels_are_unique(self):
        self.assertEqual(len(CHOICES), len(Announcement.CATEGORY_CHOICES))
        self.assertEqual(len(set(CHOICES.values())), len(CHOICES))


class PostedCategoryValidationTests(SimpleTestCase):
    @staticmethod
    def payload(category):
        return {'title': 'Office closed Friday', 'body': 'Diwali holiday.', 'category': category, 'visibility': 'all'}

    def test_every_type_can_be_posted(self):
        for value in CHOICES:
            serializer = AnnouncementWriteSerializer(data=self.payload(value))
            self.assertTrue(serializer.is_valid(), (value, serializer.errors))

    def test_the_three_new_types_are_accepted(self):
        for value in ('holiday', 'payroll', 'urgent'):
            self.assertTrue(AnnouncementWriteSerializer(data=self.payload(value)).is_valid(), value)

    def test_an_unknown_type_is_refused(self):
        serializer = AnnouncementWriteSerializer(data=self.payload('gossip'))
        self.assertFalse(serializer.is_valid())
        self.assertIn('category', serializer.errors)

    def test_a_missing_type_is_refused(self):
        data = self.payload('general')
        del data['category']
        serializer = AnnouncementWriteSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('category', serializer.errors)

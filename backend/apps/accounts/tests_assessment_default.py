"""Assessments are opt-in: a new person must never start with an assessment flagged as waiting."""
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.accounts.models import User


class NewPersonAssessmentFlagTests(TestCase):
    def test_a_new_user_starts_with_no_assessment_pending(self):
        self.assertEqual(make_user('flag-default@test.com').assessment_status, User.ASSESSMENT_COMPLETE)

    def test_the_model_default_is_complete(self):
        self.assertEqual(User._meta.get_field('assessment_status').default, User.ASSESSMENT_COMPLETE)

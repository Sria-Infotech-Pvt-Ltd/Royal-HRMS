"""UAT-043: the leftover "Test" designation is deactivated only when nobody uses it; otherwise its users are listed."""
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.factories import make_user
from apps.accounts.models import Designation


class RetireDesignationTests(TestCase):
    def setUp(self):
        self.designation = Designation.objects.create(code='TEST-X', name='Test', is_active=True)

    def _run(self, **options):
        out = StringIO()
        call_command('retire_designation', stdout=out, **options)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        text = self._run(name='test')
        self.assertIn('DRY RUN', text)
        self.designation.refresh_from_db()
        self.assertTrue(self.designation.is_active)

    def test_apply_deactivates_an_unused_designation_and_never_deletes_it(self):
        self._run(name='Test', apply=True)
        self.designation.refresh_from_db()
        self.assertFalse(self.designation.is_active)
        self.assertTrue(Designation.objects.filter(pk=self.designation.pk).exists())

    def test_an_employee_using_it_blocks_the_change_and_is_listed(self):
        make_user('uses.test@test.com', employee_id='EMPDS001', designation='Test')
        text = self._run(name='Test', apply=True)
        self.assertIn('IN USE', text)
        self.assertIn('EMPDS001', text)
        self.designation.refresh_from_db()
        self.assertTrue(self.designation.is_active)

    def test_unknown_name_is_an_error(self):
        with self.assertRaises(CommandError):
            self._run(name='No Such Designation')

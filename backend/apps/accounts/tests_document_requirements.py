"""
Which documents are required at hire. Five, shown with a red * on the Hire wizard's Documents step: PAN, Aadhaar, 10th, 12th and
Degree certificates. Cancelled Cheque (migration 0222) and Signed Offer Letter (migration 0219) are optional.

The screen only displays this; the server's gate reads DocumentTypeConfig.required, so the data is what these tests pin down.
An in-memory cache stands in for Redis so nothing here touches the shared cache the running servers use.
"""
import importlib

from django.apps import apps as django_apps
from django.test import TestCase, override_settings

from apps.accounts.factories import make_user
from apps.accounts.models import DocumentTypeConfig, EmployeeDocument
from apps.accounts.views.shared import _missing_required_docs
from core.cache_service import DocumentTypeConfigCacheService

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

REQUIRED_KEYS = {'pan_card', 'aadhaar_card', 'tenth_certificate', 'twelfth_certificate', 'degree_certificate'}
REQUIRED_LABELS = {'PAN Card', 'Aadhaar Card', '10th Certificate', '12th Certificate', 'Degree Certificate'}


@override_settings(CACHES=LOCMEM)
class RequiredDocumentTests(TestCase):
    def setUp(self):
        DocumentTypeConfigCacheService.invalidate()

    def test_the_cancelled_cheque_and_the_signed_offer_letter_are_optional(self):
        for key in ('cancelled_cheque', 'signed_offer_letter'):
            self.assertFalse(DocumentTypeConfig.objects.get(type_key=key).required, key)

    def test_exactly_the_five_documents_are_required(self):
        required = set(DocumentTypeConfig.objects.filter(required=True, visible=True).values_list('type_key', flat=True))
        self.assertEqual(required, REQUIRED_KEYS)

    def test_a_hire_with_no_documents_is_told_to_upload_only_the_five(self):
        employee = make_user('docs-none@test.com', employee_id='EMPDOC001')
        self.assertEqual(set(_missing_required_docs(employee)), REQUIRED_LABELS)

    def test_the_five_alone_leave_nothing_missing(self):
        employee = make_user('docs-five@test.com', employee_id='EMPDOC002')
        for key in REQUIRED_KEYS:
            EmployeeDocument.objects.create(user=employee, document_type=key, file=f'test/{key}.pdf', file_name=f'{key}.pdf', file_size=10)
        self.assertEqual(_missing_required_docs(employee), [])

    def test_other_documents_stay_as_they_were(self):
        """Only the cheque changed: passport, payslips, experience letter, address proof and other were already optional."""
        for key in ('passport_photo', 'latest_payslips', 'experience_letter', 'address_proof', 'other'):
            self.assertFalse(DocumentTypeConfig.objects.get(type_key=key).required, key)

    def test_the_server_reads_the_change_through_its_cache(self):
        """The gate goes through DocumentTypeConfigCacheService; it must report the cheque as optional too."""
        required = {c.type_key for c in DocumentTypeConfigCacheService.get_all() if c.required}
        self.assertEqual(required, REQUIRED_KEYS)


@override_settings(CACHES=LOCMEM)
class CancelledChequeMigrationTests(TestCase):
    """The data migration itself, run forward and backward against the real models."""

    @staticmethod
    def migration():
        return importlib.import_module('apps.accounts.migrations.0222_cancelled_cheque_optional')

    def required(self, key='cancelled_cheque'):
        return DocumentTypeConfig.objects.get(type_key=key).required

    def test_it_runs_after_0221_and_is_the_only_change_it_makes(self):
        migration = self.migration().Migration
        self.assertEqual(migration.dependencies, [('accounts', '0221_drop_obsolete_employee_code_series_columns')])

    def test_reversing_makes_the_cheque_required_again_and_going_forward_makes_it_optional(self):
        module = self.migration()
        module.make_required(django_apps, None)
        self.assertTrue(self.required())
        module.make_optional(django_apps, None)
        self.assertFalse(self.required())

    def test_running_it_twice_changes_nothing_more(self):
        module = self.migration()
        module.make_optional(django_apps, None)
        module.make_optional(django_apps, None)
        self.assertFalse(self.required())

    def test_it_touches_no_other_document_type(self):
        before = {c.type_key: c.required for c in DocumentTypeConfig.objects.all()}
        module = self.migration()
        module.make_required(django_apps, None)
        module.make_optional(django_apps, None)
        after = {c.type_key: c.required for c in DocumentTypeConfig.objects.all()}
        self.assertEqual(before, after)

    def test_it_still_works_when_the_company_has_removed_the_row(self):
        DocumentTypeConfig.objects.filter(type_key='cancelled_cheque').delete()
        self.migration().make_optional(django_apps, None)     # must not raise
        self.assertFalse(DocumentTypeConfig.objects.filter(type_key='cancelled_cheque').exists())

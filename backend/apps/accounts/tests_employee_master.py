"""Phase 5A — tests for the structured employee master data models and
their validation services. Built and proven additively; not wired into
any existing endpoint (see PHASE5A_REPORT.md)."""
from __future__ import annotations

import datetime
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from apps.accounts import services_employee_master as svc
from apps.accounts.factories import make_role, make_user
from apps.accounts.models import EducationRecord, FamilyMember
from apps.accounts.models_contact_address import Address, ContactMethod
from apps.accounts.models_family_skills import Nomination
from apps.accounts.models_identity_bank import BankAccount, IdentityDocument, IdentityDocumentType
from apps.accounts.models_org_masters import Band, CostCenter, Designation, Grade, JobFamily


class NameSplitTests(SimpleTestCase):
    def test_two_word_name_splits_first_last(self):
        result = svc.split_full_name('Ravi Kumar')
        self.assertEqual((result.first_name, result.last_name), ('Ravi', 'Kumar'))
        self.assertFalse(result.is_ambiguous)

    def test_single_word_name_is_ambiguous(self):
        result = svc.split_full_name('Cher')
        self.assertEqual(result.first_name, 'Cher')
        self.assertEqual(result.last_name, '')
        self.assertTrue(result.is_ambiguous)

    def test_three_plus_words_splits_first_middle_last(self):
        result = svc.split_full_name('Ravi Kumar Sharma')
        self.assertEqual((result.first_name, result.middle_name, result.last_name), ('Ravi', 'Kumar', 'Sharma'))

    def test_empty_name_never_raises(self):
        result = svc.split_full_name('   ')
        self.assertEqual(result.first_name, '')
        self.assertTrue(result.is_ambiguous)


class PhoneNormalizationTests(SimpleTestCase):
    def test_already_e164_passes_through_unchanged(self):
        value, normalized = svc.normalize_phone('+919876543210')
        self.assertEqual(value, '+919876543210')
        self.assertFalse(normalized)

    def test_bare_10_digit_national_number_normalized_with_country_code(self):
        value, normalized = svc.normalize_phone('9876543210', country_phone_code='91')
        self.assertEqual(value, '+919876543210')
        self.assertTrue(normalized)

    def test_formatted_number_with_separators_normalized(self):
        value, normalized = svc.normalize_phone('987-654-3210', country_phone_code='91')
        self.assertEqual(value, '+919876543210')

    def test_unnormalisable_value_returns_none_not_a_guess(self):
        value, normalized = svc.normalize_phone('call me maybe', country_phone_code='91')
        self.assertIsNone(value)
        self.assertFalse(normalized)

    def test_empty_value_returns_none(self):
        value, normalized = svc.normalize_phone('')
        self.assertIsNone(value)


class RoutingCodeValidationTests(SimpleTestCase):
    def test_valid_ifsc_accepted(self):
        self.assertTrue(svc.validate_routing_code('HDFC0001234', BankAccount.ROUTING_IFSC))

    def test_invalid_ifsc_rejected(self):
        self.assertFalse(svc.validate_routing_code('12345', BankAccount.ROUTING_IFSC))

    def test_valid_iban_accepted(self):
        self.assertTrue(svc.validate_routing_code('DE89370400440532013000', BankAccount.ROUTING_IBAN))

    def test_valid_swift_accepted(self):
        self.assertTrue(svc.validate_routing_code('DEUTDEFF', BankAccount.ROUTING_SWIFT))

    def test_other_type_never_rejected(self):
        self.assertTrue(svc.validate_routing_code('anything', BankAccount.ROUTING_OTHER))


class NominationShareTests(SimpleTestCase):
    def test_shares_totalling_100_pass(self):
        svc.validate_nomination_shares([Decimal('60'), Decimal('40')])  # no exception

    def test_shares_not_totalling_100_raise(self):
        with self.assertRaises(svc.NominationError):
            svc.validate_nomination_shares([Decimal('60'), Decimal('30')])


class ExperienceOverlapTests(SimpleTestCase):
    def test_non_overlapping_periods_sum_normally(self):
        periods = [
            (datetime.date(2018, 1, 1), datetime.date(2019, 1, 1)),
            (datetime.date(2019, 1, 1), datetime.date(2020, 1, 1)),
        ]
        total = svc.compute_total_experience_years(periods)
        self.assertEqual(total, Decimal('2.0'))

    def test_overlapping_periods_counted_once(self):
        periods = [
            (datetime.date(2018, 1, 1), datetime.date(2020, 1, 1)),
            (datetime.date(2019, 1, 1), datetime.date(2019, 6, 1)),  # fully inside the first — must not double-count
        ]
        total = svc.compute_total_experience_years(periods)
        self.assertEqual(total, Decimal('2.0'))

    def test_gap_between_periods_not_counted(self):
        periods = [
            (datetime.date(2018, 1, 1), datetime.date(2019, 1, 1)),
            (datetime.date(2022, 1, 1), datetime.date(2023, 1, 1)),
        ]
        total = svc.compute_total_experience_years(periods)
        self.assertEqual(total, Decimal('2.0'))  # 1 + 1, not 5

    def test_empty_periods_returns_zero(self):
        self.assertEqual(svc.compute_total_experience_years([]), Decimal('0'))


class HighestQualificationTests(TestCase):
    def setUp(self):
        role = make_role('edu_test_role')
        self.employee = make_user('edu-test@test.com', role=role)

    def test_picks_highest_ranked_level(self):
        EducationRecord.objects.create(employee=self.employee, level='bachelors', institution='A', order=0)
        masters = EducationRecord.objects.create(employee=self.employee, level='masters', institution='B', order=1)
        records = list(EducationRecord.objects.filter(employee=self.employee))
        rank_by_level = {'bachelors': 1, 'masters': 2, 'doctorate': 3}
        highest = svc.derive_highest_qualification(records, rank_by_level)
        self.assertEqual(highest.pk, masters.pk)

    def test_empty_list_returns_none(self):
        self.assertIsNone(svc.derive_highest_qualification([], {}))


class AddressValidationTests(SimpleTestCase):
    def test_required_fields_enforced_per_country_format(self):
        class FakeCountry:
            address_format = {'required_fields': ['postal_code', 'city']}
        errors = svc.validate_address({'line1': '123 Main St'}, FakeCountry())
        self.assertIn('postal_code', errors)
        self.assertIn('city', errors)

    def test_postal_code_regex_enforced(self):
        class FakeCountry:
            address_format = {'postal_code_regex': r'^\d{6}$'}
        errors = svc.validate_address({'postal_code': 'ABC'}, FakeCountry())
        self.assertIn('postal_code', errors)

    def test_no_declared_format_means_no_errors(self):
        class FakeCountry:
            address_format = {}
        errors = svc.validate_address({}, FakeCountry())
        self.assertEqual(errors, {})


class ModelCreationTests(TestCase):
    """Proves the new models round-trip correctly, including encryption."""

    def setUp(self):
        role = make_role('master_data_role')
        self.employee = make_user('master-data@test.com', role=role)

    def test_org_masters_create_and_link(self):
        band = Band.objects.create(code='B1', name='Band 1', rank=1)
        grade = Grade.objects.create(code='G1', name='Grade 1', rank=1, band=band)
        job_family = JobFamily.objects.create(code='ENG', name='Engineering')
        designation = Designation.objects.create(code='SE1', name='Software Engineer I', job_family=job_family, default_grade=grade)
        cost_center = CostCenter.objects.create(code='CC1', name='Engineering Cost Center')
        self.assertEqual(designation.default_grade, grade)
        self.assertEqual(grade.band, band)
        self.assertTrue(CostCenter.objects.filter(pk=cost_center.pk).exists())

    def test_contact_method_round_trip(self):
        cm = ContactMethod.objects.create(employee=self.employee, type=ContactMethod.TYPE_PERSONAL_MOBILE, value='+919876543210', is_primary=True)
        cm.refresh_from_db()
        self.assertEqual(cm.value, '+919876543210')

    def test_bank_account_encrypts_account_number(self):
        from apps.platform_core.models import Currency
        inr, _ = Currency.objects.get_or_create(code='INR', defaults={'name': 'Indian Rupee', 'symbol': '₹', 'minor_units': 2})
        from apps.platform_core.models import Country
        india, _ = Country.objects.get_or_create(iso2='IN', defaults={'iso3': 'IND', 'name': 'India', 'default_currency': inr})
        account = BankAccount.objects.create(
            employee=self.employee, country=india, bank_name='Test Bank',
            account_number='1234567890123456', routing_code_type=BankAccount.ROUTING_IFSC, routing_code='HDFC0001234',
        )
        # Read back through the model layer (decrypts transparently).
        account.refresh_from_db()
        self.assertEqual(account.account_number, '1234567890123456')
        # Confirm the DB column itself is NOT plaintext.
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT account_number FROM hrms_bank_accounts_v2 WHERE id = %s', [str(account.pk)])
            raw = cursor.fetchone()[0]
        self.assertNotEqual(raw, '1234567890123456')

    def test_identity_document_hash_uniqueness_per_type(self):
        from apps.platform_core.models import Country, Currency
        inr, _ = Currency.objects.get_or_create(code='INR', defaults={'name': 'Indian Rupee', 'symbol': '₹', 'minor_units': 2})
        india, _ = Country.objects.get_or_create(iso2='IN', defaults={'iso3': 'IND', 'name': 'India', 'default_currency': inr})
        doc_type = IdentityDocumentType.objects.create(code='PAN_TEST', country=india, label='PAN', unique_scope=IdentityDocumentType.UNIQUE_SCOPE_GLOBAL)
        from django.contrib.contenttypes.models import ContentType
        from apps.accounts.models import User
        ct = ContentType.objects.get_for_model(User)

        from core.encrypted_fields import blind_index
        number_hash = blind_index('ABCDE1234F')
        IdentityDocument.objects.create(content_type=ct, object_id=str(self.employee.pk), type=doc_type, number='ABCDE1234F', number_hash=number_hash)

        other_user = make_user('master-data-2@test.com')
        with self.assertRaises(Exception):
            IdentityDocument.objects.create(content_type=ct, object_id=str(other_user.pk), type=doc_type, number='ABCDE1234F', number_hash=number_hash)

    def test_address_round_trip_with_generic_owner(self):
        from django.contrib.contenttypes.models import ContentType
        from apps.accounts.models import User
        from apps.platform_core.models import Country, Currency
        inr, _ = Currency.objects.get_or_create(code='INR', defaults={'name': 'Indian Rupee', 'symbol': '₹', 'minor_units': 2})
        india, _ = Country.objects.get_or_create(iso2='IN', defaults={'iso3': 'IND', 'name': 'India', 'default_currency': inr})
        ct = ContentType.objects.get_for_model(User)
        address = Address.objects.create(
            content_type=ct, object_id=str(self.employee.pk), type=Address.TYPE_CURRENT,
            country=india, line1='123 Main St', city='Hyderabad', postal_code='500001', is_primary=True,
        )
        self.assertEqual(
            Address.objects.filter(content_type=ct, object_id=str(self.employee.pk), type=Address.TYPE_CURRENT).count(), 1,
        )
        self.assertEqual(address.country, india)

    def test_family_member_gains_structured_name_fields(self):
        fm = FamilyMember.objects.create(employee=self.employee, name='Priya Sharma', relationship='spouse', first_name='Priya', last_name='Sharma')
        self.assertEqual(fm.first_name, 'Priya')

    def test_nomination_links_family_member_and_scheme(self):
        from apps.platform_core.models import LookupType, LookupValue
        lookup_type = LookupType.objects.create(code='NOMINATION_SCHEME_TEST', name='Nomination scheme')
        scheme = LookupValue.objects.create(lookup_type=lookup_type, code='PF', label='Provident Fund')
        fm = FamilyMember.objects.create(employee=self.employee, name='Priya Sharma', relationship='spouse')
        nomination = Nomination.objects.create(employee=self.employee, scheme=scheme, family_member=fm, share_percentage=Decimal('100.00'))
        self.assertEqual(nomination.share_percentage, Decimal('100.00'))

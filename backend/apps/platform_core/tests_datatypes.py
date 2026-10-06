"""Phase 2 Task B.2/B.3 — data type validator/normaliser tests."""
from __future__ import annotations

from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.platform_core import services_datatypes as dt


def _field(data_type, **kwargs):
    defaults = dict(code='test_field', multiple=False, lookup_type=None, reference_entity=None, validation={})
    defaults.update(kwargs)
    return SimpleNamespace(data_type=data_type, **defaults)


class DataTypeValidatorTests(SimpleTestCase):
    def test_text_strips_whitespace(self):
        self.assertEqual(dt.validate_and_normalise(_field('text'), '  hello  '), 'hello')

    def test_text_rejects_non_string(self):
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(_field('text'), 123)

    def test_text_length_bounds(self):
        field = _field('text', validation={'min_length': 3, 'max_length': 5})
        self.assertEqual(dt.validate_and_normalise(field, 'abcd'), 'abcd')
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(field, 'ab')
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(field, 'abcdef')

    def test_text_regex(self):
        field = _field('text', validation={'regex': r'^[A-Z]{3}$'})
        self.assertEqual(dt.validate_and_normalise(field, 'ABC'), 'ABC')
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(field, 'abc')

    def test_rich_text_strips_disallowed_tags(self):
        result = dt.validate_and_normalise(_field('rich_text'), '<p>Hello</p><script>alert(1)</script>')
        self.assertIn('<p>Hello</p>', result)
        self.assertNotIn('<script>', result)

    def test_integer_bounds(self):
        field = _field('integer', validation={'min': 1, 'max': 10})
        self.assertEqual(dt.validate_and_normalise(field, '5'), 5)
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(field, 0)
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(field, 11)

    def test_integer_rejects_non_numeric(self):
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(_field('integer'), 'not a number')

    def test_decimal_places(self):
        # Decimal.quantize's default rounding is ROUND_HALF_EVEN (banker's
        # rounding) — 1.006 is unambiguous either way, avoiding the
        # half-way case entirely rather than asserting a specific
        # rounding-mode choice this test doesn't actually care about.
        field = _field('decimal', validation={'decimal_places': 2})
        self.assertEqual(dt.validate_and_normalise(field, '1.006'), '1.01')

    def test_currency_amount_shape(self):
        field = _field('currency_amount')
        result = dt.validate_and_normalise(field, {'amount': '100.50', 'currency': 'inr'})
        self.assertEqual(result, {'amount': '100.50', 'currency': 'INR'})

    def test_currency_amount_rejects_bad_shape(self):
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(_field('currency_amount'), '100.50')

    def test_percentage_default_bounds(self):
        field = _field('percentage')
        self.assertEqual(dt.validate_and_normalise(field, 50), '50')
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(field, 150)

    def test_boolean_strict(self):
        self.assertTrue(dt.validate_and_normalise(_field('boolean'), True))
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(_field('boolean'), 'true')

    def test_date_not_future(self):
        field = _field('date', validation={'not_future': True})
        self.assertEqual(dt.validate_and_normalise(field, '2020-01-01'), '2020-01-01')
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(field, '2099-01-01')

    def test_date_min_age(self):
        field = _field('date', validation={'min_age_years': 18})
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(field, '2020-01-01')  # a toddler, not 18 yet

    def test_date_invalid_format(self):
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(_field('date'), 'not-a-date')

    def test_email(self):
        self.assertEqual(dt.validate_and_normalise(_field('email'), ' Foo@Example.com '), 'foo@example.com')
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(_field('email'), 'not-an-email')

    def test_phone_e164(self):
        self.assertEqual(dt.validate_and_normalise(_field('phone'), '+919876543210'), '+919876543210')
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(_field('phone'), '9876543210')  # missing +country code

    def test_url(self):
        self.assertEqual(dt.validate_and_normalise(_field('url'), 'https://example.com'), 'https://example.com')
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(_field('url'), 'javascript:alert(1)')

    def test_json_rejects_non_serializable(self):
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(_field('json'), {1, 2, 3})  # a set isn't JSON-serializable

    def test_unregistered_type_raises(self):
        with self.assertRaises(dt.DataTypeError):
            dt.validate_and_normalise(_field('image'), 'anything')

"""The filter engine on its own: what it accepts, what it refuses, and the shape of what it builds. No database needed."""
from django.test import SimpleTestCase

from apps.global_search import filters as f
from apps.global_search.registry import FieldSpec

GENDERS = (('male', 'Male'), ('female', 'Female'), ('other', 'Other'))
FIELDS = {spec.key: spec for spec in (
    FieldSpec('name', 'Name', f.TEXT, 'full_name'),
    FieldSpec('gender', 'Gender', f.CHOICE, 'profile__gender', choices=GENDERS),
    FieldSpec('joined', 'Joined', f.DATE, 'date_of_joining'),
    FieldSpec('days', 'Days', f.NUMBER, 'total_days'),
    FieldSpec('punch_in', 'Punch in', f.TIME, 'first_punch_in'),
    FieldSpec('posted', 'Posted on', f.DATETIME, 'created_at'),
    FieldSpec('active', 'Active', f.BOOLEAN, 'is_active'),
)}


def leaf(field, operator, value=None, **extra):
    node = {'field': field, 'operator': operator, **extra}
    if value is not None:
        node['value'] = value
    return node


def refused(case, tree, fragment=None):
    with case.assertRaises(f.FilterError, msg=str(tree)) as caught:
        f.build_filter(tree, FIELDS)
    if fragment:
        case.assertIn(fragment, caught.exception.message)


class AllowListTests(SimpleTestCase):
    def test_an_empty_filter_matches_everything(self):
        for empty in (None, {}, []):
            self.assertEqual(str(f.build_filter(empty, FIELDS)), '(AND: )')

    def test_a_field_not_in_the_registry_is_refused(self):
        refused(self, leaf('password', 'eq', 'x'), 'Unknown or unavailable')

    def test_the_browser_cannot_name_an_orm_path_or_a_lookup(self):
        for key in ('profile__gender', 'full_name__icontains', 'groups__user__password', 'pk', '__class__', 'is_superuser'):
            refused(self, leaf(key, 'eq', 'x'), 'Unknown or unavailable')

    def test_an_operator_outside_the_field_type_is_refused(self):
        refused(self, leaf('gender', 'contains', 'fem'), 'cannot be used with Gender')
        refused(self, leaf('active', 'contains', 'x'), 'cannot be used')
        refused(self, leaf('name', 'between', ['a', 'b']), 'cannot be used')
        refused(self, leaf('joined', 'contains', '2026'), 'cannot be used')

    def test_an_unknown_operator_is_refused(self):
        refused(self, leaf('name', 'regex', '.*'), 'cannot be used')
        refused(self, leaf('name', '__icontains', 'x'), 'cannot be used')

    def test_a_node_that_is_not_an_object_is_refused(self):
        refused(self, 'full_name', 'must be an object')
        refused(self, {'op': 'and', 'items': ['full_name']}, 'must be an object')
        refused(self, leaf('name', 5), 'Choose how')


class ValueTests(SimpleTestCase):
    def test_a_choice_must_be_one_of_the_declared_choices(self):
        f.build_filter(leaf('gender', 'eq', 'female'), FIELDS)
        refused(self, leaf('gender', 'eq', 'robot'), 'not a valid choice')
        refused(self, leaf('gender', 'in', ['female', 'robot']), 'not a valid choice')

    def test_dates_numbers_times_and_booleans_are_converted_or_refused(self):
        f.build_filter(leaf('joined', 'after', '2026-01-31'), FIELDS)
        f.build_filter(leaf('days', 'gte', 2.5), FIELDS)
        f.build_filter(leaf('punch_in', 'before', '09:30'), FIELDS)
        f.build_filter(leaf('active', 'eq', 'true'), FIELDS)
        refused(self, leaf('joined', 'after', '31-01-2026'), 'not a valid date')
        refused(self, leaf('joined', 'after', '2026-02-31'), 'not a valid date')
        refused(self, leaf('days', 'gt', 'many'), 'not a valid number')
        refused(self, leaf('punch_in', 'before', '9am'), 'not a valid time')
        refused(self, leaf('active', 'eq', 'maybe'), 'not a valid boolean')

    def test_a_filter_that_needs_a_value_but_has_none_is_refused(self):
        refused(self, {'field': 'name', 'operator': 'eq'}, 'Enter a value')
        refused(self, leaf('gender', 'in', []), 'at least one value')

    def test_between_needs_a_start_and_an_end_in_order(self):
        f.build_filter(leaf('joined', 'between', ['2026-01-01', '2026-12-31']), FIELDS)
        refused(self, leaf('joined', 'between', ['2026-01-01']), 'start and an end')
        refused(self, leaf('joined', 'between', '2026-01-01'), 'start and an end')
        refused(self, leaf('joined', 'between', ['2026-12-31', '2026-01-01']), 'after its end')
        refused(self, leaf('days', 'between', [10, 1]), 'after its end')

    def test_text_values_are_text_and_limited_in_length(self):
        refused(self, leaf('name', 'contains', {'a': 1}), 'Enter text')
        refused(self, leaf('name', 'contains', True), 'Enter text')
        refused(self, leaf('name', 'contains', 'x' * (f.MAX_TEXT_LENGTH + 1)), 'at most')

    def test_a_datetime_is_filtered_by_its_calendar_day(self):
        built = str(f.build_filter(leaf('posted', 'after', '2026-11-18T23:59:59'), FIELDS))
        self.assertIn('created_at__date__gt', built)
        self.assertIn('datetime.date(2026, 11, 18)', built)   # the time of day is dropped


class ShapeTests(SimpleTestCase):
    def test_operators_build_the_expected_lookups(self):
        expected = {
            'eq': 'full_name__iexact', 'contains': 'full_name__icontains', 'starts_with': 'full_name__istartswith',
            'ends_with': 'full_name__iendswith',
        }
        for operator, lookup in expected.items():
            self.assertIn(lookup, str(f.build_filter(leaf('name', operator, 'ann'), FIELDS)))
        self.assertIn('NOT', str(f.build_filter(leaf('name', 'ne', 'ann'), FIELDS)))
        self.assertIn('NOT', str(f.build_filter(leaf('name', 'not_contains', 'ann'), FIELDS)))
        self.assertIn('days__gt', str(f.build_filter(leaf('days', 'gt', 1), FIELDS)))
        self.assertIn('days__lt', str(f.build_filter(leaf('days', 'lt', 1), FIELDS)))
        self.assertIn('joined'.replace('joined', 'date_of_joining__lt'), str(f.build_filter(leaf('joined', 'before', '2026-01-01'), FIELDS)))
        self.assertIn('date_of_joining__range', str(f.build_filter(leaf('joined', 'between', ['2026-01-01', '2026-02-01']), FIELDS)))
        self.assertIn('profile__gender__in', str(f.build_filter(leaf('gender', 'in', ['male', 'female']), FIELDS)))

    def test_emptiness_covers_null_and_blank_text(self):
        text_empty = str(f.build_filter({'field': 'name', 'operator': 'is_empty'}, FIELDS))
        self.assertIn('full_name__isnull', text_empty)
        self.assertIn("full_name", text_empty)
        date_empty = str(f.build_filter({'field': 'joined', 'operator': 'is_empty'}, FIELDS))
        self.assertIn('date_of_joining__isnull', date_empty)
        self.assertIn('NOT', str(f.build_filter({'field': 'joined', 'operator': 'is_not_empty'}, FIELDS)))

    def test_and_or_and_nesting(self):
        tree = {'op': 'and', 'items': [
            leaf('gender', 'eq', 'female'),
            {'op': 'or', 'items': [leaf('name', 'starts_with', 'A'), leaf('name', 'starts_with', 'B')]},
        ]}
        built = str(f.build_filter(tree, FIELDS))
        self.assertIn('AND', built)
        self.assertIn('OR', built)

    def test_a_bare_condition_is_accepted_as_a_one_item_group(self):
        self.assertIn('profile__gender', str(f.build_filter(leaf('gender', 'eq', 'male'), FIELDS)))

    def test_groups_are_validated(self):
        refused(self, {'op': 'xor', 'items': [leaf('name', 'eq', 'a')]}, 'must be "and" or "or"')
        refused(self, {'op': 'and', 'items': []}, 'cannot be empty')
        refused(self, {'op': 'and', 'items': 'nope'}, 'cannot be empty')

    def test_depth_and_condition_limits(self):
        deepest = leaf('name', 'eq', 'a')
        for _ in range(f.MAX_DEPTH + 1):   # the outermost group is level 1
            deepest = {'op': 'and', 'items': [deepest]}
        refused(self, deepest, 'nested at most')
        within = leaf('name', 'eq', 'a')
        for _ in range(f.MAX_DEPTH):
            within = {'op': 'or', 'items': [within]}
        f.build_filter(within, FIELDS)
        refused(self, {'op': 'and', 'items': [leaf('name', 'eq', 'a')] * (f.MAX_CONDITIONS + 1)}, 'at most')
        f.build_filter({'op': 'and', 'items': [leaf('name', 'eq', 'a')] * f.MAX_CONDITIONS}, FIELDS)

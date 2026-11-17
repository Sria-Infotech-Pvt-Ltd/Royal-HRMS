"""Search, pinned-only and sort options for the announcements list (no database needed)."""
from django.db.models import Q
from django.test import SimpleTestCase

from apps.announcements.services_list_options import (
    DEFAULT_SORT, MAX_SEARCH_LENGTH, SORT_ORDERINGS, apply_list_options, parse_options,
)


class RecordingQuerySet:
    """Stands in for a queryset: remembers every filter() and order_by() call and returns itself."""

    def __init__(self):
        self.filters = []
        self.ordering = None

    def filter(self, *args, **kwargs):
        self.filters.append((args, kwargs))
        return self

    def order_by(self, *fields):
        self.ordering = fields
        return self


class ParseOptionsTests(SimpleTestCase):
    def test_no_options_means_newest_first_with_no_search_and_no_pin_filter(self):
        self.assertEqual(parse_options({}), {'search': '', 'pinned_only': False, 'sort': DEFAULT_SORT})

    def test_search_is_trimmed_and_limited(self):
        self.assertEqual(parse_options({'search': '  holiday  '})['search'], 'holiday')
        self.assertEqual(len(parse_options({'search': 'x' * 500})['search']), MAX_SEARCH_LENGTH)

    def test_the_pinned_switch_accepts_the_usual_true_values_only(self):
        for value in ('1', 'true', 'TRUE', 'yes'):
            self.assertTrue(parse_options({'pinned': value})['pinned_only'], value)
        for value in ('0', 'false', '', 'maybe', None):
            self.assertFalse(parse_options({'pinned': value})['pinned_only'], value)

    def test_an_unknown_sort_falls_back_to_the_default(self):
        self.assertEqual(parse_options({'sort': 'random'})['sort'], DEFAULT_SORT)
        for known in SORT_ORDERINGS:
            self.assertEqual(parse_options({'sort': known})['sort'], known)


class ApplyListOptionsTests(SimpleTestCase):
    def test_without_options_nothing_is_filtered_and_the_old_order_is_kept(self):
        qs = apply_list_options(RecordingQuerySet(), {})
        self.assertEqual(qs.filters, [])
        self.assertEqual(qs.ordering, ('-is_pinned', '-created_at', '-id'))

    def test_search_looks_in_the_title_and_the_body(self):
        qs = apply_list_options(RecordingQuerySet(), {'search': 'diwali'})
        self.assertEqual(qs.filters, [((Q(title__icontains='diwali') | Q(body__icontains='diwali'),), {})])

    def test_a_blank_search_is_ignored(self):
        self.assertEqual(apply_list_options(RecordingQuerySet(), {'search': '   '}).filters, [])

    def test_pinned_only_filters_to_pinned_posts(self):
        qs = apply_list_options(RecordingQuerySet(), {'pinned': '1'})
        self.assertEqual(qs.filters, [((), {'is_pinned': True})])

    def test_search_and_pinned_combine(self):
        qs = apply_list_options(RecordingQuerySet(), {'search': 'policy', 'pinned': 'true'})
        self.assertEqual(len(qs.filters), 2)

    def test_every_sort_keeps_pinned_posts_on_top_and_ends_with_a_tie_breaker(self):
        for name, ordering in SORT_ORDERINGS.items():
            self.assertEqual(ordering[0], '-is_pinned', name)
            self.assertIn(ordering[-1], ('-id', 'id'), name)

    def test_each_sort_orders_by_what_it_says(self):
        expected = {'newest': '-created_at', 'oldest': 'created_at', 'reactions': '-reaction_count', 'views': '-views_count'}
        for name, field in expected.items():
            ordering = apply_list_options(RecordingQuerySet(), {'sort': name}).ordering
            self.assertEqual(ordering[1], field, name)

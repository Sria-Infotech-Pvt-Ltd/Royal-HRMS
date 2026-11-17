"""The onboarding approvals queue helpers: filters, order and totals (no database: queries are only built, never run)."""
from unittest import mock

from django.test import SimpleTestCase

from apps.accounts.models import User
from apps.accounts.services_onboarding_queue import (
    MAX_SEARCH_LENGTH, QUEUE_MEMBERSHIP, STATUS_FILTERS, apply_queue_filters, order_queue, queue_counts,
)


def sql(queryset) -> str:
    return str(queryset.query)


class ApplyQueueFiltersTests(SimpleTestCase):
    base = User.objects.filter(QUEUE_MEMBERSHIP)

    def test_no_filter_leaves_the_queue_as_it_is(self):
        self.assertEqual(sql(apply_queue_filters(self.base, '', '')), sql(self.base))
        self.assertEqual(sql(apply_queue_filters(self.base, '  ', '  ')), sql(self.base))

    def test_a_status_word_narrows_to_that_status(self):
        for word, value in (('submitted', User.ONBOARDING_SUBMITTED), ('rejected', User.ONBOARDING_REJECTED), (' REJECTED ', User.ONBOARDING_REJECTED), ('approved', User.ONBOARDING_COMPLETE)):
            self.assertIn(f'"onboarding_status" = {value}', sql(apply_queue_filters(self.base, word, '')).replace("'", ''))

    def test_an_unknown_status_is_ignored_rather_than_emptying_the_list(self):
        self.assertEqual(sql(apply_queue_filters(self.base, 'archived', '')), sql(self.base))
        self.assertEqual(sql(apply_queue_filters(self.base, 'x; drop table', '')), sql(self.base))

    def test_search_looks_in_name_email_designation_and_employee_id(self):
        query = sql(apply_queue_filters(self.base, '', 'asha'))
        for column in ('full_name', 'email', 'designation', 'employee_id'):
            self.assertIn(column, query)
        self.assertIn('%asha%'.upper(), query.upper())

    def test_search_text_is_trimmed_and_capped(self):
        long_text = 'a' * (MAX_SEARCH_LENGTH + 50)
        query = sql(apply_queue_filters(self.base, '', long_text))
        self.assertIn('a' * MAX_SEARCH_LENGTH, query)
        self.assertNotIn('a' * (MAX_SEARCH_LENGTH + 1), query)

    def test_search_text_cannot_break_out_of_the_query(self):
        query = sql(apply_queue_filters(self.base, '', "x' OR 1=1 --"))
        self.assertNotIn("OR 1=1 --' ", query.replace("''", ''))  # quoted as data by the database layer, never run as SQL


class OrderQueueTests(SimpleTestCase):
    def test_people_awaiting_review_come_first_then_longest_waiting(self):
        order = order_queue(User.objects.all()).query.order_by
        self.assertEqual((order[0], order[2], order[3]), ('_queue_rank', 'date_joined', 'pk'))
        self.assertTrue(order[1].descending)
        self.assertTrue(order[1].nulls_last)

    def test_the_rank_puts_waiting_first_then_sent_back_then_approved(self):
        query = sql(order_queue(User.objects.all())).replace("'", '')
        self.assertIn('CASE WHEN "hrms_users"."onboarding_status" = submitted THEN 0 WHEN "hrms_users"."onboarding_status" = rejected THEN 1 ELSE 2 END', query)

    def test_only_approved_people_are_sorted_newest_first(self):
        query = sql(order_queue(User.objects.all())).replace("'", '')
        self.assertIn('CASE WHEN ("hrms_users"."onboarding_status" = complete AND "hrms_users"."requires_self_service_onboarding") THEN "hrms_users"."updated_at" ELSE NULL END', query)


class QueueMembershipTests(SimpleTestCase):
    def test_approved_means_finished_and_went_through_the_self_service_wizard(self):
        query = sql(User.objects.filter(STATUS_FILTERS['approved'])).replace("'", '')
        self.assertIn(f'"onboarding_status" = {User.ONBOARDING_COMPLETE}', query)
        self.assertIn('"requires_self_service_onboarding"', query)  # people hired another way never used the wizard

    def test_the_list_can_show_all_three_statuses_and_nothing_else(self):
        query = sql(User.objects.filter(QUEUE_MEMBERSHIP)).replace("'", '')
        for value in (User.ONBOARDING_SUBMITTED, User.ONBOARDING_REJECTED, User.ONBOARDING_COMPLETE):
            self.assertIn(f'"onboarding_status" = {value}', query)
        for value in (User.ONBOARDING_PENDING, User.ONBOARDING_DRAFT):
            self.assertNotIn(f'"onboarding_status" = {value}', query)


class QueueCountsTests(SimpleTestCase):
    def test_totals_count_each_status_and_add_up(self):
        queue = mock.MagicMock()
        by_filter = {id(STATUS_FILTERS['submitted']): 7, id(STATUS_FILTERS['rejected']): 2, id(STATUS_FILTERS['approved']): 30}
        queue.filter.side_effect = lambda matches: mock.Mock(count=lambda: by_filter[id(matches)])
        self.assertEqual(queue_counts(queue), {'total': 39, 'submitted': 7, 'rejected': 2, 'approved': 30})

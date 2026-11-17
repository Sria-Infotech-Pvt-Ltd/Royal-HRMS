"""Face ID roster: each employee's state, the filter and the overall counts (no database: queries are only built, never run)."""
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase

from apps.attendance import services_face_roster as roster
from apps.attendance.serializers_face_registration import FaceRosterEmployeeSerializer

User = get_user_model()


def sql(queryset) -> str:
    return str(queryset.query).replace("'", '')


class FaceStateTests(SimpleTestCase):
    def test_a_usable_face_id_is_approved_and_active_and_beats_a_newer_pending_request(self):
        query = sql(roster.annotate_face_state(User.objects.all()))
        order = [query.index(word) for word in ('THEN approved', 'THEN pending', 'THEN rejected')]
        self.assertEqual(order, sorted(order))
        self.assertIn('"is_active"', query.split('THEN approved')[0].split('WHEN')[1])  # only an ACTIVE approved one counts
        self.assertIn('ELSE none', query)

    def test_the_state_is_worked_out_in_one_query_not_one_per_person(self):
        self.assertEqual(sql(roster.annotate_face_state(User.objects.all())).count('SELECT'), 1 + 3)  # the list plus one EXISTS per state


class FaceFilterTests(SimpleTestCase):
    annotated = roster.annotate_face_state(User.objects.all())

    def test_a_state_word_narrows_to_that_state(self):
        for state in roster.STATES:
            self.assertTrue(sql(roster.apply_face_filter(self.annotated, state)).endswith(f'END = {state}'), state)

    def test_incomplete_means_everyone_who_is_not_approved(self):
        query = sql(roster.apply_face_filter(self.annotated, 'incomplete'))
        self.assertIn('NOT', query)
        self.assertIn('approved', query.rsplit('WHERE', 1)[1])

    def test_an_unknown_or_empty_word_changes_nothing(self):
        for word in ('', '  ', 'archived', 'x; drop table', None):
            self.assertEqual(sql(roster.apply_face_filter(self.annotated, word)), sql(self.annotated))

    def test_the_word_is_not_case_sensitive(self):
        self.assertEqual(sql(roster.apply_face_filter(self.annotated, ' INCOMPLETE ')), sql(roster.apply_face_filter(self.annotated, 'incomplete')))


class FaceCountsTests(SimpleTestCase):
    def test_incomplete_is_everyone_minus_those_with_a_usable_face_id(self):
        annotated = mock.MagicMock()
        annotated.aggregate.return_value = {'total': 53, 'approved': 37, 'pending': 4, 'rejected': 2, 'none': 10}
        self.assertEqual(roster.face_counts(annotated), {'total': 53, 'approved': 37, 'pending': 4, 'rejected': 2, 'none': 10, 'incomplete': 16})

    def test_every_state_is_counted_in_one_aggregate(self):
        annotated = mock.MagicMock()
        annotated.aggregate.return_value = {'total': 0, 'approved': 0, 'pending': 0, 'rejected': 0, 'none': 0}
        roster.face_counts(annotated)
        self.assertEqual(set(annotated.aggregate.call_args.kwargs), {'total', *roster.STATES})
        annotated.aggregate.assert_called_once()


class RosterSerializerTests(SimpleTestCase):
    def row(self, **extra):
        return SimpleNamespace(id='u1', employee_id='E1', full_name='Asha Verma', email='a@example.com', branch='Hyd', department='Eng', designation='Dev', **extra)

    def test_each_row_carries_the_face_state_from_the_annotation(self):
        self.assertEqual(FaceRosterEmployeeSerializer(self.row(_face_state='pending')).data['face_status'], 'pending')

    def test_a_row_without_the_annotation_reads_as_not_registered(self):
        self.assertEqual(FaceRosterEmployeeSerializer(self.row()).data['face_status'], 'none')

    def test_the_row_still_has_only_the_minimal_picker_fields_plus_the_state(self):
        self.assertEqual(set(FaceRosterEmployeeSerializer(self.row()).data), {'uuid', 'employee_id', 'full_name', 'email', 'branch', 'department', 'designation', 'face_status'})

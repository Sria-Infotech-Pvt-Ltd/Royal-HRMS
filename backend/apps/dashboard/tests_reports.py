"""
The Reports screen API: which reports a person may run, that each is built in their own scope, and emailing a report.

Reports are built on the server for the signed-in person; the browser never supplies report content. Emails go only to
active employees picked by id, leave out contact-detail columns, are rate limited and audited.
"""
from __future__ import annotations

import io
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.attendance.models import FaceRegistrationRequest
from apps.dashboard.services_report_delivery import MAX_RECIPIENTS, MAX_SENDS_PER_HOUR, render_csv
from apps.dashboard.services_reports import REPORTS, ReportData
from apps.recruitment.models import Candidate

SEND = 'apps.dashboard.services_report_delivery.send_template_email'
ALL_REPORT_PERMISSIONS = [spec.permission for spec in REPORTS]


def _as(user) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


class _Base(TestCase):
    def setUp(self):
        cache.clear()
        self.hr = make_user('rep-hr@test.com', employee_id='RH001', full_name='Hema HR', branch='Kondapur',
                            role=make_role('rep_hr', permission_codenames=['employees.export', 'recruitment.view', 'facial_recognition.approve']))
        self.local = make_user('rep-local@test.com', employee_id='RL001', full_name='Local Person', branch='Kondapur', phone='9000000001')
        self.faraway = make_user('rep-far@test.com', employee_id='RF001', full_name='Far Person', branch='Madhapur')
        self.nobody = make_user('rep-nobody@test.com', employee_id='RN001', full_name='No Access', branch='Kondapur')

    def run_report(self, user, key, **query):
        return _as(user).get(reverse('report-download', args=[key]), query)

    def send(self, user, key, body):
        return _as(user).post(reverse('report-send', args=[key]), body, format='json')


class CatalogTests(_Base):
    def test_a_person_sees_only_the_reports_their_permissions_allow(self):
        keys = {entry['key'] for entry in _as(self.hr).get(reverse('report-catalog')).data['data']['reports']}
        self.assertEqual(keys, {'employees', 'candidates', 'face_registrations'})
        self.assertEqual(_as(self.nobody).get(reverse('report-catalog')).data['data']['reports'], [])

    def test_the_catalog_says_which_columns_an_emailed_copy_leaves_out(self):
        entry = next(e for e in _as(self.hr).get(reverse('report-catalog')).data['data']['reports'] if e['key'] == 'employees')
        self.assertEqual(entry['email_omits'], ['Email', 'Phone'])

    def test_every_report_builds_for_someone_allowed_to_run_all_of_them(self):
        everything = make_user('rep-all@test.com', employee_id='RA001', is_superuser=True)
        for spec in REPORTS:
            response = self.run_report(everything, spec.key)
            self.assertEqual(response.status_code, 200, spec.key)
            self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')


class AuthorizationAndScopeTests(_Base):
    def test_a_report_needs_its_own_permission_and_an_unknown_one_is_not_found(self):
        self.assertEqual(self.run_report(self.nobody, 'employees').status_code, 403)
        self.assertEqual(self.run_report(self.hr, 'leave').status_code, 403)          # HR here lacks leave.approve
        self.assertEqual(self.run_report(self.hr, 'no-such-report').status_code, 404)

    def test_the_employee_report_stays_inside_the_requesters_scope(self):
        text = self.run_report(self.hr, 'employees').content.decode('utf-8')
        self.assertIn('Local Person', text)
        self.assertNotIn('Far Person', text)

    def test_a_download_keeps_the_contact_columns_for_someone_who_may_see_them(self):
        text = self.run_report(self.hr, 'employees').content.decode('utf-8')
        self.assertIn('"Email"', text)
        self.assertIn('9000000001', text)

    def test_a_cell_that_looks_like_a_formula_is_defused(self):
        make_user('rep-evil@test.com', employee_id='RE001', full_name='=HYPERLINK("http://x","click")', branch='Kondapur')
        text = self.run_report(self.hr, 'employees').content.decode('utf-8')
        self.assertIn('\'=HYPERLINK', text)
        self.assertNotIn('"=HYPERLINK', text)

    def test_the_candidate_report_has_no_contact_details(self):
        from apps.branch.models import Branch, City, State

        state, _ = State.objects.get_or_create(name='Telangana')
        city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
        branch, _ = Branch.objects.get_or_create(branch_code='KDP', defaults={'branch_name': 'Kondapur', 'city': city, 'state': state})
        Candidate.objects.create(name='Cand One', email='cand.one@test.com', phone='9111111111', position_applied='Engineer', branch=branch)
        text = self.run_report(self.hr, 'candidates').content.decode('utf-8')
        self.assertIn('Cand One', text)
        self.assertNotIn('cand.one@test.com', text)
        self.assertNotIn('9111111111', text)

    def test_the_face_report_never_carries_biometric_data(self):
        FaceRegistrationRequest.objects.create(employee=self.local, face_embedding=[0.123456, 0.2, 0.3], liveness_passed=True)
        text = self.run_report(self.hr, 'face_registrations').content.decode('utf-8')
        self.assertIn('Local Person', text)
        self.assertNotIn('0.123456', text)

    def test_unknown_filter_values_are_ignored_not_trusted(self):
        response = self.run_report(self.hr, 'employees', status='nonsense', extra='x')
        self.assertEqual(response.status_code, 200)
        self.assertIn('Local Person', response.content.decode('utf-8'))


class EmailTests(_Base):
    def setUp(self):
        super().setUp()
        self.colleague = make_user('rep-colleague@test.com', employee_id='RC001', full_name='Colleague', branch='Kondapur')

    def test_the_report_is_emailed_to_each_recipient_separately_without_contact_columns(self):
        with patch(SEND) as sender:
            response = self.send(self.hr, 'employees', {'recipients': [str(self.colleague.pk), str(self.local.pk)], 'note': 'For your review'})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(sender.call_count, 2)
        first = sender.call_args_list[0].kwargs
        self.assertEqual({call.kwargs['recipient_email'] for call in sender.call_args_list}, {'rep-colleague@test.com', 'rep-local@test.com'})
        name, content, mime = first['extra_attachments'][0]
        self.assertEqual(mime, 'text/csv')
        body = content.decode('utf-8')
        self.assertIn('Local Person', body)
        self.assertNotIn('9000000001', body)             # phone left out of the emailed copy
        self.assertNotIn('"Email"', body)
        self.assertEqual(first['reply_to'], 'rep-hr@test.com')
        self.assertIn('For your review', first['context']['note'])

    def test_the_send_is_audited_without_the_data(self):
        with patch(SEND):
            self.send(self.hr, 'employees', {'recipients': [str(self.colleague.pk)]})
        row = AuditLog.objects.get(action='report_emailed')
        self.assertEqual((row.user_id, row.object_id), (self.hr.pk, 'employees'))
        self.assertEqual((row.changes['recipients'], row.changes['sent'], row.changes['failed']), (1, 1, 0))
        self.assertNotIn('Local Person', str(row.changes))

    def test_only_active_employees_can_receive_a_report(self):
        outsider = make_user('rep-inactive@test.com', employee_id='RI001', is_active=False)
        no_id = make_user('rep-noid@test.com', employee_id='')
        with patch(SEND) as sender:
            for bad in ([str(outsider.pk)], [str(no_id.pk)], ['not-a-user'], ['00000000-0000-0000-0000-000000000000'], [], None):
                response = self.send(self.hr, 'employees', {'recipients': bad})
                self.assertEqual(response.status_code, 400, bad)
        sender.assert_not_called()

    def test_a_raw_email_address_is_not_accepted_as_a_recipient(self):
        with patch(SEND) as sender:
            response = self.send(self.hr, 'employees', {'recipients': ['someone@outside.example']})
        self.assertEqual(response.status_code, 400)
        sender.assert_not_called()

    def test_too_many_recipients_are_refused(self):
        people = [make_user(f'rep-bulk{i}@test.com', employee_id=f'RB{i:03d}') for i in range(MAX_RECIPIENTS + 1)]
        with patch(SEND) as sender:
            response = self.send(self.hr, 'employees', {'recipients': [str(p.pk) for p in people]})
        self.assertEqual(response.status_code, 400)
        sender.assert_not_called()

    def test_report_content_sent_by_the_browser_is_ignored(self):
        with patch(SEND) as sender:
            self.send(self.hr, 'employees', {'recipients': [str(self.colleague.pk)], 'csv': 'forged,data', 'rows': [['x']]})
        self.assertNotIn('forged', sender.call_args.kwargs['extra_attachments'][0][1].decode('utf-8'))

    def test_someone_without_the_reports_permission_cannot_email_it(self):
        with patch(SEND) as sender:
            response = self.send(self.nobody, 'employees', {'recipients': [str(self.colleague.pk)]})
        self.assertEqual(response.status_code, 403)
        sender.assert_not_called()

    def test_an_empty_report_is_not_sent(self):
        with patch(SEND) as sender:
            response = self.send(self.hr, 'employees', {'recipients': [str(self.colleague.pk)], 'filters': {'status': 'exited'}})
        self.assertEqual(response.status_code, 400)
        sender.assert_not_called()

    def test_sending_is_rate_limited(self):
        with patch(SEND):
            for _ in range(MAX_SENDS_PER_HOUR):
                self.assertEqual(self.send(self.hr, 'employees', {'recipients': [str(self.colleague.pk)]}).status_code, 200)
            self.assertEqual(self.send(self.hr, 'employees', {'recipients': [str(self.colleague.pk)]}).status_code, 429)

    def test_a_failed_email_is_reported_and_not_called_a_success(self):
        with patch(SEND, side_effect=RuntimeError('535 authentication failed')):
            response = self.send(self.hr, 'employees', {'recipients': [str(self.colleague.pk)]})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(AuditLog.objects.get(action='report_emailed').changes['failed'], 1)

    def test_a_partial_failure_says_who_could_not_be_reached(self):
        with patch(SEND, side_effect=[None, RuntimeError('mailbox unavailable')]):
            response = self.send(self.hr, 'employees', {'recipients': [str(self.colleague.pk), str(self.local.pk)]})
        self.assertEqual(response.status_code, 200)
        self.assertIn('1 could not be reached', response.data['message'])


class RecipientSearchTests(_Base):
    def test_search_returns_active_employees_without_any_contact_details(self):
        rows = _as(self.hr).get(reverse('report-recipients'), {'q': 'Local'}).data['data']['results']
        self.assertEqual([r['employee_id'] for r in rows], ['RL001'])
        self.assertEqual(set(rows[0]), {'id', 'employee_id', 'name', 'designation'})

    def test_inactive_people_and_yourself_are_not_offered(self):
        make_user('rep-gone@test.com', employee_id='RG001', full_name='Local Gone', is_active=False)
        names = [r['name'] for r in _as(self.hr).get(reverse('report-recipients'), {'q': 'Local'}).data['data']['results']]
        self.assertEqual(names, ['Local Person'])
        self.assertEqual(_as(self.hr).get(reverse('report-recipients'), {'q': 'Hema'}).data['data']['results'], [])

    def test_someone_who_cannot_run_any_report_cannot_search(self):
        self.assertEqual(_as(self.nobody).get(reverse('report-recipients'), {'q': 'Local'}).status_code, 403)

    def test_a_very_short_search_returns_nothing(self):
        self.assertEqual(_as(self.hr).get(reverse('report-recipients'), {'q': 'L'}).data['data']['results'], [])


class CsvRenderingTests(TestCase):
    def test_a_utf8_bom_leads_the_file_and_every_cell_is_quoted(self):
        out = render_csv(ReportData(['A'], [['x,y']]))
        self.assertTrue(out.startswith(b'\xef\xbb\xbf'))
        self.assertIn('"x,y"', out.decode('utf-8'))
        self.assertEqual(io.BytesIO(out).read(3), b'\xef\xbb\xbf')

"""Employees through the real API: filters, AND/OR, scope by role, sensitive fields, pagination, bad requests."""
from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import EmployeeProfile
from apps.global_search.test_support import (
    all_of, any_of, build_world, client_for, leaf, make_branch, names, person, search,
)


class EmployeeSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.w = build_world()
        cls.admin = client_for(cls.w.admin)

    def employees(self, **kwargs):
        return search(self.admin, 'employees', **kwargs)

    # ── the examples from the brief ───────────────────────────────────────────────────────────────
    def test_female_and_male_employees(self):
        self.assertEqual(names(self.employees(filters=leaf('gender', 'eq', 'female'))), {'Anita Rao', 'Chitra Devi', 'Esha Verma'})
        self.assertEqual(names(self.employees(filters=leaf('gender', 'eq', 'male'))), {'Bharat Kumar', 'Deepak Shah'})

    def test_gender_female_and_department_and_branch(self):
        tree = all_of(leaf('gender', 'eq', 'female'), leaf('department', 'eq', 'Development'), leaf('branch', 'eq', 'Hyderabad'))
        self.assertEqual(names(self.employees(filters=tree)), {'Anita Rao'})

    def test_or_groups_and_nesting(self):
        either = any_of(leaf('department', 'eq', 'Sales'), leaf('designation', 'eq', 'Developer'))
        self.assertEqual(len(names(self.employees(filters=either))), 5)
        nested = all_of(leaf('gender', 'eq', 'female'), any_of(leaf('branch', 'eq', 'Bengaluru'), leaf('department', 'eq', 'Development')))
        self.assertEqual(names(self.employees(filters=nested)), {'Anita Rao', 'Esha Verma'})

    # ── operators ─────────────────────────────────────────────────────────────────────────────────
    def test_text_operators(self):
        run = lambda operator, value: names(self.employees(filters=all_of(leaf('designation', 'eq', 'Developer'), leaf('full_name', operator, value))))
        self.assertEqual(run('starts_with', 'an'), {'Anita Rao'})
        self.assertEqual(run('ends_with', 'shah'), {'Deepak Shah'})
        self.assertEqual(run('contains', 'har'), {'Bharat Kumar'})
        self.assertEqual(run('not_contains', 'a'), set())
        self.assertEqual(run('ne', 'Anita Rao'), {'Bharat Kumar', 'Deepak Shah'})
        self.assertEqual(run('in', ['Anita Rao', 'Deepak Shah']), {'Anita Rao', 'Deepak Shah'})

    def test_multiple_selection_and_does_not_equal(self):
        self.assertEqual(len(names(self.employees(filters=leaf('department', 'in', ['Sales', 'Development'])))), 5)
        self.assertNotIn('Chitra Devi', names(self.employees(filters=leaf('department', 'ne', 'Sales'))))
        self.assertEqual(names(self.employees(filters=leaf('gender', 'in', ['male']))), {'Bharat Kumar', 'Deepak Shah'})

    def test_empty_and_not_empty(self):
        EmployeeProfile.objects.filter(user=self.w.anita).update(current_state='')
        type(self.w.anita).objects.filter(pk=self.w.anita.pk).update(work_location='Gachibowli')
        self.assertEqual(names(self.employees(filters=leaf('work_location', 'is_not_empty'))), {'Anita Rao'})
        empty = names(self.employees(filters=leaf('work_location', 'is_empty')))
        self.assertNotIn('Anita Rao', empty)
        self.assertIn('Bharat Kumar', empty)

    def test_dates_before_after_between(self):
        type(self.w.anita).objects.filter(pk=self.w.anita.pk).update(date_of_joining=date(2024, 1, 10))
        type(self.w.bharat).objects.filter(pk=self.w.bharat.pk).update(date_of_joining=date(2025, 6, 1))
        self.assertEqual(names(self.employees(filters=leaf('date_of_joining', 'between', ['2024-01-01', '2024-12-31']))), {'Anita Rao'})
        self.assertEqual(names(self.employees(filters=leaf('date_of_joining', 'after', '2024-12-31'))), {'Bharat Kumar'})
        before = names(self.employees(filters=leaf('date_of_joining', 'before', '2021-01-01')))
        self.assertNotIn('Anita Rao', before)
        self.assertIn('Chitra Devi', before)

    def test_boolean_and_choice(self):
        type(self.w.esha).objects.filter(pk=self.w.esha.pk).update(is_active=False)
        self.assertEqual(names(self.employees(filters=leaf('is_active', 'eq', False))), {'Esha Verma'})
        self.assertNotIn('Esha Verma', names(self.employees(filters=leaf('is_active', 'eq', True))))

    def test_branch_matches_by_name_ignoring_case_and_in_lists(self):
        self.assertEqual(names(self.employees(filters=all_of(leaf('branch', 'eq', 'bengaluru'), leaf('gender', 'eq', 'female')))), {'Esha Verma'})
        self.assertEqual(len(names(self.employees(filters=all_of(leaf('branch', 'in', ['Bengaluru']), leaf('designation', 'eq', 'Executive'))))), 1)
        self.assertEqual(names(self.employees(filters=all_of(leaf('branch', 'contains', 'engal'), leaf('gender', 'eq', 'male')))), {'Deepak Shah'})

    # ── the text box ──────────────────────────────────────────────────────────────────────────────
    def test_free_text_searches_name_id_email_designation_and_needs_every_word(self):
        self.assertEqual(names(self.employees(q='anita')), {'Anita Rao'})
        self.assertEqual(names(self.employees(q='EMP002')), {'Bharat Kumar'})
        self.assertEqual(names(self.employees(q='chitra@gs.test')), {'Chitra Devi'})
        self.assertEqual(names(self.employees(q='rao developer')), {'Anita Rao'})
        self.assertEqual(names(self.employees(q='rao executive')), set())

    def test_the_result_says_which_fields_matched(self):
        row = self.employees(q='anita').data['data']['results'][0]
        self.assertIn('Name', row['matched'])
        by_id = self.employees(q='EMP001').data['data']['results'][0]
        self.assertEqual(by_id['matched'], ['Employee ID'])

    def test_text_and_filters_combine(self):
        self.assertEqual(names(self.employees(q='a', filters=leaf('gender', 'eq', 'male'))), {'Bharat Kumar', 'Deepak Shah'})

    def test_a_result_row_carries_only_the_declared_keys(self):
        row = self.employees(q='anita').data['data']['results'][0]
        self.assertEqual(set(row), {'id', 'title', 'subtitle', 'meta', 'url', 'matched'})
        self.assertNotIn('Date of birth', row['meta'])

    # ── who sees whom ─────────────────────────────────────────────────────────────────────────────
    def test_branch_hr_sees_only_their_own_branch(self):
        hr = client_for(self.w.hr)
        everyone = names(search(hr, 'employees', page_size=50))
        self.assertIn('Anita Rao', everyone)
        self.assertNotIn('Deepak Shah', everyone)
        self.assertNotIn('Esha Verma', everyone)
        self.assertEqual(names(search(hr, 'employees', q='deepak')), set())
        # counts and filtered results do not leak the other branch either
        self.assertEqual(search(hr, 'employees', q='deepak').data['data']['count'], 0)
        self.assertEqual(names(search(hr, 'employees', filters=leaf('gender', 'eq', 'female'))), {'Anita Rao', 'Chitra Devi'})

    def test_a_team_manager_sees_only_direct_reports(self):
        self.assertEqual(names(search(client_for(self.w.manager), 'employees', page_size=50)), {'Anita Rao', 'Bharat Kumar'})

    def test_a_viewer_without_employee_access_cannot_search_employees_at_all(self):
        plain = client_for(self.w.anita)
        response = search(plain, 'employees', q='bharat')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['message'], search(plain, 'no_such_module').data['message'])   # a closed area looks like a missing one
        keys = {module['key'] for module in plain.get(reverse('global-search-registry')).data['data']['modules']}
        self.assertNotIn('employees', keys)
        grouped = plain.get(reverse('global-search'), {'q': 'bharat'}).data['data']
        self.assertNotIn('employees', {group['module'] for group in grouped['groups']})

    def test_a_viewer_with_no_branch_and_no_team_sees_nobody(self):
        lone = person('lone@gs.test', 'Lone Viewer', 'EMP950', branch=self.w.hyd, perms=['employees.view'])
        type(lone).objects.filter(pk=lone.pk).update(branch='', branch_fk=None)
        lone.refresh_from_db()
        self.assertEqual(names(search(client_for(lone), 'employees')), set())

    def test_a_new_branch_is_not_visible_to_another_branchs_hr(self):
        other = make_branch('CH01', 'Chennai')
        person('ch@gs.test', 'Chennai Person', 'EMP960', branch=other, gender='female')
        self.assertNotIn('Chennai Person', names(search(client_for(self.w.hr), 'employees', q='chennai')))
        self.assertIn('Chennai Person', names(self.employees(q='chennai')))

    # ── sensitive and never-searchable fields ─────────────────────────────────────────────────────
    def test_personal_fields_need_the_sensitive_permission(self):
        EmployeeProfile.objects.filter(user=self.w.anita).update(date_of_birth=date(1990, 5, 17))
        tree = leaf('date_of_birth', 'eq', '1990-05-17')
        denied = search(client_for(self.w.hr), 'employees', filters=tree)
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(names(self.employees(filters=tree)), {'Anita Rao'})
        hr_fields = {field['key'] for module in client_for(self.w.hr).get(reverse('global-search-registry')).data['data']['modules']
                     if module['key'] == 'employees' for field in module['fields']}
        admin_fields = {field['key'] for module in self.admin.get(reverse('global-search-registry')).data['data']['modules']
                        if module['key'] == 'employees' for field in module['fields']}
        self.assertNotIn('date_of_birth', hr_fields)
        self.assertIn('date_of_birth', admin_fields)

    def test_encrypted_and_security_fields_can_never_be_used(self):
        for key in ('pan_number', 'aadhaar_number', 'account_number', 'ifsc_code', 'passport_number', 'password', 'last_login_ip', 'failed_login_attempts'):
            response = self.employees(filters=leaf(key, 'eq', 'x'))
            self.assertEqual(response.status_code, 400, key)

    def test_the_registry_never_exposes_database_paths(self):
        registry = self.admin.get(reverse('global-search-registry')).data['data']
        for module in registry['modules']:
            for field in module['fields']:
                self.assertEqual(set(field), {'key', 'label', 'type', 'searchable', 'choices', 'operators'})
                self.assertTrue(field['operators'])

    # ── pages ─────────────────────────────────────────────────────────────────────────────────────
    def test_pagination_over_many_employees(self):
        for number in range(30):
            person(f'bulk{number}@gs.test', f'Bulk Person {number:02d}', f'EMP1{number:03d}', branch=self.w.blr, gender='male')
        first = self.employees(q='bulk person', page=1, page_size=10)
        data = first.data['data']
        self.assertEqual((data['count'], data['total_pages'], len(data['results'])), (30, 3, 10))
        second = names(self.employees(q='bulk person', page=2, page_size=10))
        self.assertTrue(second.isdisjoint(names(first)))
        self.assertEqual(self.employees(q='bulk person', page_size=500).data['data']['page_size'], 50)   # capped
        self.assertEqual(len(names(self.employees(q='bulk person', page=3, page_size=10))), 10)
        self.assertEqual(self.employees(q='bulk person', page='x', page_size='y').data['data']['page'], 1)

    # ── bad requests ──────────────────────────────────────────────────────────────────────────────
    def test_bad_filter_requests_are_refused_with_a_message(self):
        bad = [
            leaf('gender', 'eq', 'robot'), leaf('gender', 'contains', 'fem'), leaf('nope', 'eq', 'x'), leaf('date_of_joining', 'after', 'yesterday'),
            {'op': 'maybe', 'items': [leaf('gender', 'eq', 'male')]}, {'op': 'and', 'items': []}, 'just a string',
        ]
        for tree in bad:
            response = self.employees(filters=tree)
            self.assertEqual(response.status_code, 400, tree)
            self.assertEqual(response.data['status'], 'error')
            self.assertTrue(response.data['message'])

    def test_malformed_and_oversized_filters(self):
        url = reverse('global-search-module', kwargs={'module': 'employees'})
        self.assertEqual(self.admin.get(url, {'filters': '{not json'}).status_code, 400)
        self.assertEqual(self.admin.get(url, {'filters': 'x' * 9000}).status_code, 400)
        self.assertEqual(self.admin.get(url, {'q': 'x' * 101}).status_code, 400)

    def test_post_takes_the_same_request_as_a_body(self):
        url = reverse('global-search-module', kwargs={'module': 'employees'})
        body = {'q': '', 'filters': leaf('gender', 'eq', 'male')}
        self.assertEqual({row['title'] for row in self.admin.post(url, body, format='json').data['data']['results']}, {'Bharat Kumar', 'Deepak Shah'})

    def test_an_anonymous_visitor_is_refused(self):
        for url in (reverse('global-search'), reverse('global-search-registry'), reverse('global-search-module', kwargs={'module': 'employees'})):
            self.assertIn(APIClient().get(url).status_code, (401, 403))

    def test_grouped_search_needs_two_characters_and_groups_by_module(self):
        url = reverse('global-search')
        self.assertEqual(self.admin.get(url, {'q': 'a'}).status_code, 400)
        data = self.admin.get(url, {'q': 'anita'}).data['data']
        self.assertEqual(data['total'], 1)
        self.assertEqual([group['module'] for group in data['groups']], ['employees'])
        self.assertEqual(self.admin.get(url, {'q': 'anita', 'modules': 'leave'}).data['data']['groups'], [])

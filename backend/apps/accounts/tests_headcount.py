"""UAT-039 / UAT-040: one headcount definition. Buckets add up to the total, the Admin account is not an employee, and every screen agrees."""
import datetime

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import User
from apps.accounts.services_headcount import current_workforce, get_headcount
from apps.branch.models import Branch, City, State
from apps.branch.utils import branch_employee_counts
from apps.hrms.models import SEP_APPROVED, SeparationRequest

TODAY = datetime.date.today()


def _branch(name, code):
    state, _ = State.objects.get_or_create(code='TG', defaults={'name': 'Telangana'})
    city, _ = City.objects.get_or_create(name='Hyderabad', state=state)
    return Branch.objects.create(
        branch_code=code, branch_name=name, address=f'{name} Office, Hyderabad', state=state, city=city, allowed_radius_meters=150,
    )


def _employee(email, code, branch, onboarding=User.ONBOARDING_COMPLETE, employment_status=User.EMPLOYMENT_STATUS_CONFIRMED, **extra):
    return make_user(email, employee_id=code, branch=branch, onboarding_status=onboarding, employment_status=employment_status, **extra)


class HeadcountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.kondapur = _branch('Kondapur', 'KDP01')
        self.mulugu = _branch('Mulugu', 'MLG01')
        # The system admin account: logs in, but has no employee record.
        make_user('system-admin@test.com', role=make_role('hc_sysadmin', permission_codenames=['employees.view', 'settings.edit', 'branches.view']))
        _employee('active1@test.com', 'EMPHC01', 'Kondapur')
        _employee('probation@test.com', 'EMPHC02', 'Kondapur', employment_status=User.EMPLOYMENT_STATUS_PROBATION)
        _employee('onboarding@test.com', 'EMPHC03', 'Mulugu', onboarding=User.ONBOARDING_PENDING)
        notice = _employee('notice@test.com', 'EMPHC04', 'Mulugu')
        SeparationRequest.objects.create(
            employee=notice, separation_type='resignation', request_date=TODAY, proposed_last_working_day=TODAY + datetime.timedelta(days=20),
            status=SEP_APPROVED,
        )
        _employee('gone@test.com', 'EMPHC05', 'Kondapur', is_active=False)

    def test_admin_without_an_employee_record_is_not_counted(self):
        self.assertEqual(current_workforce().count(), 4)
        self.assertFalse(current_workforce().filter(email='system-admin@test.com').exists())

    def test_buckets_add_up_and_probation_is_part_of_active(self):
        counts = get_headcount()
        self.assertEqual(counts['total'], 4)
        self.assertEqual(counts['active'] + counts['onboarding'] + counts['notice_period'], counts['total'])
        self.assertEqual((counts['active'], counts['onboarding'], counts['notice_period']), (2, 1, 1))
        self.assertEqual(counts['probation'], 1)  # a subset of the 2 active, not an extra bucket
        self.assertEqual(counts['exited'], 1)

    def test_branch_filter_gives_that_branchs_numbers_and_they_sum_to_the_total(self):
        kondapur, mulugu = get_headcount(branch='Kondapur'), get_headcount(branch='mulugu')
        self.assertEqual((kondapur['total'], mulugu['total']), (2, 2))
        self.assertEqual(kondapur['total'] + mulugu['total'], get_headcount()['total'])

    def test_notice_period_ends_after_the_last_working_day(self):
        later = TODAY + datetime.timedelta(days=60)
        counts = get_headcount(as_of=later)
        self.assertEqual(counts['notice_period'], 0)

    def test_branch_cards_count_the_same_people_as_the_headcount(self):
        by_branch = branch_employee_counts()
        self.assertEqual(by_branch[self.kondapur.pk], 2)
        self.assertEqual(by_branch[self.mulugu.pk], 2)
        self.assertEqual(sum(by_branch.values()), get_headcount()['total'])

    def test_branch_stats_total_workforce_matches(self):
        client = APIClient()
        client.force_authenticate(user=User.objects.get(email='system-admin@test.com'))
        response = client.get(reverse('branch-stats'))
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()['data']['total_employees'], get_headcount()['total'])


class HeadcountEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        _branch('Kondapur', 'KDP01')
        role = make_role('hc_viewer', permission_codenames=['employees.view', 'settings.edit'])
        self.viewer = make_user('hc-viewer@test.com', role=role)  # no employee id: the viewer is an admin, not counted
        _employee('a@test.com', 'EMPHE01', 'Kondapur')
        _employee('b@test.com', 'EMPHE02', 'Kondapur', employment_status=User.EMPLOYMENT_STATUS_PROBATION)
        _employee('c@test.com', 'EMPHE03', 'Kondapur', onboarding=User.ONBOARDING_PENDING)
        self.client = APIClient()
        self.client.force_authenticate(user=self.viewer)

    def test_summary_endpoint_and_directory_kpis_agree(self):
        summary = self.client.get(reverse('employee-headcount')).json()['data']
        stats = self.client.get(reverse('employee-stats')).json()['data']
        for key in ('total', 'active', 'probation', 'onboarding', 'notice_period'):
            self.assertEqual(summary[key], stats[key], key)
        self.assertEqual(stats['total'], stats['active'] + stats['onboarding'] + stats['notice_period'])
        self.assertEqual(stats['active'], 2)  # the probation employee is Active

    def test_directory_filtered_by_branch_matches_the_summary(self):
        summary = self.client.get(reverse('employee-headcount'), {'branch': 'Kondapur'}).json()['data']
        listing = self.client.get(reverse('employee-list-create'), {'branch': 'Kondapur'}).json()['data']
        self.assertEqual(summary['total'], 3)
        self.assertEqual(listing['count'], 3)

    def test_probation_counts_as_active_and_the_table_filters_return_the_kpi_numbers(self):
        stats = self.client.get(reverse('employee-stats')).json()['data']
        for status_value in ('active', 'onboarding'):
            listing = self.client.get(reverse('employee-list-create'), {'status': status_value}).json()['data']
            self.assertEqual(listing['count'], stats[status_value], status_value)
        self.assertEqual(stats['active'], 2)       # the confirmed AND the probation employee
        self.assertEqual(stats['probation'], 1)    # shown inside Active, not as a separate bucket
        self.assertEqual(stats['total'], stats['active'] + stats['onboarding'] + stats['notice_period'])

    def test_bad_as_of_is_explained(self):
        response = self.client.get(reverse('employee-headcount'), {'as_of': '31/12/2026'})
        self.assertEqual(response.status_code, 400)

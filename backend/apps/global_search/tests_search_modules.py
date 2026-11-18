"""Attendance, leave, work from home, announcements, assets and organisation through the real API.

A module is only listed as supported once it is searched, filtered and scoped here."""
from datetime import date, time
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.factories import make_permission
from apps.accounts.models import BaselinePermission, CompanyAsset, OrgUnit, Position
from apps.announcements.models import Announcement
from apps.attendance.models import AttendanceRecord
from apps.global_search.registry import all_modules
from apps.global_search.test_support import all_of, any_of, build_world, client_for, leaf, names, search
from apps.hrms.models import REQ_APPROVED, REQ_PENDING, REQ_REJECTED, LeaveRequest, WorkFromHomeRequest

NOV = date(2026, 11, 2)


class AttendanceSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.w = build_world()
        AttendanceRecord.objects.create(employee=cls.w.anita, date=NOV, status='present', first_punch_in=time(9, 0), last_punch_out=time(18, 0), total_working_minutes=540)
        AttendanceRecord.objects.create(employee=cls.w.bharat, date=NOV, status='half_day', first_punch_in=time(9, 40), last_punch_out=time(13, 30), total_working_minutes=230, is_late=True)
        AttendanceRecord.objects.create(employee=cls.w.chitra, date=date(2026, 11, 3), status='absent')
        AttendanceRecord.objects.create(employee=cls.w.deepak, date=NOV, status='present', first_punch_in=time(10, 5), last_punch_out=time(19, 0), total_working_minutes=530, overtime_minutes=30)

    def employees_of(self, viewer, **kwargs):
        return names(search(client_for(viewer), 'attendance', **kwargs), 'title')

    def test_status_date_time_and_number_filters(self):
        admin = client_for(self.w.admin)
        run = lambda tree: names(search(admin, 'attendance', filters=tree))
        self.assertEqual(run(leaf('status', 'eq', 'half_day')), {'Bharat Kumar'})
        self.assertEqual(run(all_of(leaf('status', 'eq', 'present'), leaf('date', 'between', ['2026-11-01', '2026-11-02']))), {'Anita Rao', 'Deepak Shah'})
        self.assertEqual(run(leaf('first_punch_in', 'before', '09:30')), {'Anita Rao'})
        self.assertEqual(run(leaf('last_punch_out', 'after', '18:30')), {'Deepak Shah'})
        # an absent day stores 0 minutes, so it is under 300 too; narrow by status to isolate the half day
        self.assertEqual(run(leaf('total_working_minutes', 'lt', 300)), {'Bharat Kumar', 'Chitra Devi'})
        self.assertEqual(run(all_of(leaf('total_working_minutes', 'lt', 300), leaf('status', 'ne', 'absent'))), {'Bharat Kumar'})
        self.assertEqual(run(leaf('overtime_minutes', 'gt', 0)), {'Deepak Shah'})
        self.assertEqual(run(leaf('is_late', 'eq', True)), {'Bharat Kumar'})
        self.assertEqual(run(any_of(leaf('status', 'eq', 'absent'), leaf('status', 'eq', 'half_day'))), {'Chitra Devi', 'Bharat Kumar'})
        self.assertEqual(run(leaf('date', 'after', '2026-11-02')), {'Chitra Devi'})

    def test_records_with_no_punch_are_found_by_empty(self):
        admin = client_for(self.w.admin)
        self.assertEqual(names(search(admin, 'attendance', filters=leaf('first_punch_in', 'is_empty'))), {'Chitra Devi'})
        self.assertEqual(len(names(search(admin, 'attendance', filters=leaf('first_punch_in', 'is_not_empty')))), 3)

    def test_free_text_finds_by_employee_name_and_id(self):
        self.assertEqual(self.employees_of(self.w.admin, q='deepak'), {'Deepak Shah'})
        self.assertEqual(self.employees_of(self.w.admin, q='EMP003'), {'Chitra Devi'})

    def test_everyone_sees_their_own_days_and_nobody_elses_without_attendance_access(self):
        self.assertEqual(self.employees_of(self.w.anita), {'Anita Rao'})
        self.assertEqual(self.employees_of(self.w.bharat, q='anita'), set())

    def test_managers_see_their_team_and_branch_hr_their_branch(self):
        self.assertEqual(self.employees_of(self.w.manager), {'Anita Rao', 'Bharat Kumar'})
        self.assertEqual(self.employees_of(self.w.hr), {'Anita Rao', 'Bharat Kumar', 'Chitra Devi'})
        self.assertEqual(self.employees_of(self.w.admin), {'Anita Rao', 'Bharat Kumar', 'Chitra Devi', 'Deepak Shah'})

    def test_counts_do_not_leak_other_branches(self):
        self.assertEqual(search(client_for(self.w.hr), 'attendance', filters=leaf('status', 'eq', 'present')).data['data']['count'], 1)


class LeaveSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.w = build_world()
        common = dict(duration='full_day', total_days=Decimal('1'), reason='private medical reason')
        cls.pending = LeaveRequest.objects.create(employee=cls.w.anita, leave_type='casual', start_date=date(2026, 12, 1), end_date=date(2026, 12, 1), status=REQ_PENDING, l1_approver=cls.w.manager, **common)
        cls.approved = LeaveRequest.objects.create(employee=cls.w.bharat, leave_type='sick', start_date=date(2026, 11, 10), end_date=date(2026, 11, 11), status=REQ_APPROVED, **{**common, 'total_days': Decimal('2')})
        cls.rejected = LeaveRequest.objects.create(employee=cls.w.deepak, leave_type='casual', start_date=date(2026, 11, 20), end_date=date(2026, 11, 20), status=REQ_REJECTED, **common)

    def seen_by(self, viewer, **kwargs):
        return names(search(client_for(viewer), 'leave', **kwargs))

    def test_pending_approved_and_rejected(self):
        admin = client_for(self.w.admin)
        for status, who in ((REQ_PENDING, 'Anita Rao'), (REQ_APPROVED, 'Bharat Kumar'), (REQ_REJECTED, 'Deepak Shah')):
            self.assertEqual(names(search(admin, 'leave', filters=leaf('status', 'eq', status))), {who})
        self.assertEqual(names(search(admin, 'leave', filters=leaf('status', 'in', [REQ_PENDING, REQ_REJECTED]))), {'Anita Rao', 'Deepak Shah'})
        self.assertEqual(names(search(admin, 'leave', filters=leaf('status', 'ne', REQ_PENDING))), {'Bharat Kumar', 'Deepak Shah'})

    def test_type_dates_and_days(self):
        admin = client_for(self.w.admin)
        run = lambda tree: names(search(admin, 'leave', filters=tree))
        self.assertEqual(run(leaf('leave_type', 'eq', 'sick')), {'Bharat Kumar'})
        self.assertEqual(run(leaf('start_date', 'between', ['2026-11-01', '2026-11-30'])), {'Bharat Kumar', 'Deepak Shah'})
        self.assertEqual(run(leaf('total_days', 'gt', 1)), {'Bharat Kumar'})
        self.assertEqual(run(all_of(leaf('leave_type', 'eq', 'casual'), leaf('status', 'eq', REQ_PENDING))), {'Anita Rao'})
        self.assertEqual(run(leaf('is_lwp', 'eq', False)), {'Anita Rao', 'Bharat Kumar', 'Deepak Shah'})
        self.assertEqual(run(leaf('created_at', 'eq', timezone.localdate().isoformat())), {'Anita Rao', 'Bharat Kumar', 'Deepak Shah'})

    def test_an_employee_sees_only_their_own_requests(self):
        self.assertEqual(self.seen_by(self.w.anita), {'Anita Rao'})
        self.assertEqual(self.seen_by(self.w.chitra), set())

    def test_manager_hr_and_admin_scope(self):
        self.assertEqual(self.seen_by(self.w.manager), {'Anita Rao', 'Bharat Kumar'})
        self.assertEqual(self.seen_by(self.w.hr), {'Anita Rao', 'Bharat Kumar'})   # Hyderabad employees; not Bengaluru's
        self.assertEqual(self.seen_by(self.w.admin), {'Anita Rao', 'Bharat Kumar', 'Deepak Shah'})

    def test_the_private_reason_is_neither_searched_nor_filterable(self):
        self.assertEqual(self.seen_by(self.w.admin, q='medical'), set())
        response = search(client_for(self.w.admin), 'leave', filters=leaf('reason', 'contains', 'medical'))
        self.assertEqual(response.status_code, 400)
        self.assertNotIn('reason', str(search(client_for(self.w.admin), 'leave').data))


class WorkFromHomeSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.w = build_world()
        WorkFromHomeRequest.objects.create(employee=cls.w.anita, start_date=date(2026, 11, 5), end_date=date(2026, 11, 6), reason='r', location_label='Anita home', latitude=Decimal('17.4'), longitude=Decimal('78.4'), status=REQ_PENDING, l1_approver=cls.w.manager)
        WorkFromHomeRequest.objects.create(employee=cls.w.deepak, start_date=date(2026, 11, 9), end_date=date(2026, 11, 9), reason='r', location_label='Deepak flat', latitude=Decimal('12.9'), longitude=Decimal('77.6'), status=REQ_APPROVED)

    def test_filters_text_and_scope(self):
        admin = client_for(self.w.admin)
        self.assertEqual(names(search(admin, 'work_from_home', filters=leaf('status', 'eq', REQ_APPROVED))), {'Deepak Shah'})
        self.assertEqual(names(search(admin, 'work_from_home', q='flat')), {'Deepak Shah'})
        self.assertEqual(names(search(admin, 'work_from_home', filters=leaf('start_date', 'before', '2026-11-08'))), {'Anita Rao'})
        self.assertEqual(names(search(client_for(self.w.anita), 'work_from_home')), {'Anita Rao'})
        self.assertEqual(names(search(client_for(self.w.manager), 'work_from_home')), {'Anita Rao'})
        self.assertEqual(names(search(client_for(self.w.hr), 'work_from_home')), {'Anita Rao'})


class AnnouncementSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.w = build_world()
        Announcement.objects.create(title='Company picnic', body='Bring your family along', category='event', visibility='all')
        Announcement.objects.create(title='Hyderabad parking', body='New parking rules for the Hyderabad office', category='general', visibility='branch', target_branch=cls.w.hyd)
        Announcement.objects.create(title='Bengaluru lift repair', body='Lift is closed on Friday', category='urgent', visibility='branch', target_branch=cls.w.blr, is_pinned=True)

    def titles(self, viewer, **kwargs):
        return names(search(client_for(viewer), 'announcements', **kwargs))

    def test_people_see_company_wide_and_their_own_branch_only(self):
        self.assertEqual(self.titles(self.w.anita), {'Company picnic', 'Hyderabad parking'})
        self.assertEqual(self.titles(self.w.deepak), {'Company picnic', 'Bengaluru lift repair'})
        self.assertEqual(self.titles(self.w.anita, q='lift'), set())   # another branch's announcement cannot be found by text either

    def test_announcement_editors_see_everything(self):
        self.assertEqual(len(self.titles(self.w.admin)), 3)

    def test_text_and_filters(self):
        admin = client_for(self.w.admin)
        self.assertEqual(names(search(admin, 'announcements', q='family')), {'Company picnic'})
        self.assertEqual(names(search(admin, 'announcements', filters=leaf('category', 'eq', 'urgent'))), {'Bengaluru lift repair'})
        self.assertEqual(names(search(admin, 'announcements', filters=leaf('is_pinned', 'eq', True))), {'Bengaluru lift repair'})
        self.assertEqual(names(search(admin, 'announcements', filters=leaf('visibility', 'in', ['all', 'branch']))), {'Company picnic', 'Hyderabad parking', 'Bengaluru lift repair'})
        self.assertEqual(names(search(admin, 'announcements', filters=leaf('created_at', 'eq', timezone.localdate().isoformat()))), {'Company picnic', 'Hyderabad parking', 'Bengaluru lift repair'})
        self.assertEqual(names(search(admin, 'announcements', filters=leaf('title', 'starts_with', 'Hyder'))), {'Hyderabad parking'})


class AssetSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.w = build_world()
        CompanyAsset.objects.create(employee=cls.w.anita, asset_type='laptop', tag_number='LT-100')
        CompanyAsset.objects.create(employee=cls.w.deepak, asset_type='monitor', tag_number='MN-900')

    def tags(self, viewer, **kwargs):
        return names(search(client_for(viewer), 'assets', **kwargs), 'title')

    def test_own_assets_branch_hr_and_admin(self):
        self.assertEqual(len(self.tags(self.w.anita)), 1)
        self.assertEqual(self.tags(self.w.deepak, q='LT-100'), set())
        self.assertEqual(len(self.tags(self.w.hr)), 1)          # onboarding.edit: Hyderabad employees' assets only
        self.assertEqual(self.tags(self.w.manager), set())      # no onboarding.edit: the manager has no assets of their own
        self.assertEqual(len(self.tags(self.w.admin)), 2)

    def test_filters(self):
        admin = client_for(self.w.admin)
        self.assertEqual(len(names(search(admin, 'assets', filters=leaf('asset_type', 'eq', 'monitor')))), 1)
        self.assertEqual(len(names(search(admin, 'assets', filters=leaf('tag_number', 'starts_with', 'LT')))), 1)
        self.assertEqual(len(names(search(admin, 'assets', filters=leaf('returned_at', 'is_empty')))), 2)
        self.assertEqual(len(names(search(admin, 'assets', q='anita'))), 1)


class OrganisationSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.w = build_world()
        # The database already holds a real org chart, so these use names nothing else carries.
        unit = OrgUnit.objects.create(name='Zeta Division', code='ZTD')
        OrgUnit.objects.create(name='Zeta Labs', code='ZTL')
        Position.objects.create(org_unit=unit, title='Zeta Lead', grade='L3', is_chief=True)
        Position.objects.create(org_unit=unit, title='Zeta Intern', grade='L1')

    def test_branches_follow_the_company_codes_page(self):
        self.assertEqual(names(search(client_for(self.w.admin), 'branches')), {'Hyderabad', 'Bengaluru'})
        self.assertEqual(names(search(client_for(self.w.hr), 'branches')), {'Hyderabad'})
        self.assertEqual(search(client_for(self.w.anita), 'branches').status_code, 400)
        self.assertEqual(names(search(client_for(self.w.admin), 'branches', q='bengal')), {'Bengaluru'})
        self.assertEqual(names(search(client_for(self.w.admin), 'branches', filters=leaf('is_headquarter', 'eq', False))), {'Hyderabad', 'Bengaluru'})

    def test_org_units_and_positions_search_and_filters(self):
        admin = client_for(self.w.admin)
        self.assertEqual(names(search(admin, 'org_units', q='zeta')), {'Zeta Division', 'Zeta Labs'})
        self.assertEqual(names(search(admin, 'org_units', filters=all_of(leaf('code', 'starts_with', 'ZT'), leaf('code', 'ends_with', 'L')))), {'Zeta Labs'})
        self.assertEqual(names(search(admin, 'positions', q='zeta', filters=leaf('is_chief', 'eq', True))), {'Zeta Lead'})
        self.assertEqual(names(search(admin, 'positions', filters=leaf('org_unit', 'eq', 'Zeta Division'))), {'Zeta Lead', 'Zeta Intern'})
        self.assertEqual(names(search(admin, 'positions', q='intern zeta')), {'Zeta Intern'})

    def test_org_units_and_positions_need_the_org_chart_permission(self):
        # In this company org_chart.view is a baseline permission (everyone sees the org chart), so take it away to test the gate.
        BaselinePermission.objects.filter(permission__codename='org_chart.view').delete()
        for module in ('org_units', 'positions'):
            self.assertEqual(search(client_for(self.w.anita), module).status_code, 400)
            self.assertEqual(search(client_for(self.w.admin), module).status_code, 200)

    def test_with_the_baseline_everyone_may_search_the_org_chart(self):
        BaselinePermission.objects.get_or_create(permission=make_permission('org_chart.view'))
        self.assertIn('Zeta Division', names(search(client_for(self.w.anita), 'org_units', q='zeta')))


class RegistryCoverageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.w = build_world()

    def test_every_registered_module_answers_a_plain_search_and_a_filtered_one(self):
        admin = client_for(self.w.admin)
        for key, module in all_modules().items():
            self.assertEqual(search(admin, key).status_code, 200, key)
            text_field = next(spec for spec in module.fields if spec.searchable)
            response = search(admin, key, filters=leaf(text_field.key, 'contains', 'zz-no-such-value'))
            self.assertEqual((response.status_code, response.data['data']['count']), (200, 0), key)

    def test_the_registry_lists_only_what_the_viewer_may_use(self):
        BaselinePermission.objects.filter(permission__codename='org_chart.view').delete()   # baseline access is tested separately
        keys = lambda viewer: {m['key'] for m in client_for(viewer).get(reverse('global-search-registry')).data['data']['modules']}
        self.assertEqual(keys(self.w.anita), {'attendance', 'leave', 'work_from_home', 'announcements', 'assets'})
        self.assertEqual(keys(self.w.admin), set(all_modules()))
        self.assertEqual(keys(self.w.hr), {'employees', 'branches', 'attendance', 'leave', 'work_from_home', 'announcements', 'assets'})

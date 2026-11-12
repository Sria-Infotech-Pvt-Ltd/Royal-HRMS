"""The announcement card on the employee/manager dashboard (GET /api/dashboard/announcement/).

It used to return the single newest row of the whole table, whoever it was meant for: an employee could be shown another
branch's announcement, and the announcement actually posted for them stayed hidden behind it. It must apply the same audience rule
as the Announcements page (GET /api/announcements/)."""
from __future__ import annotations

import datetime

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import OrgUnit, Placement, Position, User
from apps.announcements.models import Announcement
from apps.branch.models import Branch, City, State

DASHBOARD_URL = '/api/dashboard/announcement/'
LIST_URL = '/api/announcements/'
_seq = [0]


def _n(prefix: str) -> str:
    _seq[0] += 1
    return f'{prefix}{_seq[0]:04d}'


def _branch() -> Branch:
    state = State.objects.create(name=_n('State'), code=_n('S')[:10])
    city = City.objects.create(name=_n('City'), state=state)
    return Branch.objects.create(branch_code=_n('BR'), branch_name=_n('Branch'), address='x', state=state, city=city)


def _employee(**extra) -> User:
    user = make_user(f'{_n("emp")}@example.com', employee_id=_n('ANN'), **extra)
    User.objects.filter(pk=user.pk).update(onboarding_status='complete')
    user.refresh_from_db()
    return user


def _place(user: User, unit: OrgUnit) -> None:
    position = Position.objects.create(org_unit=unit, title=_n('Seat'), grade='L1')
    Placement.objects.create(position=position, employee=user, effective_from=datetime.date(2020, 1, 1))


def _post(title: str, visibility: str = 'all', *, pinned: bool = False, branch: Branch | None = None, unit: OrgUnit | None = None) -> Announcement:
    return Announcement.objects.create(
        title=title, body='Body of ' + title, category='general', visibility=visibility, is_pinned=pinned,
        target_branch=branch, target_org_unit=unit,
    )


def _dashboard(user: User) -> dict | None:
    """The card's announcement, or None when there is nothing to show (the API answers an empty object then)."""
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get(DASHBOARD_URL)
    assert response.status_code == 200, response.content
    return response.json()['data'] or None


class DashboardAudienceTests(TestCase):
    def setUp(self):
        self.branch_a, self.branch_b = _branch(), _branch()
        self.in_a = _employee(branch=self.branch_a.branch_name)
        self.in_b = _employee(branch=self.branch_b.branch_name)

    def test_a_company_wide_announcement_reaches_everyone(self):
        _post('For everyone')
        self.assertEqual(_dashboard(self.in_a)['title'], 'For everyone')
        self.assertEqual(_dashboard(self.in_b)['title'], 'For everyone')

    def test_another_branchs_announcement_is_not_shown(self):
        _post('Branch A only', 'branch', branch=self.branch_a)
        self.assertEqual(_dashboard(self.in_a)['title'], 'Branch A only')
        self.assertIsNone(_dashboard(self.in_b))

    def test_a_newer_announcement_for_someone_else_does_not_hide_mine(self):
        """The reported case: the announcement posted for me is older than one meant for another branch."""
        _post('For everyone')
        _post('Branch A only', 'branch', branch=self.branch_a)           # newer, not for branch B
        self.assertEqual(_dashboard(self.in_b)['title'], 'For everyone')

    def test_department_announcements_follow_the_org_unit_and_its_sub_units(self):
        parent = OrgUnit.objects.create(name=_n('Dept'))
        child = OrgUnit.objects.create(name=_n('Team'), parent=parent)
        other = OrgUnit.objects.create(name=_n('Other'))
        in_child, in_other = _employee(), _employee()
        _place(in_child, child)
        _place(in_other, other)
        _post('Department news', 'department', unit=parent)
        self.assertEqual(_dashboard(in_child)['title'], 'Department news')       # a sub-unit belongs to its parent department
        self.assertIsNone(_dashboard(in_other))
        self.assertIsNone(_dashboard(_employee()))                                # no seat, so no department announcements

    def test_no_announcement_gives_an_empty_card(self):
        self.assertIsNone(_dashboard(self.in_a))


class DashboardOrderingTests(TestCase):
    def setUp(self):
        self.employee = _employee()

    def test_the_pinned_announcement_comes_first_and_the_card_says_how_many_more_there_are(self):
        _post('Old pinned', pinned=True)
        _post('Newer')
        _post('Newest')
        data = _dashboard(self.employee)
        self.assertEqual(data['title'], 'Old pinned')
        self.assertTrue(data['is_pinned'])
        self.assertEqual(data['more_count'], 2)                   # the card must not hide that newer ones exist

    def test_without_a_pin_the_newest_is_shown(self):
        _post('Older')
        _post('Newest')
        data = _dashboard(self.employee)
        self.assertEqual((data['title'], data['more_count']), ('Newest', 1))

    def test_more_count_only_counts_what_this_person_can_see(self):
        branch = _branch()
        _post('Visible')
        _post('Elsewhere', 'branch', branch=branch)
        self.assertEqual(_dashboard(self.employee)['more_count'], 0)


class DashboardMatchesTheListTests(TestCase):
    def test_the_dashboard_card_is_always_something_the_list_page_shows(self):
        branch_a, branch_b = _branch(), _branch()
        employee = _employee(branch=branch_b.branch_name)
        _post('All 1')
        _post('A only', 'branch', branch=branch_a)
        _post('B only', 'branch', branch=branch_b, pinned=True)
        _post('All 2')
        client = APIClient()
        client.force_authenticate(user=employee)
        listed = {row['title'] for row in client.get(LIST_URL).json()['data']['results']}
        self.assertEqual(listed, {'All 1', 'B only', 'All 2'})
        self.assertIn(_dashboard(employee)['title'], listed)


class AdminPostsThenEmployeeSeesTests(TestCase):
    def test_an_announcement_posted_through_the_api_appears_on_the_employee_dashboard(self):
        admin = make_user(
            'ann_admin@example.com', role=make_role('ann_admin', permission_codenames=['announcements.create', 'announcements.edit']),
            employee_id=_n('ANN'),
        )
        User.objects.filter(pk=admin.pk).update(onboarding_status='complete')
        employee = _employee()
        client = APIClient()
        client.force_authenticate(user=admin)
        response = client.post(LIST_URL, {'title': 'Office closed Friday', 'body': 'Please plan ahead.', 'category': 'general', 'visibility': 'all'}, format='json')
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(_dashboard(employee)['title'], 'Office closed Friday')

    def test_an_announcement_editor_sees_the_newest_one_like_the_list_page_does(self):
        editor = make_user('ann_editor@example.com', role=make_role('ann_editor', permission_codenames=['announcements.edit']), employee_id=_n('ANN'))
        User.objects.filter(pk=editor.pk).update(onboarding_status='complete')
        branch = _branch()
        _post('Older for all')
        _post('Newest for a branch', 'branch', branch=branch)
        self.assertEqual(_dashboard(editor)['title'], 'Newest for a branch')


class OpenFromTheBellTests(TestCase):
    """What the bell link lands on: the announcement's detail endpoint. A person it was sent to opens it and its bell item is marked
    read; a person outside its audience cannot open it (the link then says it is not available)."""

    def _bell_item(self, user: User, announcement: Announcement):
        from apps.notifications.models import Notification
        return Notification.objects.get(user=user, module='announcement', reference_id=str(announcement.id))

    def _open(self, user: User, announcement: Announcement):
        client = APIClient()
        client.force_authenticate(user=user)
        return client.get(f'{LIST_URL}{announcement.id}/')

    def test_a_company_wide_announcement_opens_and_clears_its_bell_item(self):
        employee = _employee()
        announcement = _post('Holiday on Monday')
        bell = self._bell_item(employee, announcement)
        self.assertEqual(bell.reference_id, str(announcement.id))                  # what the bell link is built from
        self.assertFalse(bell.is_read)
        response = self._open(employee, announcement)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['data']['title'], 'Holiday on Monday')
        bell.refresh_from_db()
        self.assertTrue(bell.is_read)

    def test_a_branch_announcement_opens_for_that_branch_and_is_closed_to_others(self):
        branch_a, branch_b = _branch(), _branch()
        in_a, in_b = _employee(branch=branch_a.branch_name), _employee(branch=branch_b.branch_name)
        announcement = _post('Branch A notice', 'branch', branch=branch_a)
        from apps.notifications.models import Notification
        self.assertTrue(Notification.objects.filter(user=in_a, reference_id=str(announcement.id)).exists())
        self.assertFalse(Notification.objects.filter(user=in_b, reference_id=str(announcement.id)).exists())   # no bell item for them
        self.assertEqual(self._open(in_a, announcement).status_code, 200)
        self.assertEqual(self._open(in_b, announcement).status_code, 404)

    def test_a_department_announcement_opens_for_the_department(self):
        unit = OrgUnit.objects.create(name=_n('Dept'))
        member, outsider = _employee(), _employee()
        _place(member, unit)
        announcement = _post('Department notice', 'department', unit=unit)
        self._bell_item(member, announcement)
        self.assertEqual(self._open(member, announcement).status_code, 200)
        self.assertEqual(self._open(outsider, announcement).status_code, 404)

    def test_a_deleted_announcement_is_not_found(self):
        employee = _employee()
        announcement = _post('Short lived')
        announcement_id = announcement.id
        announcement.delete()
        client = APIClient()
        client.force_authenticate(user=employee)
        self.assertEqual(client.get(f'{LIST_URL}{announcement_id}/').status_code, 404)

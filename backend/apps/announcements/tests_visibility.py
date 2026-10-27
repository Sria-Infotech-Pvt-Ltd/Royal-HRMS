"""
Dashboard "Latest Announcement" banner and the announcement detail endpoint
(used by the dashboard View modal) only return posts the user may see:
company-wide posts, or posts targeted at the user's own branch / department.
"""
from __future__ import annotations

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import Department
from apps.announcements.models import Announcement
from apps.branch.models import Branch, City, State
from config.test_runner import TEST_COMPANY_CODE

_BANNER = '/api/dashboard/announcement/'


def _login(client, email):
    resp = client.post(reverse('login'), {'company_code': TEST_COMPANY_CODE, 'email': email,
                                          'password': 'TestPass123!'}, format='json')
    assert resp.status_code == 200, resp.data


class AnnouncementVisibilityTests(TestCase):
    def setUp(self):
        cache.clear()
        state = State.objects.create(name='VisState', code='VS1')
        city = City.objects.create(name='VisCity', state=state)
        self.branch_a = Branch.objects.create(branch_code='VSA', branch_name='VisBranchA', status=Branch.STATUS_ACTIVE,
                                              state=state, city=city)
        self.branch_b = Branch.objects.create(branch_code='VSB', branch_name='VisBranchB', status=Branch.STATUS_ACTIVE,
                                              state=state, city=city)
        self.dept = Department.objects.create(name='VisDept')
        emp_role = make_role('vis_emp')
        self.emp_a = make_user('vis.a@test.com', role=emp_role, branch=self.branch_a.branch_name, department='Other')
        self.emp_b = make_user('vis.b@test.com', role=emp_role, branch=self.branch_b.branch_name,
                               department=self.dept.name)
        editor_role = make_role('vis_editor', permission_codenames=['announcements.edit'])
        self.editor = make_user('vis.ed@test.com', role=editor_role, branch=self.branch_a.branch_name)

    def _post(self, title, **over):
        fields = dict(title=title, body=f'{title} body\nsecond line', category=Announcement.CATEGORY_GENERAL,
                      visibility=Announcement.VISIBILITY_ALL)
        fields.update(over)
        return Announcement.objects.create(**fields)

    def _client(self, user):
        api = APIClient()
        _login(api, user.email)
        return api

    def test_banner_skips_posts_targeted_at_other_branches(self):
        everyone = self._post('Company-wide')
        self._post('Branch B only', visibility=Announcement.VISIBILITY_BRANCH, target_branch=self.branch_b)  # newest
        # Branch A employee: the newest post is for branch B, so they get the company-wide one.
        data = self._client(self.emp_a).get(_BANNER).data['data']
        self.assertEqual((data['id'], data['title']), (everyone.id, 'Company-wide'))
        # Branch B employee sees the branch post.
        self.assertEqual(self._client(self.emp_b).get(_BANNER).data['data']['title'], 'Branch B only')

    def test_banner_respects_department_targeting_and_editors_see_all(self):
        self._post('Company-wide')
        dept_post = self._post('Dept only', visibility=Announcement.VISIBILITY_DEPARTMENT, target_department=self.dept)
        self.assertEqual(self._client(self.emp_b).get(_BANNER).data['data']['id'], dept_post.id)
        self.assertEqual(self._client(self.emp_a).get(_BANNER).data['data']['title'], 'Company-wide')
        self.assertEqual(self._client(self.editor).get(_BANNER).data['data']['id'], dept_post.id)

    def test_banner_returns_none_when_nothing_is_visible(self):
        self._post('Branch B only', visibility=Announcement.VISIBILITY_BRANCH, target_branch=self.branch_b)
        resp = self._client(self.emp_a).get(_BANNER)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('id', resp.data['data'])          # empty payload ({}), as for "no announcements"

    def test_banner_response_shape_unchanged(self):
        post = self._post('Shape', is_pinned=True)
        data = self._client(self.emp_a).get(_BANNER).data['data']
        self.assertEqual(set(data), {'id', 'title', 'body', 'category', 'visibility', 'is_pinned', 'posted_by',
                                     'created_at'})
        self.assertEqual((data['id'], data['body'], data['is_pinned']), (post.id, 'Shape body\nsecond line', True))

    def test_detail_for_view_modal_returns_full_post_only_when_visible(self):
        own = self._post('Branch A post', visibility=Announcement.VISIBILITY_BRANCH, target_branch=self.branch_a)
        other = self._post('Branch B post', visibility=Announcement.VISIBILITY_BRANCH, target_branch=self.branch_b)
        api = self._client(self.emp_a)
        resp = api.get(reverse('announcement-detail', kwargs={'pk': own.pk}))
        self.assertEqual(resp.status_code, 200)
        data = resp.data['data']
        self.assertEqual((data['title'], data['body'], data['target_branch_name']),
                         ('Branch A post', 'Branch A post body\nsecond line', 'VisBranchA'))
        self.assertEqual(api.get(reverse('announcement-detail', kwargs={'pk': other.pk})).status_code, 404)
        self.assertEqual(api.get(reverse('announcement-detail', kwargs={'pk': 999999})).status_code, 404)

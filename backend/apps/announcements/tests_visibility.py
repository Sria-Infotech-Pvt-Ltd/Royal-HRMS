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


class BannerAndViewAllTests(TestCase):
    """Banner: latest eligible pinned post, else latest eligible post. View All: every eligible post."""

    def setUp(self):
        import datetime
        from django.utils import timezone
        cache.clear()
        state = State.objects.create(name='BAState', code='BA1')
        city = City.objects.create(name='BACity', state=state)
        self.sury = Branch.objects.create(branch_code='BAS', branch_name='Suryapet', status=Branch.STATUS_ACTIVE,
                                          state=state, city=city)
        self.hyd = Branch.objects.create(branch_code='BAH', branch_name='Hyderabad', status=Branch.STATUS_ACTIVE,
                                         state=state, city=city)
        role = make_role('ba_employee')                       # no announcement permissions at all
        self.emp = make_user('ba.emp@test.com', role=role, branch='Suryapet')
        self.other = make_user('ba.other@test.com', role=role, branch='Hyderabad')
        self.nobranch = make_user('ba.none@test.com', role=role, branch='')
        self._t0 = timezone.now() - datetime.timedelta(days=1)
        self._n = 0

    def _post(self, title, category=Announcement.CATEGORY_GENERAL, branch=None, pinned=False):
        import datetime
        a = Announcement.objects.create(
            title=title, body=f'{title} body', category=category, is_pinned=pinned,
            visibility=Announcement.VISIBILITY_BRANCH if branch else Announcement.VISIBILITY_ALL, target_branch=branch,
        )
        self._n += 1                                          # strictly increasing creation times
        Announcement.objects.filter(pk=a.pk).update(created_at=self._t0 + datetime.timedelta(minutes=self._n))
        return a

    def _api(self, user):
        api = APIClient()
        _login(api, user.email)
        return api

    def _titles(self, user, **params):
        data = self._api(user).get(reverse('announcement-list-create'), params).data['data']
        return [r['title'] for r in data['results']], data

    # ── Dashboard banner ────────────────────────────────────────────────────
    def test_latest_eligible_pinned_post_wins(self):
        self._post('Old pinned', pinned=True, branch=self.sury)
        self._post('Newer pinned', pinned=True)
        self._post('Newest unpinned', branch=self.sury)
        self.assertEqual(self._api(self.emp).get(_BANNER).data['data']['title'], 'Newer pinned')

    def test_latest_eligible_post_when_nothing_pinned(self):
        for cat in ('general', 'policy', 'event', 'celebration'):
            self._post(f'Suryapet {cat}', category=cat, branch=self.sury)
        self.assertEqual(self._api(self.emp).get(_BANNER).data['data']['title'], 'Suryapet celebration')
        self._post('Newest policy', category='policy', branch=self.sury)
        self.assertEqual(self._api(self.emp).get(_BANNER).data['data']['category'], 'policy')   # not category-bound

    def test_other_branch_pinned_post_never_shown(self):
        self._post('Company post')
        self._post('Hyderabad pinned', pinned=True, branch=self.hyd)
        self.assertEqual(self._api(self.emp).get(_BANNER).data['data']['title'], 'Company post')
        self.assertEqual(self._api(self.other).get(_BANNER).data['data']['title'], 'Hyderabad pinned')

    # ── View All (Announcements page list API) ─────────────────────────────
    def test_view_all_lists_every_eligible_post_in_all_categories(self):
        for cat in ('general', 'policy', 'event', 'celebration'):
            self._post(f'Suryapet {cat}', category=cat, branch=self.sury)
        self._post('Company pinned', pinned=True)
        self._post('Hyderabad only', branch=self.hyd)
        titles, data = self._titles(self.emp)
        self.assertEqual(titles, ['Company pinned', 'Suryapet celebration', 'Suryapet event', 'Suryapet policy',
                                  'Suryapet general'])                        # pinned first, then newest
        self.assertEqual(data['count'], 5)
        self.assertNotIn('Hyderabad only', titles)

    def test_view_all_category_filter_still_works(self):
        self._post('Suryapet policy', category='policy', branch=self.sury)
        self._post('Company event', category='event')
        titles, _ = self._titles(self.emp, category='policy')
        self.assertEqual(titles, ['Suryapet policy'])

    def test_missing_branch_sees_company_posts_only(self):
        self._post('Company post')
        self._post('Suryapet post', branch=self.sury)
        titles, _ = self._titles(self.nobranch)
        self.assertEqual(titles, ['Company post'])
        self.assertEqual(self._api(self.nobranch).get(_BANNER).data['data']['title'], 'Company post')

    # ── Read-only for employees ────────────────────────────────────────────
    def test_employee_cannot_publish_edit_or_delete(self):
        post = self._post('Suryapet post', branch=self.sury)
        api = self._api(self.emp)
        create = api.post(reverse('announcement-list-create'),
                          {'title': 'x', 'body': 'y', 'category': 'general', 'visibility': 'all'}, format='json')
        self.assertEqual(create.status_code, 403)
        detail = reverse('announcement-detail', kwargs={'pk': post.pk})
        self.assertEqual(api.put(detail, {'title': 'z', 'body': 'z', 'category': 'general'}, format='json').status_code, 403)
        self.assertEqual(api.delete(detail).status_code, 403)
        self.assertEqual(Announcement.objects.count(), 1)
        self.assertEqual(Announcement.objects.get().title, 'Suryapet post')

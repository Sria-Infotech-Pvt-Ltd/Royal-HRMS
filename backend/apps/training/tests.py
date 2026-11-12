"""Training & Learning — backend tests."""
from __future__ import annotations

import datetime
import io
import zipfile
from unittest import mock

from django.core.cache import cache
from django.core.files.storage import InMemoryStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.factories import make_role, make_user
from apps.accounts.models import AuditLog
from apps.accounts.tests import _login
from apps.assessments.models import Assessment, AssessmentItem, AssessmentSection, CandidateAssignment
from apps.assessments.scoring import score_answers, section_weighted_score
from apps.notifications.models import Notification
from apps.training import services, validation
from apps.training.models import (
    TrainingAssessmentAttempt, TrainingAssignment, TrainingCourse, TrainingMaterial, TrainingMaterialProgress,
)
from apps.training.tasks import send_deadline_notifications

ALL = ['training.view', 'training.create', 'training.edit', 'training.delete', 'training.assign',
       'training.view_all_progress', 'training.manage_assessments', 'training.view_reports']

PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
MP4 = b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom' + b'\x00' * 64


def ooxml(folder: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types/>')
        z.writestr(f'{folder}/document.xml', '<x/>')
    return buf.getvalue()


def png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (4, 4), 'red').save(buf, 'PNG')
    return buf.getvalue()


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.storage = InMemoryStorage(base_url='/media/')
        for model, field in ((TrainingMaterial, 'document_file'), (TrainingMaterial, 'video_file'),
                             (TrainingCourse, 'thumbnail')):
            p = mock.patch.object(model._meta.get_field(field), 'storage', self.storage)
            p.start()
            self.addCleanup(p.stop)
        hr_role = make_role('tr_hr', permission_codenames=ALL)
        mgr_role = make_role('tr_mgr', can_manage_team=True, permission_codenames=['training.view'])
        emp_role = make_role('tr_emp')
        kw = {'onboarding_status': 'complete'}
        self.hr = make_user('tr.hr@test.com', role=hr_role, full_name='North HR', branch='North', employee_id='TH', **kw)
        self.hr_south = make_user('tr.hrs@test.com', role=hr_role, full_name='South HR', branch='South',
                                  employee_id='THS', **kw)
        self.mgr = make_user('tr.mgr@test.com', role=mgr_role, full_name='Mgr', branch='North', employee_id='TM', **kw)
        self.emp = make_user('tr.emp@test.com', role=emp_role, full_name='Asha', branch='North', department='Sales',
                             employee_id='TE1', reporting_manager=self.mgr, **kw)
        self.emp2 = make_user('tr.emp2@test.com', role=emp_role, full_name='Ravi', branch='North', department='Ops',
                              employee_id='TE2', **kw)
        self.south = make_user('tr.emp3@test.com', role=emp_role, full_name='Kiran', branch='South',
                               department='Sales', employee_id='TE3', **kw)
        self.course = TrainingCourse.objects.create(title='Safety Basics', created_by=self.hr)

    def api(self, user):
        cl = APIClient()
        _login(cl, user.email)
        return cl

    def doc(self, course=None, **kw):
        kw.setdefault('min_view_seconds', 0)
        return TrainingMaterial.objects.create(course=course or self.course, title='Handbook', order=1,
                                               material_type='document', file_format='pdf',
                                               document_file=SimpleUploadedFile('h.pdf', PDF), **kw)

    def video(self, course=None, **kw):
        kw.setdefault('duration_seconds', 100)
        return TrainingMaterial.objects.create(course=course or self.course, title='Intro video', order=2,
                                               material_type='video', file_format='mp4',
                                               video_file=SimpleUploadedFile('v.mp4', MP4), **kw)

    def assessment(self, max_attempts=2, pass_percentage=60):
        a = Assessment.objects.create(title='Safety quiz', pass_percentage=pass_percentage, max_attempts=max_attempts)
        self.q = [AssessmentItem.objects.create(assessment=a, item_type='quiz', title=f'Q{n}', question=f'Q{n}?',
                                                option_a='A', option_b='B', option_c='C', correct_option='a', order=n)
                  for n in range(3)]
        return a

    def assign(self, employee=None, course=None, **kw):
        return services.assign_course(course or self.course, [employee or self.emp], assigned_by=self.hr, **kw)


# ── Courses ───────────────────────────────────────────────────────────────────

class CourseTests(Base):
    def test_create_edit_and_permissions(self):
        url = reverse('training-courses')
        self.assertEqual(self.api(self.emp).post(url, {'title': 'X'}, format='json').status_code, 403)
        self.assertEqual(self.api(self.hr).post(url, {'title': ' '}, format='json').status_code, 400)
        resp = self.api(self.hr).post(url, {'title': 'Fire drill', 'category': 'Safety', 'is_mandatory': True,
                                            'duration_minutes': 45, 'start_date': '2026-12-01',
                                            'deadline': '2026-12-31'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        cid = resp.data['data']['id']
        bad = self.api(self.hr).patch(reverse('training-course-detail', args=[cid]), {'deadline': '2026-11-01'},
                                      format='json')
        self.assertEqual(bad.status_code, 400)
        ok = self.api(self.hr).patch(reverse('training-course-detail', args=[cid]),
                                     {'title': 'Fire drill 2026', 'is_active': False}, format='json')
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertFalse(TrainingCourse.objects.get(pk=cid).is_active)
        self.assertTrue(AuditLog.objects.filter(action='training_course_created').exists())
        self.assertEqual(self.api(self.emp).get(url).status_code, 403)

    def test_delete_archives_when_history_exists(self):
        empty = TrainingCourse.objects.create(title='Draft')
        self.assertFalse(self.api(self.hr).delete(reverse('training-course-detail', args=[empty.pk]))
                         .data['data']['archived'])
        self.assertFalse(TrainingCourse.objects.filter(pk=empty.pk).exists())
        self.assign()
        resp = self.api(self.hr).delete(reverse('training-course-detail', args=[self.course.pk]))
        self.assertTrue(resp.data['data']['archived'])
        self.course.refresh_from_db()
        self.assertIsNotNone(self.course.archived_at)
        self.assertEqual(TrainingAssignment.objects.count(), 1)              # history kept

    def test_link_assessment_requires_mcq_and_permission(self):
        a = self.assessment()
        empty = Assessment.objects.create(title='Empty')
        url = reverse('training-course-detail', args=[self.course.pk])
        self.assertEqual(self.api(self.hr).patch(url, {'assessment': str(empty.pk)}, format='json').status_code, 400)
        self.assertEqual(self.api(self.hr).patch(url, {'assessment': str(a.pk)}, format='json').status_code, 200)
        self.course.refresh_from_db()
        self.assertEqual(self.course.assessment_id, a.pk)
        opts = self.api(self.hr).get(reverse('training-assessment-options')).data['data']
        self.assertEqual([o['id'] for o in opts], [str(a.pk)])


# ── Materials & files ─────────────────────────────────────────────────────────

class MaterialTests(Base):
    def upload(self, name, data, kind='document', user=None, **extra):
        if kind == 'video':
            extra.setdefault('duration_seconds', 120)                   # tracked videos need their length
        return self.api(user or self.hr).post(
            reverse('training-materials', args=[self.course.pk]),
            {'material_type': kind, 'title': name, 'file': SimpleUploadedFile(name, data), **extra}, format='multipart')

    def test_valid_uploads(self):
        for name, data, kind, fmt in (('a.pdf', PDF, 'document', 'pdf'), ('s.pptx', ooxml('ppt'), 'document', 'pptx'),
                                      ('w.docx', ooxml('word'), 'document', 'docx'), ('v.mp4', MP4, 'video', 'mp4')):
            with self.subTest(name=name):
                resp = self.upload(name, data, kind)
                self.assertEqual(resp.status_code, 201, resp.data)
                self.assertEqual(resp.data['data']['file_format'], fmt)
        self.assertEqual(list(self.course.materials.values_list('order', flat=True)), [1, 2, 3, 4])

    def test_content_and_type_checks(self):
        cases = [('fake.pdf', b'MZ\x90\x00 not a pdf', 'document'), ('a.exe', PDF, 'document'),
                 ('s.pptx', ooxml('word'), 'document'), ('broken.pdf', b'%PDF-1.4 no end', 'document'),
                 ('v.mp4', PDF, 'video'), ('v.avi', MP4, 'video'), ('empty.pdf', b'', 'document')]
        for name, data, kind in cases:
            with self.subTest(name=name):
                self.assertEqual(self.upload(name, data, kind).status_code, 400)
        self.assertFalse(self.course.materials.exists())
        self.assertEqual(self.upload('a.pdf', PDF, user=self.emp).status_code, 403)

    def test_size_limit(self):
        with mock.patch.object(validation, 'DOC_MAX_BYTES', 10):
            self.assertEqual(self.upload('a.pdf', PDF).status_code, 400)

    def test_thumbnail(self):
        url = reverse('training-course-thumbnail', args=[self.course.pk])
        bad = self.api(self.hr).post(url, {'thumbnail': SimpleUploadedFile('t.png', b'not png')}, format='multipart')
        self.assertEqual(bad.status_code, 400)
        ok = self.api(self.hr).post(url, {'thumbnail': SimpleUploadedFile('t.png', png())}, format='multipart')
        self.assertEqual(ok.status_code, 200, ok.data)
        file_url = reverse('training-course-thumbnail-file', args=[self.course.pk])
        self.assertEqual(self.api(self.emp2).get(file_url).status_code, 404)        # not assigned
        self.assign()
        self.assertEqual(self.api(self.emp).get(file_url).status_code, 200)

    def test_external_links(self):
        url = reverse('training-materials', args=[self.course.pk])
        good = {
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ': ('youtube', 'dQw4w9WgXcQ'),
            'https://youtu.be/dQw4w9WgXcQ?t=5': ('youtube', 'dQw4w9WgXcQ'),
            'https://www.youtube.com/embed/dQw4w9WgXcQ': ('youtube', 'dQw4w9WgXcQ'),
            'https://vimeo.com/123456': ('vimeo', '123456'),
            'https://cdn.example.com/media/intro.mp4': ('direct', ''),
        }
        for link, (provider, vid) in good.items():
            with self.subTest(link=link):
                parsed = validation.parse_external_video(link)
                self.assertEqual((parsed['provider'], parsed['embed_id']), (provider, vid))
        bad = ['http://www.youtube.com/watch?v=dQw4w9WgXcQ', 'javascript:alert(1)', 'https://localhost/v.mp4',
               'https://10.0.0.5/v.mp4', 'https://192.168.1.2/a.mp4', 'https://user:pw@example.com/a.mp4',
               'https://example.com:8443/a.mp4', 'https://example.com/page.html', 'https://intranet.local/a.mp4',
               'https://www.youtube.com/watch?v=short', 'file:///etc/passwd', 'https://[::1]/a.mp4']
        for link in bad:
            with self.subTest(link=link):
                with self.assertRaises(validation.TrainingValidationError):
                    validation.parse_external_video(link)
        resp = self.api(self.hr).post(url, {'material_type': 'external_video', 'title': 'Talk', 'duration_seconds': 212,
                                            'external_url': 'https://youtu.be/dQw4w9WgXcQ'}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertTrue(resp.data['data']['is_tracked'])

    def test_remove_keeps_history_and_reorder(self):
        d, v = self.doc(), self.video()
        self.assign()
        a = TrainingAssignment.objects.get()
        services.record_open(a, d)
        self.assertEqual(self.api(self.hr).delete(reverse('training-material-detail', args=[d.pk])).status_code, 200)
        d.refresh_from_db()
        self.assertTrue(d.is_archived)                                    # had progress -> archived
        self.assertTrue(TrainingMaterialProgress.objects.filter(material=d).exists())
        self.api(self.hr).delete(reverse('training-material-detail', args=[v.pk]))
        self.assertFalse(TrainingMaterial.objects.filter(pk=v.pk).exists())   # no progress -> deleted
        m1, m2 = self.doc(), self.video()
        url = reverse('training-materials-reorder', args=[self.course.pk])
        self.assertEqual(self.api(self.hr).post(url, {'order': [str(m2.pk)]}, format='json').status_code, 400)
        self.assertEqual(self.api(self.hr).post(url, {'order': [str(m2.pk), str(m1.pk)]}, format='json')
                         .status_code, 200)
        m1.refresh_from_db()
        m2.refresh_from_db()
        self.assertEqual((m2.order, m1.order), (1, 2))


# ── Assignment ────────────────────────────────────────────────────────────────

class AssignmentTests(Base):
    def post(self, user, body):
        return self.api(user).post(reverse('training-assign', args=[self.course.pk]), body, format='json')

    def test_individual_department_branch_all_without_duplicates(self):
        r = self.post(self.hr, {'employee_ids': [str(self.emp.pk)], 'due_date': '2026-12-31'})
        self.assertEqual(r.data['data'], {'assigned': 1, 'already_assigned': 0})
        self.assertEqual(Notification.objects.filter(user=self.emp, title='Training Assigned').count(), 1)
        r = self.post(self.hr, {'departments': ['sales']})                 # Asha (dup) — Kiran is South
        self.assertEqual(r.data['data'], {'assigned': 0, 'already_assigned': 1})
        r = self.post(self.hr, {'branches': ['North']})
        self.assertEqual(r.data['data']['assigned'], 3)                     # Ravi, Mgr, North HR
        r = self.post(self.hr, {'all': True})
        self.assertEqual(r.data['data']['assigned'], 0)
        self.assertFalse(TrainingAssignment.objects.filter(employee=self.south).exists())
        self.assertEqual(Notification.objects.filter(user=self.emp, title='Training Assigned').count(), 1)

    def test_scope_and_permissions(self):
        self.assertEqual(self.post(self.hr, {'employee_ids': [str(self.south.pk)]}).status_code, 403)
        self.assertEqual(self.post(self.emp, {'employee_ids': [str(self.emp2.pk)]}).status_code, 403)
        self.assertEqual(self.post(self.hr, {}).status_code, 400)
        self.assertEqual(self.post(self.hr_south, {'all': True}).data['data']['assigned'], 2)   # South only
        self.assertEqual(self.post(self.hr, {'employee_ids': [str(self.emp.pk)], 'due_date': '2020-01-01'})
                         .status_code, 400)
        picker = self.api(self.hr).get(reverse('training-employee-picker')).data['data']
        self.assertNotIn(str(self.south.pk), {e['id'] for e in picker['employees']})
        self.assertEqual(picker['branches'], ['North'])

    def test_inactive_course_cannot_be_assigned(self):
        self.course.is_active = False
        self.course.save()
        self.assertEqual(self.post(self.hr, {'all': True}).status_code, 400)

    def test_unassign_only_before_start(self):
        self.assign()
        a = TrainingAssignment.objects.get()
        url = reverse('training-assignment-delete', args=[a.pk])
        services.record_open(a, self.doc())
        self.assertEqual(self.api(self.hr).delete(url).status_code, 409)
        TrainingMaterialProgress.objects.all().delete()
        TrainingAssignment.objects.filter(pk=a.pk).update(status='assigned')
        self.assertEqual(self.api(self.hr_south).delete(url).status_code, 404)       # other branch
        self.assertEqual(self.api(self.hr).delete(url).status_code, 200)


class NewJoinerTests(Base):
    def setUp(self):
        super().setUp()
        self.course.auto_assign_new_joiners = True
        self.course.new_joiner_deadline_days = 14
        self.course.new_joiner_branches = ['North']
        self.course.save()

    def onboard(self, user):
        user.onboarding_status = 'complete'
        with self.captureOnCommitCallbacks(execute=True):
            user.save(update_fields=['onboarding_status'])

    def joiner(self, email, branch='North', dept='Sales'):
        return make_user(email, role=make_role('tr_emp'), full_name='New', branch=branch, department=dept,
                         onboarding_status='submitted')

    def test_assigned_on_onboarding_completion_once(self):
        u = self.joiner('tr.new1@test.com')
        self.onboard(u)
        a = TrainingAssignment.objects.get(employee=u)
        self.assertEqual((a.source, a.due_date), ('onboarding', timezone.localdate() + datetime.timedelta(days=14)))
        self.onboard(u)                                                    # saving again: no duplicate
        self.assertEqual(TrainingAssignment.objects.filter(employee=u).count(), 1)

    def test_filters_and_no_retroactive_assignment(self):
        self.onboard(self.joiner('tr.new2@test.com', branch='South'))
        with self.captureOnCommitCallbacks(execute=True):
            self.emp.full_name = 'Asha K'
            self.emp.save()                                                # already complete employee
        self.assertFalse(TrainingAssignment.objects.exists())

    def test_module_disabled(self):
        u = self.joiner('tr.new3@test.com')
        with mock.patch('apps.tenants.access.module_enabled', return_value=False):
            self.onboard(u)
        self.assertFalse(TrainingAssignment.objects.exists())


# ── Employee learning ─────────────────────────────────────────────────────────

class LearningTests(Base):
    def setUp(self):
        super().setUp()
        self.d, self.v = self.doc(min_view_seconds=30), self.video()
        self.assign()
        self.a = TrainingAssignment.objects.get(employee=self.emp)

    def act(self, material, action, body=None, user=None):
        return self.api(user or self.emp).post(
            reverse('training-my-material', args=[self.a.pk, material.pk, action]), body or {}, format='json')

    def test_only_own_assignments_and_files(self):
        self.assertEqual(len(self.api(self.emp).get(reverse('training-my')).data['data']), 1)
        self.assertEqual(self.api(self.emp2).get(reverse('training-my')).data['data'], [])
        self.assertEqual(self.api(self.emp2).get(reverse('training-my-detail', args=[self.a.pk])).status_code, 404)
        self.assertEqual(self.act(self.d, 'open', user=self.emp2).status_code, 404)
        file_url = reverse('training-material-file', args=[self.d.pk])
        self.assertEqual(self.api(self.emp2).get(file_url).status_code, 404)
        resp = self.api(self.emp).get(file_url)
        self.assertEqual((resp.status_code, resp['Content-Type']), (200, 'application/pdf'))
        self.assertEqual(resp['Cache-Control'], 'private, no-store')
        vid = self.api(self.emp).get(reverse('training-material-video', args=[self.v.pk]))
        self.assertEqual((vid.status_code, vid.data['data']['url']), (200, None))    # local storage: stream
        ranged = self.api(self.emp).get(reverse('training-material-file', args=[self.v.pk]), HTTP_RANGE='bytes=0-9')
        self.assertEqual((ranged.status_code, len(ranged.content)), (206, 10))
        detail = self.api(self.emp).get(reverse('training-my-detail', args=[self.a.pk])).data['data']
        self.assertNotIn('document_file', str(detail))

    def test_opening_does_not_complete(self):
        self.act(self.d, 'open')
        self.act(self.v, 'open')
        self.a.refresh_from_db()
        self.assertEqual(self.a.status, 'in_progress')
        self.assertFalse(TrainingMaterialProgress.objects.filter(completed_at__isnull=False).exists())

    def test_document_needs_open_and_minimum_time(self):
        self.assertEqual(self.act(self.d, 'confirm').status_code, 400)           # not opened
        self.act(self.d, 'open')
        self.assertEqual(self.act(self.d, 'confirm').status_code, 400)           # too soon
        TrainingMaterialProgress.objects.filter(material=self.d).update(
            opened_at=timezone.now() - datetime.timedelta(seconds=31))
        resp = self.act(self.d, 'confirm')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['data']['material']['progress']['completion_method'], 'read')

    def test_video_watch_tracking_cannot_be_skipped(self):
        t0 = timezone.now()
        with mock.patch('apps.training.services.timezone.now', return_value=t0):
            self.act(self.v, 'progress', {'position': 0, 'duration': 5})          # HR set 100 s; 5 ignored
        with mock.patch('apps.training.services.timezone.now', return_value=t0 + datetime.timedelta(seconds=10)):
            self.act(self.v, 'progress', {'position': 99})                        # skipped ahead
        p = TrainingMaterialProgress.objects.get(material=self.v)
        self.assertLessEqual(p.watched_seconds, 15)                                # only real elapsed time counts
        self.assertIsNone(p.completed_at)
        with mock.patch('apps.training.services.timezone.now', return_value=t0 + datetime.timedelta(seconds=11)):
            self.act(self.v, 'progress', {'position': 100})                        # jumping to the end again
        p.refresh_from_db()
        self.assertIsNone(p.completed_at)
        self.assertEqual(self.act(self.v, 'confirm').status_code, 400)            # tracked: no manual shortcut
        start = t0 + datetime.timedelta(seconds=20)
        for step in range(0, 11):                                                  # watch 0 -> 100 in real time
            with mock.patch('apps.training.services.timezone.now',
                            return_value=start + datetime.timedelta(seconds=10 * step)):
                self.act(self.v, 'progress', {'position': 10 * step})
        p.refresh_from_db()
        self.assertIsNotNone(p.completed_at, p.watched_seconds)
        self.assertEqual(p.completion_method, 'tracked')

    def test_untracked_video_needs_hr_permission_to_confirm(self):
        vimeo = TrainingMaterial.objects.create(course=self.course, title='Vimeo', order=3,
                                                material_type='external_video', provider='vimeo', embed_id='1',
                                                external_url='https://vimeo.com/1')
        self.act(vimeo, 'open')
        self.assertEqual(self.act(vimeo, 'confirm').status_code, 400)
        self.assertEqual(self.act(vimeo, 'progress', {'position': 5}).status_code, 400)
        vimeo.allow_manual_completion = True
        vimeo.save()
        self.assertEqual(self.act(vimeo, 'confirm').status_code, 200)

    def test_course_completes_without_assessment(self):
        self.v.is_required = False
        self.v.save()
        self.act(self.d, 'open')
        TrainingMaterialProgress.objects.filter(material=self.d).update(
            opened_at=timezone.now() - datetime.timedelta(minutes=5))
        self.act(self.d, 'confirm')
        self.a.refresh_from_db()
        self.assertEqual(self.a.status, 'completed')
        self.assertTrue(Notification.objects.filter(user=self.emp, title='Training Completed').exists())


class AssessmentFlowTests(Base):
    def setUp(self):
        super().setUp()
        self.course.assessment = self.assessment(max_attempts=2)
        self.course.save()
        self.d = self.doc()
        self.assign()
        self.a = TrainingAssignment.objects.get(employee=self.emp)

    def start(self):
        return self.api(self.emp).post(reverse('training-my-assessment', args=[self.a.pk, 'start']), format='json')

    def submit(self, answers):
        return self.api(self.emp).post(reverse('training-my-assessment', args=[self.a.pk, 'submit']),
                                       {'answers': answers}, format='json')

    def finish_materials(self):
        services.record_open(self.a, self.d)
        services.confirm_material(self.a, self.d)

    def answers(self, right):
        return {str(q.id): ('a' if n < right else 'b') for n, q in enumerate(self.q)}

    def test_locked_until_materials_done_and_no_answer_leak(self):
        self.assertEqual(self.start().status_code, 400)
        self.finish_materials()
        resp = self.start()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(len(resp.data['data']['questions']), 3)
        self.assertNotIn('correct', str(resp.data['data']))
        self.assertEqual(self.start().data['data']['attempt_id'], resp.data['data']['attempt_id'])  # same open attempt

    def test_fail_twice_then_reset_then_pass(self):
        self.finish_materials()
        self.start()
        r = self.submit(self.answers(1))                    # 33% < 60%
        self.assertFalse(r.data['data']['passed'])
        self.a.refresh_from_db()
        self.assertEqual((self.a.status, self.a.attempts_used), ('in_progress', 1))
        self.start()
        self.submit(self.answers(0))
        self.a.refresh_from_db()
        self.assertEqual(self.a.status, 'failed')
        self.assertEqual(self.start().status_code, 409)
        reset = self.api(self.hr).post(reverse('training-assignment-reset', args=[self.a.pk]))
        self.assertEqual(reset.status_code, 200)
        self.start()
        r = self.submit(self.answers(2))                    # 67% >= 60%
        self.assertTrue(r.data['data']['passed'])
        self.a.refresh_from_db()
        self.assertEqual((self.a.status, self.a.best_score_percent), ('completed', 67))
        self.assertEqual(list(TrainingAssessmentAttempt.objects.filter(assignment=self.a)
                              .order_by('attempt_number').values_list('attempt_number', flat=True)), [1, 2, 3])
        self.assertEqual(Notification.objects.filter(user=self.emp, title='Assessment Result').count(), 3)

    def test_optional_retake_after_pass_keeps_completion_and_best_score(self):
        self.finish_materials()
        self.start()
        self.submit(self.answers(3))                              # 100%: passed on attempt 1 of 2
        self.a.refresh_from_db()
        self.assertEqual(self.a.status, 'completed')
        state = services.assessment_state(self.a)
        self.assertEqual((state['can_retake'], state['attempts_left']), (True, 1))
        self.assertEqual(self.start().status_code, 200)
        r = self.submit(self.answers(0))                          # retake scores 0%
        self.assertFalse(r.data['data']['passed'])
        self.a.refresh_from_db()
        self.assertEqual((self.a.status, self.a.assessment_passed, self.a.best_score_percent),
                         ('completed', True, 100))                # pass and best score kept
        self.assertFalse(services.assessment_state(self.a)['can_attempt'])
        self.assertEqual(self.start().status_code, 409)           # attempt limit (2) reached
        self.assertIn('best score is 100%',
                      Notification.objects.filter(user=self.emp, title='Assessment Result').first().message)

    def test_retake_raises_best_score(self):
        self.finish_materials()
        self.start()
        self.submit(self.answers(2))                              # 67%: passed
        self.start()
        self.submit(self.answers(3))                              # retake 100%
        self.a.refresh_from_db()
        self.assertEqual((self.a.status, self.a.best_score_percent), ('completed', 100))

    def test_unlimited_attempts_allow_two_retakes_after_pass(self):
        self.course.assessment.max_attempts = 0                   # 0 = unlimited
        self.course.assessment.save()
        self.finish_materials()
        self.start()
        self.submit(self.answers(2))                              # passed
        for _ in range(2):
            self.assertEqual(self.start().status_code, 200)
            self.submit(self.answers(1))
        self.assertEqual(self.start().status_code, 409)           # capped at 2 retakes
        self.a.refresh_from_db()
        self.assertEqual((self.a.status, self.a.assessment_passed), ('completed', True))

    def test_does_not_touch_onboarding_assessment_gate(self):
        status_before = type(self.emp).objects.get(pk=self.emp.pk).assessment_status
        self.finish_materials()
        self.start()
        self.submit(self.answers(3))
        self.assertFalse(CandidateAssignment.objects.exists())
        self.assertEqual(type(self.emp).objects.get(pk=self.emp.pk).assessment_status, status_before)

    def test_time_limit(self):
        self.course.assessment.time_limit_mins = 1
        self.course.assessment.save()
        self.finish_materials()
        self.start()
        TrainingAssessmentAttempt.objects.update(started_at=timezone.now() - datetime.timedelta(minutes=5))
        r = self.submit(self.answers(3))
        self.assertFalse(r.data['data']['passed'])


class ScoringTests(Base):
    def test_matches_assessment_engine(self):
        a = self.assessment()
        sec = AssessmentSection.objects.create(assessment=a, title='S', score=10)
        AssessmentItem.objects.filter(pk__in=[self.q[0].pk, self.q[1].pk]).update(section=sec)
        r = score_answers(a, {str(self.q[0].id): 'a', str(self.q[1].id): 'b', str(self.q[2].id): 'a'})
        # section: 1 of 2 right -> 5 of 10; unsectioned item right -> 1 of 1
        self.assertEqual((r['score'], r['max_score'], r['percentage']), (6, 11, 55))
        self.assertEqual(section_weighted_score([sec], [{'id': self.q[0].id, 'section_id': sec.id},
                                                        {'id': self.q[1].id, 'section_id': sec.id}],
                                                {self.q[0].id}), (5, 10))


# ── Reporting & access ────────────────────────────────────────────────────────

class ReportTests(Base):
    def setUp(self):
        super().setUp()
        self.assign(self.emp, due_date=timezone.localdate() - datetime.timedelta(days=1))   # overdue
        self.assign(self.emp2)
        self.assign(self.south)

    def test_branch_scope_filters_and_csv(self):
        rows = self.api(self.hr).get(reverse('training-reports')).data['data']
        self.assertEqual({r['employee']['name'] for r in rows}, {'Asha', 'Ravi'})
        rows = self.api(self.hr_south).get(reverse('training-reports')).data['data']
        self.assertEqual({r['employee']['name'] for r in rows}, {'Kiran'})
        overdue = self.api(self.hr).get(reverse('training-reports'), {'status': 'overdue'}).data['data']
        self.assertEqual([r['employee']['name'] for r in overdue], ['Asha'])
        dept = self.api(self.hr).get(reverse('training-reports'), {'department': 'Ops'}).data['data']
        self.assertEqual([r['employee']['name'] for r in dept], ['Ravi'])
        csv_resp = self.api(self.hr).get(reverse('training-reports'), {'export': 'csv'})
        self.assertEqual(csv_resp['Content-Type'], 'text/csv')
        self.assertIn(b'Safety Basics', csv_resp.content)
        self.assertNotIn(b'Kiran', csv_resp.content)
        dash = self.api(self.hr).get(reverse('training-dashboard')).data['data']
        self.assertEqual((dash['assigned'], dash['overdue'], dash['not_started']), (2, 1, 1))

    def test_manager_sees_direct_reports_only_and_employees_nothing(self):
        rows = self.api(self.mgr).get(reverse('training-course-progress', args=[self.course.pk])).data['data']
        self.assertEqual([r['employee']['name'] for r in rows], ['Asha'])
        self.assertEqual(self.api(self.mgr).get(reverse('training-reports')).status_code, 403)
        self.assertEqual(self.api(self.emp).get(reverse('training-course-progress', args=[self.course.pk]))
                         .status_code, 403)
        self.assertEqual(self.api(self.emp).get(reverse('training-dashboard')).status_code, 403)

    def test_module_switched_off(self):
        with mock.patch('apps.tenants.models.Client.has_module', return_value=False):
            resp = self.api(self.hr).get(reverse('training-courses'))
        self.assertEqual(resp.status_code, 403)
        self.assertIn('Training & Learning', resp.json()['message'])


class DeadlineTaskTests(Base):
    def test_reminder_and_overdue_once(self):
        today = timezone.localdate()
        self.assign(self.emp, due_date=today + datetime.timedelta(days=2))
        self.assign(self.emp2, due_date=today - datetime.timedelta(days=1))
        Notification.objects.all().delete()
        self.assertEqual(send_deadline_notifications(today), {'reminded': 1, 'overdue': 1})
        self.assertEqual(send_deadline_notifications(today), {'reminded': 0, 'overdue': 0})
        self.assertEqual(list(Notification.objects.filter(user=self.emp).values_list('title', flat=True)),
                         ['Training Due Soon'])
        self.assertEqual(list(Notification.objects.filter(user=self.emp2).values_list('title', flat=True)),
                         ['Training Overdue'])


# ── Audit fixes (C-1, C-2, C-3, C-4, C-6, C-7, C-10, optional videos) ───────────

class AuditFixTests(Base):
    def setUp(self):
        super().setUp()
        self.t0 = timezone.now()

    def beat(self, a, m, position, at, duration=None):
        with mock.patch('apps.training.services.timezone.now', return_value=self.t0 + datetime.timedelta(seconds=at)):
            return services.record_heartbeat(a, m, position, duration)

    def my_assignment(self):
        self.assign()
        return TrainingAssignment.objects.get(employee=self.emp)

    # C-1 — watched time can't grow faster than real time
    def test_c1_rapid_or_fast_forward_updates_do_not_count(self):
        v = self.video(duration_seconds=100)
        a = self.my_assignment()
        self.beat(a, v, 0, 0)
        p = self.beat(a, v, 50, 0.5)                                 # 0.5 s later: ignored
        self.assertEqual((p.watched_seconds, p.last_position_seconds), (0, 0))
        for n in range(1, 11):                                        # every 3 s, claims 10 s of video
            p = self.beat(a, v, 10 * n, 3 * n)
        self.assertLessEqual(p.watched_seconds, 30 * services.WATCH_RATE_TOLERANCE + 0.01)
        self.assertIsNone(p.completed_at)
        p = self.beat(a, v, float('inf'), 40)                         # junk position
        self.assertTrue(p.last_position_seconds <= 100)

    def test_c1_total_never_exceeds_time_since_opened(self):
        v = self.video(duration_seconds=1000)
        a = self.my_assignment()
        for n in range(0, 61):                                        # 10.5 s of video every 10 s
            p = self.beat(a, v, 10.5 * n, 10 * n)
        self.assertLessEqual(p.watched_seconds, 600 + services.WATCH_TIME_SLACK_SECONDS)

    def test_c1_normal_viewing_still_completes(self):
        v = self.video(duration_seconds=60)
        a = self.my_assignment()
        for n in range(0, 7):
            p = self.beat(a, v, 10 * n, 10 * n)
        self.assertIsNotNone(p.completed_at)

    # C-2 — the browser's video length is ignored; HR must enter it
    def test_c2_browser_duration_ignored(self):
        v = TrainingMaterial.objects.create(course=self.course, title='Old video', order=5, material_type='video',
                                            file_format='mp4', video_file=SimpleUploadedFile('o.mp4', MP4))
        a = self.my_assignment()
        self.beat(a, v, 0, 0, duration=10)
        p = self.beat(a, v, 10, 10, duration=10)
        self.assertIsNone(p.duration_seconds)
        self.assertIsNone(p.completed_at)

    def test_c2_video_length_required_for_tracked_videos(self):
        url = reverse('training-materials', args=[self.course.pk])
        hr = self.api(self.hr)
        r = hr.post(url, {'material_type': 'external_video', 'title': 'YT',
                          'external_url': 'https://youtu.be/dQw4w9WgXcQ'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('duration_seconds', r.data['data'])
        r = hr.post(url, {'material_type': 'video', 'title': 'Up', 'file': SimpleUploadedFile('v.mp4', MP4)},
                    format='multipart')
        self.assertEqual(r.status_code, 400)
        r = hr.post(url, {'material_type': 'external_video', 'title': 'Vimeo',
                          'external_url': 'https://vimeo.com/123'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)                 # not tracked: length optional
        r = hr.post(url, {'material_type': 'external_video', 'title': 'YT', 'duration_seconds': 90,
                          'external_url': 'https://youtu.be/dQw4w9WgXcQ'}, format='json')
        self.assertEqual(r.status_code, 201, r.data)
        mid = r.data['data']['id']
        r = hr.patch(reverse('training-material-detail', args=[mid]), {'duration_seconds': ''}, format='json')
        self.assertEqual(r.status_code, 400)

    # C-3 — only a failed assessment can be reset
    def test_c3_reset_only_when_failed(self):
        self.course.assessment = self.assessment()
        self.course.save()
        a = self.my_assignment()
        url = reverse('training-assignment-reset', args=[a.pk])
        self.assertEqual(self.api(self.hr).post(url).status_code, 409)                    # assigned
        TrainingAssignment.objects.filter(pk=a.pk).update(status='completed', assessment_passed=True)
        self.assertEqual(self.api(self.hr).post(url).status_code, 409)                    # completed + passed
        a.refresh_from_db()
        self.assertEqual((a.status, a.assessment_passed), ('completed', True))
        TrainingAssignment.objects.filter(pk=a.pk).update(status='failed', assessment_passed=False)
        self.assertEqual(self.api(self.hr).post(url).status_code, 200)

    # C-4 — an assessment without questions is never an automatic pass
    def test_c4_empty_assessment_cannot_be_taken_or_passed(self):
        self.course.assessment = self.assessment()
        self.course.save()
        a = self.my_assignment()
        cl = self.api(self.emp)
        self.assertEqual(cl.post(reverse('training-my-assessment', args=[a.pk, 'start'])).status_code, 200)
        AssessmentItem.objects.filter(assessment=self.course.assessment).delete()          # HR empties it
        r = cl.post(reverse('training-my-assessment', args=[a.pk, 'submit']), {'answers': {}}, format='json')
        self.assertEqual(r.status_code, 409)
        a.refresh_from_db()
        self.assertNotEqual(a.assessment_passed, True)
        self.assertEqual(a.status, 'assigned')
        state = services.assessment_state(a)
        self.assertEqual((state['has_questions'], state['can_attempt']), (False, False))
        self.assertEqual(cl.post(reverse('training-my-assessment', args=[a.pk, 'start'])).status_code, 409)

    # C-6 — CSV values that a spreadsheet would run as formulas are neutralised
    def test_c6_csv_formula_injection(self):
        self.course.title = '=HYPERLINK("http://x","click")'
        self.course.save()
        self.assign()
        content = self.api(self.hr).get(reverse('training-reports'), {'export': 'csv'}).content
        self.assertIn(b"'=HYPERLINK", content)
        self.assertNotIn(b',=HYPERLINK', content)
        from apps.training.views import _csv_safe
        self.assertEqual([_csv_safe(v) for v in ('+1', '-2', '@x', 'ok', 5)], ["'+1", "'-2", "'@x", 'ok', 5])

    # C-7 — a past course deadline is not used as the default due date
    def test_c7_past_course_deadline_not_used_as_due_date(self):
        today = timezone.localdate()
        self.course.deadline = today - datetime.timedelta(days=3)
        self.course.save()
        url = reverse('training-assign', args=[self.course.pk])
        self.api(self.hr).post(url, {'employee_ids': [str(self.emp.pk)]}, format='json')
        self.assertIsNone(TrainingAssignment.objects.get(employee=self.emp).due_date)
        self.course.deadline = today + datetime.timedelta(days=10)
        self.course.save()
        self.api(self.hr).post(url, {'employee_ids': [str(self.emp2.pk)]}, format='json')
        self.assertEqual(TrainingAssignment.objects.get(employee=self.emp2).due_date, self.course.deadline)

    def test_c7_new_joiner_without_days_and_past_deadline(self):
        self.course.auto_assign_new_joiners = True
        self.course.new_joiner_deadline_days = 0
        self.course.deadline = timezone.localdate() - datetime.timedelta(days=1)
        self.course.save()
        u = make_user('tr.new9@test.com', role=make_role('tr_emp'), full_name='New', branch='North',
                      onboarding_status='submitted')
        u.onboarding_status = 'complete'
        with self.captureOnCommitCallbacks(execute=True):
            u.save(update_fields=['onboarding_status'])
        self.assertIsNone(TrainingAssignment.objects.get(employee=u).due_date)

    # C-10 — nothing opens before the course start date
    def test_c10_course_not_open_before_start_date(self):
        self.course.start_date = timezone.localdate() + datetime.timedelta(days=2)
        self.course.assessment = self.assessment()
        self.course.save()
        d = self.doc()
        a = self.my_assignment()
        cl = self.api(self.emp)
        r = cl.post(reverse('training-my-material', args=[a.pk, d.pk, 'open']), format='json')
        self.assertEqual(r.status_code, 409)
        self.assertIn('starts on', r.data['message'])
        self.assertEqual(cl.post(reverse('training-my-assessment', args=[a.pk, 'start'])).status_code, 409)
        detail = cl.get(reverse('training-my-detail', args=[a.pk])).data['data']
        self.assertEqual(detail['starts_on'], self.course.start_date.isoformat())
        self.assertFalse(detail['assessment']['can_attempt'])
        self.course.start_date = timezone.localdate()                                       # starts today: open
        self.course.save()
        self.assertEqual(cl.post(reverse('training-my-material', args=[a.pk, d.pk, 'open']), format='json')
                         .status_code, 200)
        self.assertIsNone(cl.get(reverse('training-my-detail', args=[a.pk])).data['data']['starts_on'])

    # Course setting: video watching optional — the assessment decides completion
    def test_videos_optional_needs_assessment_and_skips_videos(self):
        url = reverse('training-course-detail', args=[self.course.pk])
        r = self.api(self.hr).patch(url, {'videos_optional': True}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('videos_optional', r.data['data'])
        quiz = self.assessment()
        r = self.api(self.hr).patch(url, {'videos_optional': True, 'assessment': str(quiz.pk)}, format='json')
        self.assertEqual(r.status_code, 200, r.data)
        self.assertTrue(r.data['data']['videos_optional'])
        v, d = self.video(), self.doc()
        a = self.my_assignment()
        cl = self.api(self.emp)
        detail = cl.get(reverse('training-my-detail', args=[a.pk])).data['data']
        required = {m['id']: m['is_required'] for m in detail['materials']}
        self.assertEqual((required[str(v.pk)], required[str(d.pk)]), (False, True))
        self.assertFalse(detail['assessment']['unlocked'])                                 # document still required
        services.record_open(a, d)
        services.confirm_material(a, d)
        self.assertTrue(services.assessment_state(a)['unlocked'])                          # video not watched
        cl.post(reverse('training-my-assessment', args=[a.pk, 'start']))
        cl.post(reverse('training-my-assessment', args=[a.pk, 'submit']),
                {'answers': {str(q.id): 'a' for q in self.q}}, format='json')
        a.refresh_from_db()
        self.assertEqual(a.status, 'completed')
        r = self.api(self.hr).patch(url, {'assessment': ''}, format='json')                 # can't unlink now
        self.assertEqual(r.status_code, 400)

    def test_without_videos_optional_video_blocks_assessment(self):
        self.course.assessment = self.assessment()
        self.course.save()
        self.video()
        a = self.my_assignment()
        self.assertFalse(services.assessment_state(a)['unlocked'])

"""
/api/training/ — gated by the 'training' module (apps.tenants.feature_gate).

HR / admin                                               permission
  GET  POST   courses/                                   view · create
  GET  PATCH  DELETE courses/<id>/                       view · edit · delete (archives when history exists)
  POST        courses/<id>/thumbnail/                    edit
  GET  POST   courses/<id>/materials/                    view · edit
  POST        courses/<id>/materials/reorder/            edit
  PATCH DELETE materials/<id>/                           edit (removing keeps employee history)
  POST        courses/<id>/assign/                       assign (employees in the assigner's scope)
  GET         courses/<id>/progress/                     view_all_progress / team managers (scoped)
  DELETE      assignments/<id>/                          assign (only while not started)
  POST        assignments/<id>/reset-assessment/         manage_assessments
  GET         assessments/                               manage_assessments (assessments to link)
  GET         employees/                                 assign (picker, scoped)
  GET         dashboard/   GET reports/ (?export=csv)    view_reports / view_all_progress (scoped)
Employee (own assignments only)
  GET   my/   GET my/<assignment>/
  POST  my/<assignment>/materials/<material>/open|progress|confirm/
  POST  my/<assignment>/assessment/start|submit/
Files (access-checked)
  GET   courses/<id>/thumbnail/file/   materials/<id>/file/   materials/<id>/video-source/
"""
from __future__ import annotations

import csv
import datetime
import io
import logging
import os

from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm
from core.responses import error, get_client_ip, success

from apps.training import services
from apps.training.models import TrainingAssignment, TrainingCourse, TrainingMaterial, TrainingMaterialProgress
from apps.training.validation import (
    CONTENT_TYPES, TrainingValidationError, parse_external_video, validate_document, validate_thumbnail,
    validate_video,
)

logger = logging.getLogger(__name__)
FORBIDDEN = 'You do not have permission to perform this action.'


def _deny():
    return error(FORBIDDEN, http_status=status.HTTP_403_FORBIDDEN)


def _bad(exc):
    field = getattr(exc, 'field', '')
    return error(str(exc), data={field: [str(exc)]} if field else None,
                 http_status=getattr(exc, 'status', 400))


def _audit(request, action, obj_id, changes=None):
    from apps.accounts.models import AuditLog
    AuditLog.objects.create(user=request.user, action=action, module='training', object_id=str(obj_id),
                            changes=changes or {}, ip_address=get_client_ip(request))


def _date(value, field):
    if value in (None, ''):
        return None
    try:
        return datetime.date.fromisoformat(str(value))
    except ValueError:
        raise TrainingValidationError('Use a date like 2026-12-31.', field) from None


def _bool(value) -> bool:
    return value in (True, 'true', 'True', '1', 1, 'on')


def _person(u):
    return {'id': str(u.pk), 'name': u.full_name or u.email, 'employee_id': u.employee_id or '',
            'branch': u.branch or '', 'department': u.department or ''} if u else None


# ── Serialisation ─────────────────────────────────────────────────────────────

def material_out(m: TrainingMaterial, progress: TrainingMaterialProgress | None = None) -> dict:
    out = {
        'id': str(m.id), 'title': m.title, 'description': m.description, 'material_type': m.material_type,
        'order': m.order, 'is_required': m.is_required, 'file_format': m.file_format, 'file_size': m.file_size,
        'original_name': m.original_name, 'provider': m.provider, 'embed_id': m.embed_id,
        'external_url': m.external_url, 'duration_seconds': m.duration_seconds,
        'min_view_seconds': m.min_view_seconds, 'allow_manual_completion': m.allow_manual_completion,
        'is_tracked': m.is_tracked, 'is_archived': m.is_archived,
    }
    if progress is not None:
        out['progress'] = {
            'opened_at': progress.opened_at.isoformat() if progress.opened_at else None,
            'watched_seconds': round(progress.watched_seconds, 1),
            'last_position_seconds': round(progress.last_position_seconds, 1),
            'duration_seconds': progress.duration_seconds or m.duration_seconds,
            'completed_at': progress.completed_at.isoformat() if progress.completed_at else None,
            'completion_method': progress.completion_method,
        }
    return out


def course_out(c: TrainingCourse, *, counts=None, detail=False) -> dict:
    out = {
        'id': str(c.id), 'title': c.title, 'description': c.description, 'category': c.category,
        'owner': _person(c.owner), 'trainer_name': c.trainer_name, 'has_thumbnail': bool(c.thumbnail),
        'duration_minutes': c.duration_minutes, 'is_mandatory': c.is_mandatory, 'is_active': c.is_active,
        'start_date': c.start_date.isoformat() if c.start_date else None,
        'deadline': c.deadline.isoformat() if c.deadline else None,
        'assessment': ({'id': str(c.assessment.id), 'title': c.assessment.title,
                        'pass_percentage': c.assessment.pass_percentage} if c.assessment_id else None),
        'videos_optional': c.videos_optional,
        'auto_assign_new_joiners': c.auto_assign_new_joiners,
        'new_joiner_deadline_days': c.new_joiner_deadline_days,
        'new_joiner_branches': c.new_joiner_branches, 'new_joiner_departments': c.new_joiner_departments,
        'archived': c.archived_at is not None, 'created_at': c.created_at.isoformat(),
    }
    if counts is not None:
        out.update(counts)
    if detail:
        out['materials'] = [material_out(m) for m in c.materials.filter(is_archived=False).order_by('order', 'created_at')]
    return out


def assignment_row(a: TrainingAssignment) -> dict:
    return {
        'id': str(a.id), 'employee': _person(a.employee), 'course_id': str(a.course_id), 'course_title': a.course.title,
        'status': a.display_status, 'source': a.source, 'due_date': a.due_date.isoformat() if a.due_date else None,
        'assigned_at': a.created_at.isoformat(),
        'started_at': a.started_at.isoformat() if a.started_at else None,
        'completed_at': a.completed_at.isoformat() if a.completed_at else None,
        'attempts_used': a.attempts_used, 'best_score_percent': a.best_score_percent,
        'assessment_passed': a.assessment_passed,
    }


def _progress_percent(a: TrainingAssignment, required_ids: set) -> int:
    if not required_ids:
        return 100 if a.status == TrainingAssignment.STATUS_COMPLETED else 0
    done = sum(1 for p in a.material_progress.all() if p.completed_at and p.material_id in required_ids)
    return round(done * 100 / len(required_ids))


# ── Course parsing ────────────────────────────────────────────────────────────

_COURSE_FIELDS = ('title', 'description', 'category', 'trainer_name', 'duration_minutes', 'is_mandatory', 'is_active',
                  'start_date', 'deadline', 'owner', 'assessment', 'auto_assign_new_joiners',
                  'new_joiner_deadline_days', 'new_joiner_branches', 'new_joiner_departments', 'videos_optional')


def _apply_course(c: TrainingCourse, data, user, *, creating: bool):
    from apps.accounts.models import User
    if creating or 'title' in data:
        title = (data.get('title') or '').strip()
        if not title:
            raise TrainingValidationError('Give the course a title.', 'title')
        c.title = title[:200]
    for f in ('description', 'category', 'trainer_name'):
        if f in data:
            setattr(c, f, (data.get(f) or '').strip()[:{'category': 100, 'trainer_name': 150}.get(f, 20000)])
    if 'duration_minutes' in data:
        v = data.get('duration_minutes')
        try:
            c.duration_minutes = None if v in (None, '') else max(1, min(int(v), 100000))
        except (TypeError, ValueError):
            raise TrainingValidationError('Enter the duration in minutes.', 'duration_minutes') from None
    for f in ('is_mandatory', 'is_active', 'auto_assign_new_joiners', 'videos_optional'):
        if f in data:
            setattr(c, f, _bool(data.get(f)))
    if 'start_date' in data:
        c.start_date = _date(data.get('start_date'), 'start_date')
    if 'deadline' in data:
        c.deadline = _date(data.get('deadline'), 'deadline')
    if c.start_date and c.deadline and c.deadline < c.start_date:
        raise TrainingValidationError('The deadline must be on or after the start date.', 'deadline')
    if 'new_joiner_deadline_days' in data:
        try:
            c.new_joiner_deadline_days = max(0, min(int(data.get('new_joiner_deadline_days') or 0), 365))
        except (TypeError, ValueError):
            raise TrainingValidationError('Enter a number of days (0–365).', 'new_joiner_deadline_days') from None
    for f in ('new_joiner_branches', 'new_joiner_departments'):
        if f in data:
            v = data.get(f) or []
            if isinstance(v, str):
                v = [x for x in v.split(',')]
            if not isinstance(v, list):
                raise TrainingValidationError('Send a list of names.', f)
            setattr(c, f, sorted({str(x).strip()[:100] for x in v if str(x).strip()}))
    if 'owner' in data:
        oid = data.get('owner')
        c.owner = User.objects.filter(pk=oid, is_active=True).first() if oid else None
        if oid and c.owner is None:
            raise TrainingValidationError('Choose an active employee as the training owner.', 'owner')
    if 'assessment' in data:
        aid = data.get('assessment')
        if aid and not has_perm(user, 'training.manage_assessments'):
            raise TrainingValidationError('You are not allowed to link assessments.', 'assessment')
        if aid:
            from apps.assessments.models import Assessment, AssessmentItem
            a = Assessment.objects.filter(pk=aid, is_active=True).first()
            if a is None:
                raise TrainingValidationError('Choose an active assessment.', 'assessment')
            if not a.items.filter(item_type=AssessmentItem.TYPE_QUIZ).exists():
                raise TrainingValidationError('That assessment has no MCQ questions.', 'assessment')
            c.assessment = a
        elif has_perm(user, 'training.manage_assessments'):
            c.assessment = None
    if c.videos_optional and not c.assessment_id:
        raise TrainingValidationError(
            'Link an assessment to make video watching optional — employees complete the course by passing it.',
            'videos_optional')


# ── HR: courses ───────────────────────────────────────────────────────────────

class CourseListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_perm(request.user, 'training.view'):
            return _deny()
        qs = TrainingCourse.objects.select_related('owner', 'assessment')
        if request.query_params.get('archived') != '1':
            qs = qs.filter(archived_at__isnull=True)
        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(Q(title__icontains=search) | Q(category__icontains=search))
        scope = services.assignment_scope_q(request.user)
        counts = {}
        if scope is not None:
            agg = (TrainingAssignment.objects.filter(scope).values('course_id')
                   .annotate(total=Count('id'), completed=Count('id', filter=Q(status='completed'))))
            counts = {r['course_id']: r for r in agg}
        rows = []
        for c in qs[:500]:
            r = counts.get(c.id, {})
            rows.append(course_out(c, counts={'assigned_count': r.get('total', 0),
                                              'completed_count': r.get('completed', 0),
                                              'material_count': c.materials.filter(is_archived=False).count()}))
        return success('Courses.', rows)

    def post(self, request):
        if not has_perm(request.user, 'training.create'):
            return _deny()
        c = TrainingCourse(created_by=request.user)
        try:
            _apply_course(c, request.data, request.user, creating=True)
        except TrainingValidationError as exc:
            return _bad(exc)
        c.save()
        _audit(request, 'training_course_created', c.pk, {'title': c.title})
        return success('Course created.', course_out(c, detail=True), http_status=status.HTTP_201_CREATED)


class CourseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not has_perm(request.user, 'training.view'):
            return _deny()
        c = get_object_or_404(TrainingCourse.objects.select_related('owner', 'assessment'), pk=pk)
        return success('Course.', course_out(c, detail=True))

    def patch(self, request, pk):
        if not has_perm(request.user, 'training.edit'):
            return _deny()
        c = get_object_or_404(TrainingCourse, pk=pk)
        try:
            _apply_course(c, request.data, request.user, creating=False)
        except TrainingValidationError as exc:
            return _bad(exc)
        c.save()
        _audit(request, 'training_course_updated', c.pk, {k: str(request.data.get(k)) for k in request.data
                                                           if k in _COURSE_FIELDS})
        return success('Course saved.', course_out(c, detail=True))

    def delete(self, request, pk):
        if not has_perm(request.user, 'training.delete'):
            return _deny()
        c = get_object_or_404(TrainingCourse, pk=pk)
        if c.assignments.exists():
            c.archived_at, c.is_active, c.auto_assign_new_joiners = timezone.now(), False, False
            c.save(update_fields=['archived_at', 'is_active', 'auto_assign_new_joiners', 'updated_at'])
            _audit(request, 'training_course_archived', c.pk, {'title': c.title})
            return success('The course has training history, so it was archived instead of deleted.',
                           {'archived': True})
        _audit(request, 'training_course_deleted', c.pk, {'title': c.title})
        for m in c.materials.all():
            _delete_files(m)
        if c.thumbnail:
            c.thumbnail.delete(save=False)
        c.delete()
        return success('Course deleted.', {'archived': False})


def _delete_files(m: TrainingMaterial):
    for f in (m.document_file, m.video_file):
        if f:
            try:
                f.delete(save=False)
            except Exception:
                logger.warning('Could not delete training file %s', f.name)


class CourseThumbnailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, pk):
        if not has_perm(request.user, 'training.edit'):
            return _deny()
        c = get_object_or_404(TrainingCourse, pk=pk)
        upload = request.FILES.get('thumbnail')
        try:
            validate_thumbnail(upload)
        except TrainingValidationError as exc:
            return _bad(exc)
        old = c.thumbnail.name if c.thumbnail else ''
        c.thumbnail = upload
        c.save(update_fields=['thumbnail', 'updated_at'])
        if old:
            try:
                c.thumbnail.storage.delete(old)
            except Exception:
                logger.warning('Could not delete old thumbnail %s', old)
        return success('Thumbnail saved.', {'has_thumbnail': True})


# ── HR: materials ─────────────────────────────────────────────────────────────

class MaterialListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, pk):
        if not has_perm(request.user, 'training.view'):
            return _deny()
        c = get_object_or_404(TrainingCourse, pk=pk)
        return success('Materials.', [material_out(m) for m in services.active_materials(c)])

    def post(self, request, pk):
        if not has_perm(request.user, 'training.edit'):
            return _deny()
        c = get_object_or_404(TrainingCourse, pk=pk)
        d = request.data
        kind = d.get('material_type')
        title = (d.get('title') or '').strip()
        try:
            if kind not in dict(TrainingMaterial.TYPE_CHOICES):
                raise TrainingValidationError('Choose video, document or external video.', 'material_type')
            if not title:
                raise TrainingValidationError('Give the material a title.', 'title')
            m = TrainingMaterial(course=c, title=title[:200], material_type=kind,
                                 description=(d.get('description') or '').strip())
            _apply_material_options(m, d)
            upload = request.FILES.get('file')
            if kind == TrainingMaterial.TYPE_DOCUMENT:
                m.file_format = validate_document(upload)
                m.document_file = upload
            elif kind == TrainingMaterial.TYPE_VIDEO:
                m.file_format = validate_video(upload)
                m.video_file = upload
            else:
                link = parse_external_video(d.get('external_url'))
                m.external_url, m.provider, m.embed_id = link['url'], link['provider'], link['embed_id']
            if upload is not None and kind != TrainingMaterial.TYPE_EXTERNAL_VIDEO:
                m.file_size, m.original_name = upload.size, os.path.basename(upload.name or '')[:255]
            _require_video_length(m)
        except TrainingValidationError as exc:
            return _bad(exc)
        last = c.materials.order_by('-order').values_list('order', flat=True).first()
        m.order = (last or 0) + 1
        m.save()
        _audit(request, 'training_material_added', c.pk, {'material': m.title, 'type': kind})
        return success('Material added.', material_out(m), http_status=status.HTTP_201_CREATED)


def _require_video_length(m: TrainingMaterial):
    """Tracked videos need their length from HR: watched time is measured against it, and the
    length reported by the employee's browser is never trusted."""
    if m.is_tracked and not m.duration_seconds:
        raise TrainingValidationError('Enter the video length — it is used to check how much was watched.',
                                      'duration_seconds')


def _apply_material_options(m: TrainingMaterial, d):
    if 'is_required' in d:
        m.is_required = _bool(d.get('is_required'))
    if 'allow_manual_completion' in d:
        m.allow_manual_completion = _bool(d.get('allow_manual_completion'))
    for f, top in (('min_view_seconds', 7200), ('duration_seconds', 86400)):
        if f in d:
            v = d.get(f)
            try:
                val = None if v in (None, '') else max(0, min(int(float(v)), top))
            except (TypeError, ValueError):
                raise TrainingValidationError('Enter a number of seconds.', f) from None
            setattr(m, f, val if f == 'duration_seconds' else (val or 0))


class MaterialDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not has_perm(request.user, 'training.edit'):
            return _deny()
        m = get_object_or_404(TrainingMaterial, pk=pk, is_archived=False)
        d = request.data
        try:
            if 'title' in d:
                t = (d.get('title') or '').strip()
                if not t:
                    raise TrainingValidationError('Give the material a title.', 'title')
                m.title = t[:200]
            if 'description' in d:
                m.description = (d.get('description') or '').strip()
            if 'external_url' in d and m.material_type == TrainingMaterial.TYPE_EXTERNAL_VIDEO:
                link = parse_external_video(d.get('external_url'))
                m.external_url, m.provider, m.embed_id = link['url'], link['provider'], link['embed_id']
            _apply_material_options(m, d)
            if 'duration_seconds' in d or 'external_url' in d:
                _require_video_length(m)
        except TrainingValidationError as exc:
            return _bad(exc)
        m.save()
        return success('Material saved.', material_out(m))

    def delete(self, request, pk):
        if not has_perm(request.user, 'training.edit'):
            return _deny()
        m = get_object_or_404(TrainingMaterial, pk=pk, is_archived=False)
        if m.progress.exists():
            m.is_archived = True
            m.save(update_fields=['is_archived', 'updated_at'])
        else:
            _delete_files(m)
            m.delete()
        _audit(request, 'training_material_removed', m.course_id, {'material': m.title})
        return success('Material removed.')


class MaterialReorderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not has_perm(request.user, 'training.edit'):
            return _deny()
        c = get_object_or_404(TrainingCourse, pk=pk)
        ids = [str(x) for x in (request.data.get('order') or [])]
        current = {str(m.id): m for m in services.active_materials(c)}
        if sorted(ids) != sorted(current):
            return error('Send every material of the course exactly once.', data={'order': ['Incomplete list.']})
        with transaction.atomic():
            for n, mid in enumerate(ids, start=1):
                TrainingMaterial.objects.filter(pk=mid).update(order=n)
        return success('Order saved.', [material_out(m) for m in services.active_materials(c)])


# ── HR: assignment ────────────────────────────────────────────────────────────

class AssignView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not has_perm(request.user, 'training.assign'):
            return _deny()
        c = get_object_or_404(TrainingCourse, pk=pk)
        d = request.data
        scope = services.scoped_employees(request.user).filter(onboarding_status='complete')
        try:
            due = _date(d.get('due_date'), 'due_date')
            if due and due < timezone.localdate():
                raise TrainingValidationError('The due date is in the past.', 'due_date')
        except TrainingValidationError as exc:
            return _bad(exc)
        ids = [str(x) for x in (d.get('employee_ids') or [])]
        departments = [str(x).strip() for x in (d.get('departments') or []) if str(x).strip()]
        branches = [str(x).strip() for x in (d.get('branches') or []) if str(x).strip()]
        everyone = _bool(d.get('all'))
        if not (ids or departments or branches or everyone):
            return error('Choose employees, departments, branches or everyone.')
        results = {'assigned': 0, 'already_assigned': 0}
        batches = []
        if everyone:
            batches.append((scope, TrainingAssignment.SOURCE_ALL))
        else:
            if ids:
                found = scope.filter(pk__in=ids)
                if found.count() != len(set(ids)):
                    return error('Some selected employees are not in your scope.', http_status=403)
                batches.append((found, TrainingAssignment.SOURCE_INDIVIDUAL))
            if departments:
                q = Q()
                for dept in departments:
                    q |= Q(department__iexact=dept)
                batches.append((scope.filter(q), TrainingAssignment.SOURCE_DEPARTMENT))
            if branches:
                q = Q()
                for br in branches:
                    q |= Q(branch__iexact=br)
                batches.append((scope.filter(q), TrainingAssignment.SOURCE_BRANCH))
        try:
            for qs, source in batches:
                r = services.assign_course(c, list(qs), assigned_by=request.user, source=source, due_date=due)
                results['assigned'] += r['assigned']
                results['already_assigned'] += r['already_assigned']
        except services.TrainingError as exc:
            return _bad(exc)
        _audit(request, 'training_assigned', c.pk, {'course': c.title, **results,
                                                    'departments': departments, 'branches': branches,
                                                    'all': everyone, 'employees': len(ids)})
        msg = f'Assigned to {results["assigned"]} employee(s).'
        if results['already_assigned']:
            msg += f' {results["already_assigned"]} already had this course.'
        return success(msg, results)


class AssignmentDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not has_perm(request.user, 'training.assign'):
            return _deny()
        scope = services.assignment_scope_q(request.user)
        a = TrainingAssignment.objects.filter(scope, pk=pk).first() if scope is not None else None
        if a is None:
            return error('Assignment not found.', http_status=404)
        if a.status != TrainingAssignment.STATUS_ASSIGNED or a.material_progress.exists():
            return error('This employee has already started the training — it can no longer be removed.',
                         http_status=409)
        _audit(request, 'training_unassigned', a.course_id, {'employee': a.employee.full_name})
        a.delete()
        return success('Assignment removed.')


class ResetAssessmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not has_perm(request.user, 'training.manage_assessments'):
            return _deny()
        scope = services.assignment_scope_q(request.user)
        a = TrainingAssignment.objects.filter(scope, pk=pk).first() if scope is not None else None
        if a is None:
            return error('Assignment not found.', http_status=404)
        try:
            services.reset_assessment(a)
        except services.TrainingError as exc:
            return _bad(exc)
        _audit(request, 'training_assessment_reset', a.course_id, {'employee': a.employee.full_name})
        return success('Assessment attempts reset.', assignment_row(a))


class AssessmentOptionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_perm(request.user, 'training.manage_assessments'):
            return _deny()
        from apps.assessments.models import Assessment
        rows = (Assessment.objects.filter(is_active=True)
                .annotate(questions=Count('items', filter=Q(items__item_type='quiz'))).filter(questions__gt=0)
                .order_by('title'))
        return success('Assessments.', [{'id': str(a.id), 'title': a.title, 'questions': a.questions,
                                         'pass_percentage': a.pass_percentage} for a in rows])


class EmployeePickerView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_perm(request.user, 'training.assign'):
            return _deny()
        qs = services.scoped_employees(request.user).filter(onboarding_status='complete')
        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(Q(full_name__icontains=search) | Q(employee_id__icontains=search) | Q(email__icontains=search))
        all_rows = services.scoped_employees(request.user).filter(onboarding_status='complete')
        return success('Employees.', {
            'employees': [_person(u) for u in qs.order_by('full_name')[:300]],
            'departments': sorted({d for d in all_rows.values_list('department', flat=True) if d}),
            'branches': sorted({b for b in all_rows.values_list('branch', flat=True) if b}),
        })


# ── HR: progress, dashboard, reports ──────────────────────────────────────────

def _filtered_assignments(request, *, course_id=None):
    scope = services.assignment_scope_q(request.user)
    if scope is None:
        return None
    qs = TrainingAssignment.objects.filter(scope).select_related('employee', 'course')
    p = request.query_params
    course_id = course_id or p.get('course')
    if course_id:
        qs = qs.filter(course_id=course_id)
    if p.get('employee'):
        qs = qs.filter(employee_id=p['employee'])
    if p.get('department'):
        qs = qs.filter(employee__department__iexact=p['department'])
    if p.get('branch'):
        qs = qs.filter(employee__branch__iexact=p['branch'])
    st = p.get('status')
    today = timezone.localdate()
    open_states = (TrainingAssignment.STATUS_ASSIGNED, TrainingAssignment.STATUS_IN_PROGRESS)
    if st == 'overdue':
        qs = qs.filter(status__in=open_states, due_date__lt=today)
    elif st in (TrainingAssignment.STATUS_ASSIGNED, TrainingAssignment.STATUS_IN_PROGRESS):
        qs = qs.filter(status=st).exclude(due_date__lt=today)
    elif st in (TrainingAssignment.STATUS_COMPLETED, TrainingAssignment.STATUS_FAILED):
        qs = qs.filter(status=st)
    try:
        if p.get('from'):
            qs = qs.filter(created_at__date__gte=datetime.date.fromisoformat(p['from']))
        if p.get('to'):
            qs = qs.filter(created_at__date__lte=datetime.date.fromisoformat(p['to']))
    except ValueError:
        pass
    return qs


def _can_see_progress(user) -> bool:
    return services.employee_scope_q(user) is not None


class CourseProgressView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _can_see_progress(request.user):
            return _deny()
        c = get_object_or_404(TrainingCourse, pk=pk)
        qs = _filtered_assignments(request, course_id=c.pk).prefetch_related('material_progress')
        required = services.required_material_ids(c)
        rows = []
        for a in qs.order_by('employee__full_name')[:2000]:
            r = assignment_row(a)
            r['progress_percent'] = _progress_percent(a, required)
            rows.append(r)
        return success('Progress.', rows)


def _stats(qs) -> dict:
    today = timezone.localdate()
    open_states = (TrainingAssignment.STATUS_ASSIGNED, TrainingAssignment.STATUS_IN_PROGRESS)
    return {
        'assigned': qs.count(),
        'completed': qs.filter(status=TrainingAssignment.STATUS_COMPLETED).count(),
        'in_progress': qs.filter(status=TrainingAssignment.STATUS_IN_PROGRESS).exclude(due_date__lt=today).count(),
        'not_started': qs.filter(status=TrainingAssignment.STATUS_ASSIGNED).exclude(due_date__lt=today).count(),
        'overdue': qs.filter(status__in=open_states, due_date__lt=today).count(),
        'failed': qs.filter(status=TrainingAssignment.STATUS_FAILED).count(),
        'assessment_passed': qs.filter(assessment_passed=True).count(),
        'assessment_failed': qs.filter(assessment_passed=False).count(),
    }


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (has_perm(request.user, 'training.view_reports') or _can_see_progress(request.user)):
            return _deny()
        qs = _filtered_assignments(request)
        if qs is None:
            qs = TrainingAssignment.objects.none()
        courses = TrainingCourse.objects.filter(archived_at__isnull=True)
        out = {'total_courses': courses.count(), 'active_courses': courses.filter(is_active=True).count(),
               'employees_assigned': qs.values('employee_id').distinct().count(), **_stats(qs)}
        out['completion_percent'] = round(out['completed'] * 100 / out['assigned']) if out['assigned'] else 0
        return success('Training dashboard.', out)


class ReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_perm(request.user, 'training.view_reports'):
            return _deny()
        qs = _filtered_assignments(request)
        if qs is None:
            return _deny()
        qs = qs.prefetch_related('material_progress').order_by('course__title', 'employee__full_name')[:5000]
        required_by_course: dict = {}
        rows = []
        for a in qs:
            if a.course_id not in required_by_course:
                required_by_course[a.course_id] = services.required_material_ids(a.course)
            r = assignment_row(a)
            r['progress_percent'] = _progress_percent(a, required_by_course[a.course_id])
            rows.append(r)
        if request.query_params.get('export') == 'csv':
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(['Employee', 'Employee ID', 'Department', 'Branch', 'Course', 'Status', 'Progress %',
                        'Assigned', 'Due', 'Completed', 'Best score %', 'Attempts'])
            for r in rows:
                e = r['employee']
                w.writerow([_csv_safe(v) for v in [e['name'], e['employee_id'], e['department'], e['branch'], r['course_title'],
                            r['status'], r['progress_percent'], r['assigned_at'][:10], r['due_date'] or '',
                            (r['completed_at'] or '')[:10], '' if r['best_score_percent'] is None
                            else r['best_score_percent'], r['attempts_used']]])
            resp = HttpResponse(buf.getvalue(), content_type='text/csv')
            resp['Content-Disposition'] = 'attachment; filename="training-report.csv"'
            return resp
        return success('Training report.', rows)


def _csv_safe(value):
    """Text a spreadsheet would run as a formula (=, +, -, @, tab, CR) is prefixed with ' ."""
    if isinstance(value, str) and value[:1] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + value
    return value


# ── Employee: My Learning ─────────────────────────────────────────────────────

def _my_assignment(request, pk) -> TrainingAssignment | None:
    return (TrainingAssignment.objects.select_related('course', 'course__assessment')
            .filter(pk=pk, employee=request.user, course__archived_at__isnull=True).first())


def my_course_out(a: TrainingAssignment, detail=False) -> dict:
    c = a.course
    mats = list(services.active_materials(c))
    progress = {p.material_id: p for p in a.material_progress.all()}
    required = {m.id for m in mats if services.material_required(c, m)}
    done = {mid for mid, p in progress.items() if p.completed_at and mid in required}
    out = {
        **assignment_row(a), 'progress_percent': round(len(done) * 100 / len(required)) if required else (
            100 if a.status == TrainingAssignment.STATUS_COMPLETED else 0),
        'course': {k: v for k, v in course_out(c).items() if k not in (
            'auto_assign_new_joiners', 'new_joiner_deadline_days', 'new_joiner_branches', 'new_joiner_departments')},
        'material_count': len(mats),
        'starts_on': start.isoformat() if (start := services.starts_on(a)) else None,
    }
    if detail:
        out['materials'] = []
        for m in mats:
            row = material_out(m, progress.get(m.id) or TrainingMaterialProgress(material=m))
            row['is_required'] = services.material_required(c, m)      # videos may be optional for the course
            out['materials'].append(row)
        out['assessment'] = services.assessment_state(a)
    return out


class MyTrainingListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = (TrainingAssignment.objects.filter(employee=request.user, course__archived_at__isnull=True)
              .select_related('course', 'course__owner', 'course__assessment').prefetch_related('material_progress'))
        return success('My training.', [my_course_out(a) for a in qs])


class MyTrainingDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        a = _my_assignment(request, pk)
        if a is None:
            return error('Training not found.', http_status=404)
        return success('Training.', my_course_out(a, detail=True))


def _my_material(request, pk, material_id):
    a = _my_assignment(request, pk)
    if a is None:
        return None, None
    m = TrainingMaterial.objects.filter(pk=material_id, course_id=a.course_id, is_archived=False).first()
    return a, m


class MyMaterialActionView(APIView):
    """open | progress (video heartbeat) | confirm (document read / untracked video watched)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, material_id, action):
        a, m = _my_material(request, pk, material_id)
        if a is None or m is None:
            return error('Training material not found.', http_status=404)
        if a.status == TrainingAssignment.STATUS_FAILED:
            return error('This training is closed — contact HR.', http_status=409)
        try:
            if action == 'open':
                p = services.record_open(a, m)
            elif action == 'progress':
                try:
                    position = float(request.data.get('position') or 0)
                    duration = request.data.get('duration')
                    duration = float(duration) if duration not in (None, '') else None
                except (TypeError, ValueError):
                    return error('position and duration must be numbers.')
                p = services.record_heartbeat(a, m, position, duration)
            elif action == 'confirm':
                p = services.confirm_material(a, m)
            else:
                return error('Unknown action.', http_status=404)
        except services.TrainingError as exc:
            return _bad(exc)
        a.refresh_from_db()
        return success('Saved.', {'material': material_out(m, p), 'status': a.display_status,
                                  'assessment': services.assessment_state(a)})


class MyAssessmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, action):
        a = _my_assignment(request, pk)
        if a is None:
            return error('Training not found.', http_status=404)
        try:
            if action == 'start':
                attempt, questions = services.start_attempt(a)
                return success('Assessment started.', {
                    'attempt_id': str(attempt.id), 'attempt_number': attempt.attempt_number,
                    'started_at': attempt.started_at.isoformat(), 'questions': questions,
                    'time_limit_mins': services.assessment_state(a)['time_limit_mins']})
            if action == 'submit':
                attempt = services.submit_attempt(a, request.data.get('answers') or {})
                a.refresh_from_db()
                return success('Assessment submitted.', {
                    'score': attempt.score, 'max_score': attempt.max_score, 'percentage': attempt.percentage,
                    'pass_percentage': attempt.pass_percentage, 'passed': attempt.passed,
                    'status': a.display_status, 'assessment': services.assessment_state(a)})
        except services.TrainingError as exc:
            return _bad(exc)
        return error('Unknown action.', http_status=404)


# ── Files ─────────────────────────────────────────────────────────────────────

def _can_open_material(user, m: TrainingMaterial) -> bool:
    if services.can_manage_courses(user):
        return True
    return TrainingAssignment.objects.filter(employee=user, course_id=m.course_id,
                                             course__archived_at__isnull=True).exists() and not m.is_archived


def _read(field) -> bytes:
    reader = getattr(field.storage, 'read_via_download_api', None)
    if reader:
        return reader(field.name)
    with field.open('rb') as fh:
        return fh.read()


def _ranged(content: bytes, content_type: str, range_header: str):
    """Serve bytes with HTTP Range support (local storage video playback)."""
    total = len(content)
    if range_header.startswith('bytes='):
        try:
            start_s, end_s = range_header[6:].split(',')[0].split('-')
            start = int(start_s) if start_s else max(0, total - int(end_s))
            end = min(int(end_s), total - 1) if (end_s and start_s) else total - 1
        except ValueError:
            start, end = 0, total - 1
        if start >= total:
            resp = HttpResponse(status=416)
            resp['Content-Range'] = f'bytes */{total}'
            return resp
        resp = HttpResponse(content[start:end + 1], status=206, content_type=content_type)
        resp['Content-Range'] = f'bytes {start}-{end}/{total}'
    else:
        resp = HttpResponse(content, content_type=content_type)
    resp['Accept-Ranges'] = 'bytes'
    return resp


def _private(resp, filename=''):
    resp['Cache-Control'] = 'private, no-store'
    resp['X-Content-Type-Options'] = 'nosniff'
    if filename:
        resp['Content-Disposition'] = f'inline; filename="{filename}"'
    return resp


class MaterialFileView(APIView):
    """The document / uploaded video bytes, only for assigned employees and course managers."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        m = get_object_or_404(TrainingMaterial, pk=pk)
        if not _can_open_material(request.user, m):
            return error('Not found.', http_status=404)
        field = m.document_file if m.material_type == TrainingMaterial.TYPE_DOCUMENT else m.video_file
        if not field:
            return error('This material has no file.', http_status=404)
        try:
            content = _read(field)
        except Exception:
            logger.exception('Training file %s could not be read', m.pk)
            return error('The file could not be loaded. Please try again.', http_status=502)
        ctype = CONTENT_TYPES.get(m.file_format, 'application/octet-stream')
        safe = f'{m.title[:60].replace(chr(34), "")}.{m.file_format or "bin"}'
        if m.material_type == TrainingMaterial.TYPE_VIDEO:
            return _private(_ranged(content, ctype, request.META.get('HTTP_RANGE', '')))
        return _private(HttpResponse(content, content_type=ctype), safe)


class MaterialVideoSourceView(APIView):
    """{url} — a signed, private playback URL for an uploaded video (cloud storage),
    or {url: null} when the file must be streamed through the API (local storage)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        m = get_object_or_404(TrainingMaterial, pk=pk, material_type=TrainingMaterial.TYPE_VIDEO)
        if not _can_open_material(request.user, m) or not m.video_file:
            return error('Not found.', http_status=404)
        signer = getattr(m.video_file.storage, 'signed_playback_url', None)
        url = None
        if signer:
            try:
                url = signer(m.video_file.name, m.file_format)
            except Exception:
                logger.exception('Signed URL failed for training video %s', m.pk)
        resp = success('Video source.', {'url': url, 'content_type': CONTENT_TYPES.get(m.file_format, 'video/mp4')})
        resp['Cache-Control'] = 'private, no-store'
        return resp


class CourseThumbnailFileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        c = get_object_or_404(TrainingCourse, pk=pk)
        allowed = has_perm(request.user, 'training.view') or c.assignments.filter(employee=request.user).exists()
        if not allowed or not c.thumbnail:
            return error('Not found.', http_status=404)
        try:
            content = _read(c.thumbnail)
        except Exception:
            return error('The image could not be loaded.', http_status=502)
        ctype = 'image/png' if content.startswith(b'\x89PNG') else 'image/jpeg'
        resp = HttpResponse(content, content_type=ctype)
        resp['Cache-Control'] = 'private, max-age=300'
        resp['X-Content-Type-Options'] = 'nosniff'
        return resp


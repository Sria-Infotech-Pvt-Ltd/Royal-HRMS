import logging

from django.db import transaction
from django.db.models import Prefetch
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from ..models import Assessment, AssessmentItem, AssessmentSettings, CandidateAssignment
from ..serializers import (
    AssessmentCreateSerializer,
    AssessmentItemCreateSerializer,
    AssessmentItemSerializer,
    AssessmentSerializer,
    ResultsAssignmentSerializer,
)

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user:
        return False
    if getattr(user, 'is_superuser', False):
        return True
    if not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


def _send_assessment_email(recipient_email: str, context: dict, template_name: str = 'assessment_assigned') -> None:
    try:
        from apps.accounts.utils import send_template_email
        send_template_email(
            recipient_email=recipient_email,
            template_name=template_name,
            context=context,
        )
    except Exception:
        logger.exception('Failed to send %s email to %s', template_name, recipient_email)


def _queue_assignment_emails(assignment_ids: list, template_name: str) -> None:
    """
    Enqueue assignment-notification email delivery for one or more
    CandidateAssignment ids, after the current transaction commits.

    Queuing failure (e.g. broker down) is logged, not raised — the
    assignment row(s) have already been saved successfully by this point,
    so the request must not fail on their account.
    """
    if not assignment_ids:
        return
    from apps.assessments.tasks import send_assessment_assignment_emails_task

    def _dispatch(ids=list(assignment_ids), tpl=template_name):
        try:
            # retry=False + ignore_result=True — bounds broker/backend
            # retries so a down Redis can't block this request; see the
            # referral-submission dispatch in recruitment/views.py.
            send_assessment_assignment_emails_task.apply_async(
                args=[ids, tpl], retry=False, ignore_result=True,
            )
        except Exception as exc:
            logger.error(
                'Failed to queue assessment assignment email(s) for %s: %s',
                ids, exc, exc_info=True,
            )

    transaction.on_commit(_dispatch)


def _queue_assignment_email(assignment_id, template_name: str) -> None:
    """Single-assignment convenience wrapper around _queue_assignment_emails."""
    _queue_assignment_emails([assignment_id], template_name)


class AssessmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'assessments.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        assignments_qs = CandidateAssignment.objects.select_related(
            'candidate', 'employee',
        ).order_by('-created_at')
        queryset = Assessment.objects.prefetch_related(
            'items',
            Prefetch('assignments', queryset=assignments_qs),
        ).all()
        if request.query_params.get('active_only'):
            queryset = queryset.filter(is_active=True)
        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        global_settings = AssessmentSettings.load()
        serializer = AssessmentSerializer(
            page_obj.object_list, many=True, context={'settings': global_settings},
        )
        return success('Assessments retrieved.', paginated_data(paginator, page_obj, serializer.data))

    def post(self, request):
        if not _has_perm(request.user, 'assessments.create'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = AssessmentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        assessment = serializer.save(created_by=request.user)
        logger.info('Assessment "%s" created by %s', assessment.title, request.user.email)
        ctx = {'settings': AssessmentSettings.load()}
        return success('Assessment created.', AssessmentSerializer(assessment, context=ctx).data, http_status=status.HTTP_201_CREATED)


class AssessmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return Assessment.objects.prefetch_related('items', 'sections').get(pk=pk)
        except Assessment.DoesNotExist:
            return None

    def get(self, request, assessment_id):
        if not _has_perm(request.user, 'assessments.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        assessment = self._get(assessment_id)
        if not assessment:
            return error('Assessment not found.', http_status=status.HTTP_404_NOT_FOUND)
        ctx = {'settings': AssessmentSettings.load()}
        return success('Assessment retrieved.', AssessmentSerializer(assessment, context=ctx).data)

    def put(self, request, assessment_id):
        if not _has_perm(request.user, 'assessments.edit'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        assessment = self._get(assessment_id)
        if not assessment:
            return error('Assessment not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = AssessmentCreateSerializer(assessment, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        logger.info('Assessment "%s" updated by %s', assessment.title, request.user.email)
        ctx = {'settings': AssessmentSettings.load()}
        return success('Assessment updated.', AssessmentSerializer(serializer.instance, context=ctx).data)

    def delete(self, request, assessment_id):
        if not _has_perm(request.user, 'assessments.delete'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        assessment = self._get(assessment_id)
        if not assessment:
            return error('Assessment not found.', http_status=status.HTTP_404_NOT_FOUND)
        if assessment.assignments.filter(
            status__in=[CandidateAssignment.STATUS_PENDING, CandidateAssignment.STATUS_IN_PROGRESS]
        ).exists():
            return error(
                'Cannot delete an assessment with active candidate assignments.',
                http_status=status.HTTP_409_CONFLICT,
            )
        assessment.delete()
        logger.info('Assessment "%s" deleted by %s', assessment.title, request.user.email)
        return success('Assessment deleted.')


class AssessmentItemListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, assessment_id):
        if not _has_perm(request.user, 'assessments.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            assessment = Assessment.objects.get(pk=assessment_id)
        except Assessment.DoesNotExist:
            return error('Assessment not found.', http_status=status.HTTP_404_NOT_FOUND)
        items = assessment.items.all()
        return success('Items retrieved.', AssessmentItemSerializer(items, many=True).data)

    def post(self, request, assessment_id):
        if not _has_perm(request.user, 'assessments.edit'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        try:
            assessment = Assessment.objects.get(pk=assessment_id)
        except Assessment.DoesNotExist:
            return error('Assessment not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = AssessmentItemCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        section = serializer.validated_data.get('section')
        if section and section.assessment_id != assessment.pk:
            return error('Section does not belong to this assessment.')
        item = serializer.save(assessment=assessment)
        logger.info('Item "%s" added to assessment "%s" by %s', item.title, assessment.title, request.user.email)
        return success('Item added.', AssessmentItemSerializer(item).data, http_status=status.HTTP_201_CREATED)


class AssessmentItemDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, item_id):
        try:
            return AssessmentItem.objects.select_related('assessment').get(pk=item_id)
        except AssessmentItem.DoesNotExist:
            return None

    def put(self, request, item_id):
        if not _has_perm(request.user, 'assessments.edit'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        item = self._get(item_id)
        if not item:
            return error('Item not found.', http_status=status.HTTP_404_NOT_FOUND)
        serializer = AssessmentItemCreateSerializer(item, data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        serializer.save()
        return success('Item updated.', AssessmentItemSerializer(item).data)

    def delete(self, request, item_id):
        if not _has_perm(request.user, 'assessments.edit'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        item = self._get(item_id)
        if not item:
            return error('Item not found.', http_status=status.HTTP_404_NOT_FOUND)
        title = item.title
        item.delete()
        logger.info('Item "%s" deleted by %s', title, request.user.email)
        return success('Item deleted.')


class AssignAssessmentView(APIView):
    """
    POST /api/assessments/assign/

    Assign an assessment to one of four targets — resolved by which key is sent:

      candidate_id   → single new-joiner candidate
      employee_id    → single existing employee  (e.g. "RSS00023")
      department     → all active employees in that department
      assign_to      → "company"  to assign to every active employee

    Optional:
      deadline       → ISO-8601 datetime string  (e.g. "2026-08-31T23:59:59")
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'assessments.edit'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        import re
        _UUID_RE = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.I,
        )

        assessment_id = request.data.get('assessment_id')
        candidate_id  = request.data.get('candidate_id')
        employee_id   = request.data.get('employee_id')
        department    = request.data.get('department', '').strip()
        assign_to     = request.data.get('assign_to', '').strip().lower()
        deadline_raw  = request.data.get('deadline')
        template_name = (request.data.get('template_name') or 'assessment_assigned').strip()

        if not assessment_id:
            return error('assessment_id is required.')

        # If candidate_id is not a UUID AND not a plain integer (Candidate PK), treat it as employee_id
        if candidate_id and not _UUID_RE.match(str(candidate_id)) and not str(candidate_id).isdigit():
            employee_id  = candidate_id
            candidate_id = None

        # Exactly one target must be provided
        targets = [bool(candidate_id), bool(employee_id), bool(department), assign_to == 'company']
        if sum(targets) != 1:
            return error(
                'Provide exactly one of: candidate_id, employee_id, department, or assign_to="company".'
            )

        try:
            assessment = Assessment.objects.prefetch_related('items').get(pk=assessment_id)
        except Assessment.DoesNotExist:
            return error('Assessment not found.', http_status=status.HTTP_404_NOT_FOUND)

        # Parse deadline
        deadline = None
        if deadline_raw:
            from django.utils import timezone as tz
            from django.utils.dateparse import parse_datetime
            deadline = parse_datetime(str(deadline_raw))
            if deadline is None:
                return error('deadline must be a valid ISO-8601 datetime string (e.g. "2026-08-31T23:59:59").')
            if tz.is_naive(deadline):
                deadline = tz.make_aware(deadline)

        max_score = assessment.compute_max_score()

        from apps.accounts.models import Company
        company    = Company.objects.first()
        company_name = company.company_name if company else ''
        portal_url   = (company.portal_url if company else '') or ''

        # ── Single candidate (new joiner) or employee sent as candidate_id ──────
        if candidate_id:
            from apps.recruitment.models import Candidate
            from apps.accounts.models import User

            candidate = None
            try:
                candidate = Candidate.objects.get(pk=candidate_id)
            except (Candidate.DoesNotExist, ValueError):
                # candidate_id is not a Candidate PK — the employee-assign UI
                # sends the User UUID here, so fall through to the employee path.
                pass

            if candidate is None:
                # Try resolving as a User UUID (primary key)
                try:
                    employee = User.objects.get(pk=candidate_id)
                except (User.DoesNotExist, ValueError):
                    return error('Candidate or employee not found.', http_status=status.HTTP_404_NOT_FOUND)

                assignment, created = CandidateAssignment.objects.get_or_create(
                    employee=employee,
                    assessment=assessment,
                    defaults={'assigned_by': request.user, 'max_score': max_score, 'deadline': deadline},
                )
                if not created:
                    return error('Assessment already assigned to this employee.', http_status=status.HTTP_409_CONFLICT)

                User.objects.filter(
                    pk=employee.pk, assessment_status=User.ASSESSMENT_COMPLETE,
                ).update(assessment_status=User.ASSESSMENT_PENDING)

                if employee.email:
                    _queue_assignment_email(assignment.id, template_name)

                logger.info('Assessment "%s" assigned to employee %s by %s', assessment.title, employee.employee_id, request.user.email)
                return success('Assessment assigned to employee.', {'assignment_id': str(assignment.id)}, http_status=status.HTTP_201_CREATED)

            # ── Candidate (new joiner) path ───────────────────────────────────
            assignment, created = CandidateAssignment.objects.get_or_create(
                candidate=candidate,
                assessment=assessment,
                defaults={'assigned_by': request.user, 'max_score': max_score, 'deadline': deadline},
            )
            if not created:
                return error('Assessment already assigned to this candidate.', http_status=status.HTTP_409_CONFLICT)

            if candidate.portal_user_id:
                User.objects.filter(
                    pk=candidate.portal_user_id, assessment_status=User.ASSESSMENT_COMPLETE
                ).update(assessment_status=User.ASSESSMENT_PENDING)

            if candidate.email and candidate.portal_user_id:
                _queue_assignment_email(assignment.id, template_name)

            logger.info('Assessment "%s" assigned to candidate %s by %s', assessment.title, candidate_id, request.user.email)
            return success('Assessment assigned.', {'assignment_id': str(assignment.id)}, http_status=status.HTTP_201_CREATED)

        # ── Single employee ───────────────────────────────────────────────────
        if employee_id:
            from apps.accounts.models import User
            try:
                employee = User.objects.get(employee_id=employee_id)
            except User.DoesNotExist:
                return error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)

            assignment, created = CandidateAssignment.objects.get_or_create(
                employee=employee,
                assessment=assessment,
                defaults={'assigned_by': request.user, 'max_score': max_score, 'deadline': deadline},
            )
            if not created:
                return error('Assessment already assigned to this employee.', http_status=status.HTTP_409_CONFLICT)

            User.objects.filter(
                pk=employee.pk, assessment_status=User.ASSESSMENT_COMPLETE,
            ).update(assessment_status=User.ASSESSMENT_PENDING)

            if employee.email:
                _queue_assignment_email(assignment.id, template_name)

            logger.info('Assessment "%s" assigned to employee %s by %s', assessment.title, employee_id, request.user.email)
            return success('Assessment assigned to employee.', {'assignment_id': str(assignment.id)}, http_status=status.HTTP_201_CREATED)

        # ── Department or company-wide (bulk) ─────────────────────────────────
        from apps.accounts.models import User
        employee_qs = User.objects.filter(is_active=True).exclude(role=None).exclude(employee_id='')
        if department:
            employee_qs = employee_qs.filter(department__iexact=department)
            if not employee_qs.exists():
                return error(f'No active employees found in department "{department}".')

        employees = list(employee_qs.only('id', 'employee_id', 'full_name', 'email'))

        # One query to find who already has this assessment — replaces the
        # old per-employee get_or_create() (one SELECT + maybe one INSERT
        # per employee, i.e. up to ~2 x N queries for N employees).
        already_assigned_ids = set(
            CandidateAssignment.objects.filter(
                assessment=assessment,
                employee_id__in=[emp.pk for emp in employees],
            ).values_list('employee_id', flat=True)
        )

        to_create = [
            CandidateAssignment(
                employee=emp,
                assessment=assessment,
                assigned_by=request.user,
                max_score=max_score,
                deadline=deadline,
            )
            for emp in employees if emp.pk not in already_assigned_ids
        ]

        # ignore_conflicts guards the narrow race of two overlapping bulk
        # assigns for the same assessment — the same protection the old
        # per-row get_or_create gave for free — without reintroducing N+1.
        CandidateAssignment.objects.bulk_create(to_create, ignore_conflicts=True, batch_size=500)

        assigned = len(to_create)
        skipped  = len(employees) - assigned

        newly_assigned_pks = [obj.employee_id for obj in to_create]
        if newly_assigned_pks:
            User.objects.filter(
                pk__in=newly_assigned_pks, assessment_status=User.ASSESSMENT_COMPLETE,
            ).update(assessment_status=User.ASSESSMENT_PENDING)

        # obj.employee is the in-memory User instance passed in above, so
        # this is a plain attribute read — no extra query per assignment.
        assignment_ids_to_email = [obj.id for obj in to_create if obj.employee.email]
        _queue_assignment_emails(assignment_ids_to_email, template_name)

        scope = f'department "{department}"' if department else 'entire company'
        logger.info(
            'Assessment "%s" bulk-assigned to %s — %d assigned, %d skipped — by %s',
            assessment.title, scope, assigned, skipped, request.user.email,
        )
        return success(
            f'Assessment assigned. {assigned} new assignment(s), {skipped} already had it.',
            {'assigned_count': assigned, 'skipped_count': skipped},
            http_status=status.HTTP_201_CREATED,
        )


class EmailTemplateOptionsView(APIView):
    """
    GET /api/assessments/email-template-options/
    Returns a flat list of {name, display_name} for all active email templates.
    Used to populate the template selector in the Assign Assessment modal.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import EmailTemplate
        templates = list(
            EmailTemplate.objects
            .filter(is_active=True)
            .order_by('display_name')
            .values('name', 'display_name')
        )
        return success('Email templates retrieved.', templates)


class CandidateResultsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, candidate_id):
        if not _has_perm(request.user, 'assessments.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        from apps.recruitment.models import Candidate
        try:
            candidate = Candidate.objects.get(pk=candidate_id)
        except Candidate.DoesNotExist:
            return error('Candidate not found.', http_status=status.HTTP_404_NOT_FOUND)
        assignments = (
            CandidateAssignment.objects.select_related('assessment')
                                       .prefetch_related(
                                           'responses', 'responses__item',
                                           'assessment__items',
                                           'assessment__sections',
                                       )
                                       .filter(candidate=candidate)
        )
        serializer = ResultsAssignmentSerializer(assignments, many=True)
        return success('Results retrieved.', {
            'candidate_name': candidate.name,
            'candidate_email': candidate.email,
            'assignments': serializer.data,
        })

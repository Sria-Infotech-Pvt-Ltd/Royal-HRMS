import logging

from django.db.models import Sum
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from ..models import Assessment, AssessmentItem, CandidateAssignment
from ..serializers import (
    AssessmentCreateSerializer,
    AssessmentItemCreateSerializer,
    AssessmentItemSerializer,
    AssessmentSerializer,
    ResultsAssignmentSerializer,
)

logger = logging.getLogger(__name__)


def _has_perm(user, codename: str) -> bool:
    if not user or not user.role:
        return False
    return user.role.role_permissions.filter(permission__codename=codename).exists()


class AssessmentListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'assessments.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        queryset = Assessment.objects.prefetch_related('items').all()
        if request.query_params.get('active_only'):
            queryset = queryset.filter(is_active=True)
        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = AssessmentSerializer(page_obj.object_list, many=True)
        return success('Assessments retrieved.', paginated_data(paginator, page_obj, serializer.data))

    def post(self, request):
        if not _has_perm(request.user, 'assessments.create'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        serializer = AssessmentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        assessment = serializer.save(created_by=request.user)
        logger.info('Assessment "%s" created by %s', assessment.title, request.user.email)
        return success('Assessment created.', AssessmentSerializer(assessment).data, http_status=status.HTTP_201_CREATED)


class AssessmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        try:
            return Assessment.objects.prefetch_related('items').get(pk=pk)
        except Assessment.DoesNotExist:
            return None

    def get(self, request, assessment_id):
        if not _has_perm(request.user, 'assessments.view'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        assessment = self._get(assessment_id)
        if not assessment:
            return error('Assessment not found.', http_status=status.HTTP_404_NOT_FOUND)
        return success('Assessment retrieved.', AssessmentSerializer(assessment).data)

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
        return success('Assessment updated.', AssessmentSerializer(assessment).data)

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
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not _has_perm(request.user, 'assessments.edit'):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        from apps.recruitment.models import Candidate
        candidate_id  = request.data.get('candidate_id')
        assessment_id = request.data.get('assessment_id')
        if not candidate_id or not assessment_id:
            return error('candidate_id and assessment_id are required.')
        try:
            candidate  = Candidate.objects.get(pk=candidate_id)
            assessment = Assessment.objects.prefetch_related('items').get(pk=assessment_id)
        except (Candidate.DoesNotExist, Assessment.DoesNotExist) as exc:
            return error(str(exc).split('"')[0] + ' not found.', http_status=status.HTTP_404_NOT_FOUND)
        max_score = assessment.items.filter(
            item_type=AssessmentItem.TYPE_QUIZ
        ).aggregate(total=Sum('pass_score'))['total'] or 0
        assignment, created = CandidateAssignment.objects.get_or_create(
            candidate=candidate,
            assessment=assessment,
            defaults={'assigned_by': request.user, 'max_score': max_score},
        )
        if not created:
            return error('Assessment already assigned to this candidate.', http_status=status.HTTP_409_CONFLICT)
        logger.info('Assessment "%s" assigned to candidate %s by %s', assessment.title, candidate_id, request.user.email)

        # Flip portal user's assessment_status to pending so the candidate
        # is redirected to the assessments page on next login
        if candidate.portal_user_id:
            from apps.accounts.models import User
            (
                User.objects
                .filter(pk=candidate.portal_user_id, assessment_status=User.ASSESSMENT_COMPLETE)
                .update(assessment_status=User.ASSESSMENT_PENDING)
            )

        # Notify the candidate by email if they have a portal account
        if candidate.email and candidate.portal_user_id:
            try:
                from apps.accounts.models import Company
                from apps.accounts.utils import send_template_email
                company    = Company.objects.first()
                portal_url = (company.portal_url if company else '') or ''
                send_template_email(
                    recipient_email=candidate.email,
                    template_name='assessment_assigned',
                    context={
                        'candidate_name':   candidate.name,
                        'assessment_title': assessment.title,
                        'company_name':     company.company_name if company else '',
                        'portal_url':       portal_url,
                    },
                )
            except Exception:
                logger.exception('Failed to send assessment_assigned email to %s', candidate.email)

        return success('Assessment assigned.', {'assignment_id': str(assignment.id)}, http_status=status.HTTP_201_CREATED)


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
                                       .prefetch_related('responses', 'responses__item', 'assessment__items')
                                       .filter(candidate=candidate)
        )
        serializer = ResultsAssignmentSerializer(assignments, many=True)
        return success('Results retrieved.', {
            'candidate_name': candidate.name,
            'candidate_email': candidate.email,
            'assignments': serializer.data,
        })

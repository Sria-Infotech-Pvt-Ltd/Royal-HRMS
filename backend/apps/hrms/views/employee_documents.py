import logging

from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from ..models import EMP_DOC_VERIFIED, EmployeeDocumentSubmission
from ..serializers import (
    EmployeeDocumentSubmissionCreateSerializer,
    EmployeeDocumentSubmissionSerializer,
)

logger = logging.getLogger(__name__)


class EmployeeDocumentSubmissionListCreateView(APIView):
    """GET/POST /document-submissions/ — ESS "Documents" self-service
    submission list. Always scoped to the requesting employee; this is a
    private "my documents" view, not the org-wide Document Center. The
    employee is always resolved from request.user, never from client input,
    so a submission can never be created on someone else's behalf here."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request):
        queryset = EmployeeDocumentSubmission.objects.filter(employee=request.user)
        page_obj, paginator = paginate(queryset, request, default_page_size=20)
        serializer = EmployeeDocumentSubmissionSerializer(page_obj.object_list, many=True)
        return success('Document submissions retrieved.', paginated_data(paginator, page_obj, serializer.data))

    def post(self, request):
        serializer = EmployeeDocumentSubmissionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))

        submission = serializer.save(employee=request.user)
        logger.info(
            'Document submission %s (%s) recorded for %s',
            submission.file_name, submission.category, request.user.email,
        )
        return success(
            'Document submitted for verification.',
            EmployeeDocumentSubmissionSerializer(submission).data,
            http_status=201,
        )


class EmployeeDocumentSubmissionDetailView(APIView):
    """DELETE /document-submissions/<id>/ — an employee withdrawing one of
    their own submissions. Scoped to request.user, so another employee's
    submission 404s rather than leaking its existence. A document HR has
    already verified is part of the employee's record and cannot be removed
    from here."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        submission = EmployeeDocumentSubmission.objects.filter(pk=pk, employee=request.user).first()
        if submission is None:
            return error('Document not found.', http_status=404)
        if submission.status == EMP_DOC_VERIFIED:
            return error('A verified document cannot be deleted. Please contact HR.', http_status=400)

        file_name = submission.file_name
        if submission.file:
            try:
                submission.file.delete(save=False)
            except Exception:
                # A storage hiccup must not block the employee from removing the record;
                # the orphaned file is logged for cleanup.
                logger.exception('Could not remove stored file for document submission %s', submission.pk)
        submission.delete()
        logger.info('Document submission %s deleted by %s', file_name, request.user.email)
        return success('Document deleted.', None)

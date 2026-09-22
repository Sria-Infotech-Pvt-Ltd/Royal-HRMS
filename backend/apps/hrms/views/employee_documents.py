import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

from ..models import EmployeeDocumentSubmission
from ..serializers import (
    EmployeeDocumentSubmissionCreateSerializer,
    EmployeeDocumentSubmissionSerializer,
)

logger = logging.getLogger(__name__)


class EmployeeDocumentSubmissionListCreateView(APIView):
    """GET/POST /documents/submissions/ — ESS "Documents" self-service
    submission list. Always scoped to the requesting employee; this is a
    private "my documents" view, not the org-wide Document Center. The
    employee is always resolved from request.user, never from client input,
    so a submission can never be created on someone else's behalf here."""
    permission_classes = [IsAuthenticated]

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

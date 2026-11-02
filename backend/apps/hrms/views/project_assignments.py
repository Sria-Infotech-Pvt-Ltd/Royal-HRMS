import logging

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, get_client_ip, success
from apps.accounts.authentication_external import ExternalAPIKeyAuthentication
from apps.accounts.models import AuditLog
from apps.accounts.throttles import ExternalWebhookThrottle
from apps.hrms.models import ProjectSyncLog
from apps.hrms.serializers_project_assignment import (
    WEBHOOK_EVENT_PROJECTS_CHANGED,
    ProjectsChangedWebhookSerializer,
)
from apps.hrms.services_project_sync import SOURCE_WEBHOOK, sync_employee_snapshot

logger = logging.getLogger(__name__)


class ProjectAssignmentsWebhookView(APIView):
    """POST /api/external/project-assignments/ — Project Budgeting pushes an employee's complete current project list
    here (event employee.projects_changed). X-API-Key auth, same as the read-only external APIs.

    A well-formed push always gets 2xx — even for an employee_id we don't have yet (it's stored, logged and reported to
    admins) — because the sender retries on anything else. A malformed body gets 400 (they don't retry 4xx) and is
    written to the sync log so admins can see it. An unexpected failure is logged and surfaces as 500 so they retry."""
    authentication_classes = [ExternalAPIKeyAuthentication]
    permission_classes     = [IsAuthenticated]
    throttle_classes       = [ExternalWebhookThrottle]

    def post(self, request):
        client_name = request.auth.name
        serializer = ProjectsChangedWebhookSerializer(data=request.data)
        if not serializer.is_valid():
            message = first_error(serializer.errors)
            employee_code = str(request.data.get('employee_id', ''))[:20] if hasattr(request.data, 'get') else ''
            ProjectSyncLog.objects.create(
                source=SOURCE_WEBHOOK, triggered_by=client_name, employee_code=employee_code,
                status=ProjectSyncLog.STATUS_FAILED, message=f'Rejected malformed push: {message}'[:1000],
            )
            return error(message)
        payload = serializer.validated_data

        if payload['event'] != WEBHOOK_EVENT_PROJECTS_CHANGED:
            return success('Event ignored.')

        employee_code = payload['employee_id']
        result = sync_employee_snapshot(employee_code, payload['rows'], source=SOURCE_WEBHOOK, triggered_by=client_name)

        AuditLog.objects.create(
            user=None,
            action='external_project_assignments_push',
            module='external_api',
            changes={'client': client_name, 'employee_id': employee_code, 'saved': result['saved'],
                     'changed': result['changed'], 'removed': result['removed']},
            ip_address=get_client_ip(request),
        )
        return success('Project assignments updated.', {
            'employee_id': employee_code, 'saved': result['saved'], 'changed': result['changed'],
            'removed': result['removed'], 'is_matched': result['is_matched'],
        })

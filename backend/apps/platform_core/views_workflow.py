"""Phase 3B Task D+H — workflow admin API + the unified "My Approvals" inbox."""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import HasSettingsPermission
from core.responses import error, success

from apps.platform_core import services_workflow as wf
from apps.platform_core import services_workflow_definitions as wf_defs
from apps.platform_core.models import (
    Delegation, WorkflowApproverOverride, WorkflowDefinition, WorkflowInstance, WorkflowStep, WorkflowTask,
)
from apps.platform_core.serializers_workflow import (
    DelegationSerializer, WorkflowApproverOverrideSerializer, WorkflowDefinitionSerializer,
    WorkflowInstanceSerializer, WorkflowStepSerializer, WorkflowTaskSerializer,
)
from apps.platform_core.views import _BaseDetailView, _BaseListCreateView


class WorkflowDefinitionListCreateView(_BaseListCreateView):
    model = WorkflowDefinition
    serializer_class = WorkflowDefinitionSerializer
    search_fields = ['code', 'name']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        entity_code = request.query_params.get('entity')
        if entity_code:
            qs = qs.filter(entity__code=entity_code)
        return qs


class WorkflowDefinitionDetailView(_BaseDetailView):
    model = WorkflowDefinition
    serializer_class = WorkflowDefinitionSerializer


class WorkflowStepListCreateView(_BaseListCreateView):
    model = WorkflowStep
    serializer_class = WorkflowStepSerializer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        definition_id = request.query_params.get('definition')
        if definition_id:
            qs = qs.filter(definition_id=definition_id)
        return qs


class WorkflowStepDetailView(_BaseDetailView):
    model = WorkflowStep
    serializer_class = WorkflowStepSerializer


class WorkflowDefinitionValidateView(APIView):
    permission_classes = [HasSettingsPermission]

    def post(self, request, pk):
        definition = WorkflowDefinition.objects.filter(pk=pk).first()
        if definition is None:
            return error('Not found.', http_status=404)
        errors = wf_defs.validate(definition)
        return success('Validation complete.', {'valid': not errors, 'errors': errors})


class WorkflowDefinitionPublishView(APIView):
    permission_classes = [HasSettingsPermission]

    def post(self, request, pk):
        definition = WorkflowDefinition.objects.filter(pk=pk).first()
        if definition is None:
            return error('Not found.', http_status=404)
        try:
            wf_defs.publish(definition)
        except wf_defs.WorkflowValidationError as exc:
            return error(exc.message, data={'errors': exc.errors}, http_status=400)
        return success('Published.', WorkflowDefinitionSerializer(definition).data)


class WorkflowDefinitionImpactPreviewView(APIView):
    permission_classes = [HasSettingsPermission]

    def get(self, request, pk):
        definition = WorkflowDefinition.objects.filter(pk=pk).first()
        if definition is None:
            return error('Not found.', http_status=404)
        return success('Impact computed.', {'matching_open_records': wf_defs.impact_preview(definition)})


class WorkflowApproverOverrideListCreateView(_BaseListCreateView):
    model = WorkflowApproverOverride
    serializer_class = WorkflowApproverOverrideSerializer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        employee_id = request.query_params.get('employee')
        if employee_id:
            qs = qs.filter(employee_id=employee_id)
        return qs


class WorkflowApproverOverrideDetailView(_BaseDetailView):
    model = WorkflowApproverOverride
    serializer_class = WorkflowApproverOverrideSerializer


class DelegationListCreateView(APIView):
    """Users manage their own; admins manage all (Task H.1)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Delegation.objects.all() if request.query_params.get('all') == 'true' and _is_admin(request.user) else Delegation.objects.filter(from_user=request.user)
        page_obj, paginator = paginate(qs, request)
        return success('Delegations retrieved.', paginated_data(paginator, page_obj, DelegationSerializer(page_obj, many=True).data))

    def post(self, request):
        data = dict(request.data)
        if not _is_admin(request.user):
            data['from_user'] = request.user.pk
        serializer = DelegationSerializer(data=data)
        if not serializer.is_valid():
            return error('Validation failed.', data=serializer.errors, http_status=400)
        obj = serializer.save()
        return success('Delegation created.', DelegationSerializer(obj).data, http_status=201)


def _is_admin(user) -> bool:
    from core.permissions import has_perm
    return has_perm(user, 'settings.edit')


class MyApprovalsInboxView(APIView):
    """Task D.1 — GET /api/v1/workflow/tasks/?status=&entity=&overdue=&delegated="""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = WorkflowTask.objects.filter(assignee=request.user).select_related('step', 'instance__definition__entity')
        status_param = request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        entity_code = request.query_params.get('entity')
        if entity_code:
            qs = qs.filter(instance__definition__entity__code=entity_code)
        if request.query_params.get('overdue') == 'true':
            from django.utils import timezone
            qs = qs.filter(due_at__lt=timezone.now(), status=WorkflowTask.STATUS_PENDING)
        if request.query_params.get('delegated') == 'true':
            qs = qs.exclude(original_assignee__isnull=True)

        page_obj, paginator = paginate(qs, request)
        return success('Inbox retrieved.', paginated_data(paginator, page_obj, WorkflowTaskSerializer(page_obj, many=True).data))


class MyApprovalsCountsView(APIView):
    """Task D.3 — badge counts, one query."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils import timezone
        base = WorkflowTask.objects.filter(assignee=request.user, status=WorkflowTask.STATUS_PENDING)
        return success('Counts computed.', {
            'pending': base.count(),
            'overdue': base.filter(due_at__lt=timezone.now()).count(),
        })


class WorkflowInstanceDetailView(APIView):
    """Task D.2 — timeline for a record, visible to requester/assignees/
    users with view permission on the record."""
    permission_classes = [IsAuthenticated]

    def get(self, request, content_type, object_id):
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.filter(model=content_type).first()
        if ct is None:
            return error('Unknown content type.', http_status=404)
        instance = WorkflowInstance.objects.filter(content_type=ct, object_id=object_id).order_by('-started_at').first()
        if instance is None:
            return error('No workflow instance for this record.', http_status=404)

        is_requester = instance.requester_id == request.user.pk
        is_assignee = WorkflowTask.objects.filter(instance=instance, assignee=request.user).exists()
        if not (is_requester or is_assignee or _is_admin(request.user)):
            return error('You do not have permission to view this.', http_status=403)
        return success('Instance retrieved.', WorkflowInstanceSerializer(instance).data)


class WorkflowTaskActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, task_id):
        action = request.data.get('action')
        remarks = request.data.get('remarks', '')
        idempotency_key = request.data.get('idempotency_key')
        try:
            task = wf.act(task_id, user=request.user, action=action, remarks=remarks, idempotency_key=idempotency_key)
        except wf.WorkflowError as exc:
            return error(exc.message, http_status=400)
        return success('Action applied.', WorkflowTaskSerializer(task).data)


class WorkflowTaskBulkActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        task_ids = request.data.get('task_ids', [])
        action = request.data.get('action')
        remarks = request.data.get('remarks', '')
        result = wf.bulk_act(task_ids, user=request.user, action=action, remarks=remarks)
        return success('Bulk action complete.', result)


class WorkflowInstanceWithdrawView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, instance_id):
        try:
            instance = wf.withdraw(instance_id, user=request.user)
        except wf.WorkflowError as exc:
            return error(exc.message, http_status=400)
        return success('Withdrawn.', WorkflowInstanceSerializer(instance).data)


class WorkflowTaskReassignView(APIView):
    permission_classes = [HasSettingsPermission]

    def post(self, request, task_id):
        from apps.accounts.models import User
        new_user = User.objects.filter(pk=request.data.get('user_id')).first()
        if new_user is None:
            return error('Unknown user.', http_status=400)
        try:
            task = wf.reassign(task_id, new_user=new_user, actor=request.user)
        except wf.WorkflowError as exc:
            return error(exc.message, http_status=400)
        return success('Reassigned.', WorkflowTaskSerializer(task).data)

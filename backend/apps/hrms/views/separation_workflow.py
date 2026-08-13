import logging

from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.responses import error, first_error, success

from ..models import (
    APPROVAL_APPROVED, APPROVAL_PENDING, APPROVAL_REJECTED,
    SEP_APPROVED, SEP_CLEARANCE_MANAGER, SEP_REJECTED, SEP_STAGE2_PENDING,
    SEP_STAGE_BRANCH_ADMIN, SEP_STAGE_HR, SEP_STAGE_MANAGER,
    SeparationApprovalStage, SeparationClearance, SeparationDocument,
    SeparationHandoverTask, SeparationRequest,
)
from ..serializers import (
    SeparationActivitySerializer, SeparationClearanceSerializer, SeparationDocumentCreateSerializer,
    SeparationDocumentSerializer, SeparationHandoverTaskCreateSerializer,
    SeparationHandoverTaskSerializer, SeparationRequestSerializer,
)
from .separation import _has_perm, _log, _user_branch

logger = logging.getLogger(__name__)


def _get_visible_request(request_id: str, user):
    try:
        sep_request = SeparationRequest.objects.select_related('employee').get(id=request_id)
    except SeparationRequest.DoesNotExist:
        return None, error('Separation request not found.', http_status=status.HTTP_404_NOT_FOUND)
    is_own  = sep_request.employee_id == user.id
    can_see = is_own or _has_perm(user, 'separation.approve') or _has_perm(user, 'employees.view')
    if not can_see:
        return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
    return sep_request, None


def _can_action_stage(user, sep_request, stage) -> bool:
    if sep_request.employee_id == user.id:
        return False
    if _has_perm(user, 'settings.edit'):
        return True
    if stage.stage == SEP_STAGE_MANAGER:
        return stage.approver_id == user.id
    if stage.stage == SEP_STAGE_BRANCH_ADMIN:
        return bool(
            user.role and user.role.can_manage_branch
            and _user_branch(user) == _user_branch(sep_request.employee)
        )
    if stage.stage == SEP_STAGE_HR:
        if stage.approver_id:
            return stage.approver_id == user.id
        branch = _user_branch(user)
        return _has_perm(user, 'separation.approve') and (not branch or branch == _user_branch(sep_request.employee))
    return False


# ─── Approval stages ────────────────────────────────────────────────────────────

class SeparationApprovalStageActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id: str, stage_id: str):
        try:
            stage = SeparationApprovalStage.objects.select_related('request', 'request__employee').get(
                id=stage_id, request_id=request_id,
            )
        except SeparationApprovalStage.DoesNotExist:
            return error('Approval stage not found.', http_status=status.HTTP_404_NOT_FOUND)

        sep_request = stage.request
        if stage.status != APPROVAL_PENDING:
            return error(f'This stage has already been {stage.status}.')
        earlier_pending = SeparationApprovalStage.objects.filter(
            request=sep_request, sequence__lt=stage.sequence, status=APPROVAL_PENDING,
        ).exists()
        if earlier_pending:
            return error('An earlier approval stage is still pending.')
        if not _can_action_stage(request.user, sep_request, stage):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        action = request.data.get('action')
        if action not in ('approve', 'reject'):
            return error('Action must be "approve" or "reject".')

        remarks = (request.data.get('remarks') or '').strip()
        stage.status      = APPROVAL_APPROVED if action == 'approve' else APPROVAL_REJECTED
        stage.approver     = request.user  # records who actually acted, even for an unresolved/fallback stage
        stage.remarks      = remarks
        stage.actioned_at  = timezone.now()
        stage.save()

        if action == 'reject':
            sep_request.status = SEP_REJECTED
        else:
            still_pending = sep_request.approval_stages.filter(status=APPROVAL_PENDING).exists()
            sep_request.status = SEP_STAGE2_PENDING if still_pending else SEP_APPROVED
        sep_request.save(update_fields=['status', 'updated_at'])

        suffix = f' — "{remarks}"' if remarks else ''
        _log(sep_request, request.user, f'{stage.get_stage_display()} {action}d by {request.user.full_name}.{suffix}')
        logger.info('Separation stage %s %sd on request %s by %s', stage.id, action, sep_request.id, request.user.email)
        return success(
            f'{stage.get_stage_display()} {action}d.',
            SeparationRequestSerializer(sep_request, context={'request': request}).data,
        )


# ─── KT / Handover tasks ────────────────────────────────────────────────────────

class SeparationHandoverTaskListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id: str):
        sep_request, err = _get_visible_request(request_id, request.user)
        if err:
            return err
        tasks = sep_request.handover_tasks.select_related('assigned_to', 'created_by').all()
        return success('Handover tasks retrieved.', SeparationHandoverTaskSerializer(tasks, many=True).data)

    def post(self, request, request_id: str):
        sep_request, err = _get_visible_request(request_id, request.user)
        if err:
            return err
        is_own      = sep_request.employee_id == request.user.id
        has_approve = _has_perm(request.user, 'separation.approve')
        # Self-service add is only for a plain employee documenting their own
        # handover — an HR/Manager/Branch Admin approver loses that allowance
        # on their OWN request, so they can't both raise and manage their exit.
        if not (is_own != has_approve):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        serializer = SeparationHandoverTaskCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        task = SeparationHandoverTask.objects.create(
            request=sep_request, created_by=request.user, **serializer.validated_data,
        )
        _log(sep_request, request.user, f'Handover task "{task.task}" added by {request.user.full_name}.')
        return success('Handover task added.', SeparationHandoverTaskSerializer(task).data, http_status=status.HTTP_201_CREATED)


class SeparationHandoverTaskDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_task(self, request_id: str, task_id: str, user):
        try:
            task = SeparationHandoverTask.objects.select_related('request', 'request__employee', 'assigned_to').get(
                id=task_id, request_id=request_id,
            )
        except SeparationHandoverTask.DoesNotExist:
            return None, error('Handover task not found.', http_status=status.HTTP_404_NOT_FOUND)
        is_own  = task.request.employee_id == user.id
        can_see = is_own or _has_perm(user, 'separation.approve') or _has_perm(user, 'employees.view')
        if not can_see:
            return None, error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        return task, None

    def patch(self, request, request_id: str, task_id: str):
        task, err = self._get_task(request_id, task_id, request.user)
        if err:
            return err
        user       = request.user
        can_manage = _has_perm(user, 'separation.approve') or task.request.employee_id == user.id

        if 'is_completed' in request.data:
            if not (can_manage or task.assigned_to_id == user.id):
                return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
            completed = bool(request.data.get('is_completed'))
            task.is_completed = completed
            task.completed_at = timezone.now() if completed else None
            task.save(update_fields=['is_completed', 'completed_at', 'updated_at'])
        else:
            if not can_manage:
                return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
            serializer = SeparationHandoverTaskCreateSerializer(task, data=request.data, partial=True)
            if not serializer.is_valid():
                return error(first_error(serializer.errors))
            serializer.save()

        _log(task.request, user, f'Handover task "{task.task}" updated by {user.full_name}.')
        return success('Handover task updated.', SeparationHandoverTaskSerializer(task).data)

    def delete(self, request, request_id: str, task_id: str):
        task, err = self._get_task(request_id, task_id, request.user)
        if err:
            return err
        user = request.user
        if not (_has_perm(user, 'separation.approve') or task.created_by_id == user.id):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        _log(task.request, user, f'Handover task "{task.task}" removed by {user.full_name}.')
        task.delete()
        return success('Handover task deleted.')


# ─── Clearances ─────────────────────────────────────────────────────────────────

class SeparationClearanceListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id: str):
        sep_request, err = _get_visible_request(request_id, request.user)
        if err:
            return err
        clearances = sep_request.clearances.select_related('cleared_by').all()
        return success('Clearances retrieved.', SeparationClearanceSerializer(clearances, many=True, context={'request': request}).data)


class SeparationClearanceActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, request_id: str, clearance_id: str):
        try:
            clearance = SeparationClearance.objects.select_related('request', 'request__employee').get(
                id=clearance_id, request_id=request_id,
            )
        except SeparationClearance.DoesNotExist:
            return error('Clearance record not found.', http_status=status.HTTP_404_NOT_FOUND)

        sep_request = clearance.request
        user        = request.user
        if sep_request.employee_id == user.id:
            return error('You cannot clear your own separation.', http_status=status.HTTP_403_FORBIDDEN)
        if clearance.status != APPROVAL_PENDING:
            return error(f'This clearance has already been {clearance.status}.')

        can_action = _has_perm(user, 'separation.approve')
        if not can_action and clearance.clearance_type == SEP_CLEARANCE_MANAGER:
            from apps.accounts.models import Department
            dept = Department.objects.filter(name=sep_request.employee.department).first()
            can_action = bool(dept and dept.manager_id == user.id)
        if not can_action:
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        action = request.data.get('action')
        if action not in ('approve', 'reject'):
            return error('Action must be "approve" or "reject".')

        clearance.status      = APPROVAL_APPROVED if action == 'approve' else APPROVAL_REJECTED
        clearance.cleared_by   = user
        clearance.remarks      = (request.data.get('remarks') or '').strip()
        clearance.actioned_at  = timezone.now()
        clearance.save()

        _log(sep_request, user, f'{clearance.get_clearance_type_display()} {action}d by {user.full_name}.')
        return success(
            f'{clearance.get_clearance_type_display()} {action}d.',
            SeparationClearanceSerializer(clearance, context={'request': request}).data,
        )


# ─── Documents ──────────────────────────────────────────────────────────────────

class SeparationDocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, request_id: str):
        sep_request, err = _get_visible_request(request_id, request.user)
        if err:
            return err
        docs = sep_request.documents.select_related('uploaded_by').all()
        return success('Documents retrieved.', SeparationDocumentSerializer(docs, many=True, context={'request': request}).data)

    def post(self, request, request_id: str):
        sep_request, err = _get_visible_request(request_id, request.user)
        if err:
            return err
        is_own = sep_request.employee_id == request.user.id
        if not (is_own or _has_perm(request.user, 'separation.approve')):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)

        serializer = SeparationDocumentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors))
        doc = SeparationDocument.objects.create(
            request=sep_request, uploaded_by=request.user, **serializer.validated_data,
        )
        _log(sep_request, request.user, f'{doc.get_document_type_display()} uploaded by {request.user.full_name}.')
        return success(
            'Document uploaded.',
            SeparationDocumentSerializer(doc, context={'request': request}).data,
            http_status=status.HTTP_201_CREATED,
        )


class SeparationDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, request_id: str, document_id: str):
        try:
            doc = SeparationDocument.objects.select_related('request').get(id=document_id, request_id=request_id)
        except SeparationDocument.DoesNotExist:
            return error('Document not found.', http_status=status.HTTP_404_NOT_FOUND)
        user = request.user
        if not (_has_perm(user, 'separation.approve') or doc.uploaded_by_id == user.id):
            return error('Permission denied.', http_status=status.HTTP_403_FORBIDDEN)
        _log(doc.request, user, f'{doc.get_document_type_display()} removed by {user.full_name}.')
        doc.delete()
        return success('Document deleted.')


# ─── Activity log ───────────────────────────────────────────────────────────────

class SeparationActivityListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, request_id: str):
        sep_request, err = _get_visible_request(request_id, request.user)
        if err:
            return err
        activities = sep_request.activities.select_related('actor', 'actor__role').all()
        return success('Activity retrieved.', SeparationActivitySerializer(activities, many=True).data)

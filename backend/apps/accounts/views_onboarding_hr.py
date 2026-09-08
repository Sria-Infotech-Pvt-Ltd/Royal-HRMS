"""
HR/Admin-facing onboarding wizard — lets HR/Admin fill in and submit an
employee's onboarding profile on their behalf (walk-in hires, or anyone who
can't complete it themselves), gated on the new `onboarding.edit` permission.

Deliberately its own file, not views.py (already far past the 300-line
convention, 6800+ lines) — mirrors the split pattern used for
apps/attendance/views/face_registration_hr.py, which solves the exact same
"HR acts on someone else's self-service flow" problem.

Keyed by the User's UUID pk (`user_id`), not the human-readable `employee_id`
code that EmployeeDetailView/EmployeeProfileDocumentView use — a recruited
candidate converted to a portal user has no employee_id until
OnboardingApprovalView generates one at approval time, so this must resolve
the same way OnboardingApprovalView itself already does (by user_id) to work
for that population pre-approval too.

Delegates all validation/save logic to the same module-level helpers the
self-service OnboardingView already uses (_save_profile_step,
_submit_onboarding, _extract_step_data, _compute_completed_steps,
_missing_required_docs, _step_all_field_keys/_step_custom_field_keys/
_step_file_field_keys) — this file only resolves the target employee,
checks permission/branch scope, and writes one audit row per write action.
Document/custom-file-field detail (stream) and delete already work for HR
today via the existing self-service routes' own `employees.edit` fallback
(see EmployeeDocumentView._get_doc / CustomFieldFileValueView._get_value) —
not duplicated here.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.permissions import has_perm
from core.responses import error, first_error, get_client_ip, success

from apps.accounts.models import AuditLog, EmployeeProfile, User
from apps.accounts.views import (
    _VALID_STEPS,
    _employee_out_of_branch_scope,
    _extract_step_data,
    _compute_completed_steps,
    _missing_required_docs,
    _save_profile_step,
    _step_all_field_keys,
    _step_custom_field_keys,
    _step_file_field_keys,
    _submit_onboarding,
)

logger = logging.getLogger(__name__)

_DENIED = 'You do not have permission to complete onboarding for this employee.'


def _resolve_onboarding_target(request, user_id: str):
    """Returns (target_user, None) on success, or (None, error_response)."""
    if not has_perm(request.user, 'onboarding.edit'):
        return None, error(_DENIED, http_status=status.HTTP_403_FORBIDDEN)
    try:
        target = User.objects.select_related('role').get(pk=user_id)
    except (User.DoesNotExist, ValueError):
        return None, error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
    if _employee_out_of_branch_scope(request.user, target):
        return None, error('Employee not found.', http_status=status.HTTP_404_NOT_FOUND)
    return target, None


def _audit_hr_onboarding(request, target, action: str, changes: dict) -> None:
    try:
        AuditLog.objects.create(
            user=request.user, action=action, module='accounts',
            object_id=str(target.pk), changes={'employee': target.email, **changes},
            branch=target.branch, ip_address=get_client_ip(request),
        )
    except Exception:
        logger.warning('AuditLog write failed for %s target=%s', action, target.pk)


class HREmployeeOnboardingView(APIView):
    """
    GET    /onboarding/employees/<user_id>/            → full profile summary
    GET    /onboarding/employees/<user_id>/step/<n>/    → fields for this step only
    PATCH  /onboarding/employees/<user_id>/step/<n>/    → save step data
    DELETE /onboarding/employees/<user_id>/step/<n>/    → clear all fields for this step
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [JSONParser, FormParser, MultiPartParser]

    def get(self, request: Request, user_id: str, step: int = None) -> Response:
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err

        from apps.accounts.serializers import EmployeeProfileSerializer

        if step is None:
            profile, _ = EmployeeProfile.objects.get_or_create(user=target)
            data = EmployeeProfileSerializer(profile).data
            data['completed_steps'] = _compute_completed_steps(profile, target)
            return success('Profile retrieved.', data=data)

        if step not in _VALID_STEPS:
            return error(f'Invalid step {step}. Valid steps are 0 to 4.', http_status=status.HTTP_400_BAD_REQUEST)

        if step == 4:
            from apps.accounts.models import EmployeeDocument as ED
            from apps.accounts.serializers import EmployeeDocumentSerializer
            docs = ED.objects.filter(user=target)
            return success(
                'Step 4 documents retrieved.',
                data=EmployeeDocumentSerializer(docs, many=True, context={'request': request}).data,
            )

        profile, _ = EmployeeProfile.objects.get_or_create(user=target)
        all_data = EmployeeProfileSerializer(profile).data
        return success(f'Step {step} data retrieved.', data=_extract_step_data(profile, all_data, step))

    def patch(self, request: Request, user_id: str, step: int = None) -> Response:
        if step is None:
            return error('Specify a step: PATCH /onboarding/employees/<user_id>/step/<n>/',
                         http_status=status.HTTP_405_METHOD_NOT_ALLOWED)
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        if step not in _VALID_STEPS:
            return error(f'Invalid step {step}. Valid steps are 0 to 4.', http_status=status.HTTP_400_BAD_REQUEST)

        result = _save_profile_step(request, step, target_user=target)
        if result.status_code < 300:
            _audit_hr_onboarding(request, target, 'onboarding_step_saved_by_hr', {'step': step})
        return result

    def delete(self, request: Request, user_id: str, step: int = None) -> Response:
        if step is None:
            return error('Specify a step to clear, e.g. DELETE .../step/0/.',
                         http_status=status.HTTP_405_METHOD_NOT_ALLOWED)
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        if step not in _VALID_STEPS:
            return error(f'Invalid step {step}. Valid steps are 0 to 4.', http_status=status.HTTP_400_BAD_REQUEST)

        ob_status = target.onboarding_status
        if ob_status == User.ONBOARDING_COMPLETE:
            return error('Onboarding is already complete and cannot be modified.', http_status=status.HTTP_403_FORBIDDEN)
        if ob_status == User.ONBOARDING_SUBMITTED:
            return error(
                'Onboarding has been submitted and is awaiting approval. Reject it first if changes are needed.',
                http_status=status.HTTP_403_FORBIDDEN,
            )

        if step == 4:
            return success(
                'Step 4 documents are managed individually — '
                'use DELETE /api/onboarding/documents/<id>/ to remove a specific document.',
                data={},
            )

        step_fields = _step_all_field_keys(step)
        if not step_fields:
            return success(f'Step {step} has no profile fields to clear.', data={})
        custom_keys  = _step_custom_field_keys(step)
        file_keys    = _step_file_field_keys(step)
        builtin_keys = step_fields - custom_keys - file_keys

        profile, _ = EmployeeProfile.objects.get_or_create(user=target)
        try:
            if builtin_keys:
                EmployeeProfile.objects.filter(pk=profile.pk).update(**{field: None for field in builtin_keys})
            if custom_keys:
                remaining = {k: v for k, v in (profile.custom_field_values or {}).items() if k not in custom_keys}
                EmployeeProfile.objects.filter(pk=profile.pk).update(custom_field_values=remaining)
            if file_keys:
                from apps.accounts.models import CustomFieldFileValue
                CustomFieldFileValue.objects.filter(user=target, field_key__in=file_keys).delete()
        except Exception as exc:
            logger.error('HR onboarding step clear failed target=%s step=%d: %s', target.pk, step, exc, exc_info=True)
            return error('Failed to clear step data. Please try again.', http_status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        _audit_hr_onboarding(request, target, 'onboarding_step_cleared_by_hr', {'step': step})
        logger.info('Onboarding step %d cleared for %s by %s', step, target.email, request.user.email)
        return success(f'Step {step} data cleared successfully.')


class HREmployeeOnboardingSubmitView(APIView):
    """POST /onboarding/employees/<user_id>/submit/ — submit on the employee's behalf."""
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, user_id: str) -> Response:
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        result = _submit_onboarding(target)
        if result.status_code < 300:
            _audit_hr_onboarding(request, target, 'onboarding_submitted_by_hr', {})
        return result


class HREmployeeOnboardingDocumentView(APIView):
    """
    GET  /onboarding/employees/<user_id>/documents/ → list this employee's documents
    POST /onboarding/employees/<user_id>/documents/ → upload a document on their behalf

    Viewing/streaming a specific document or deleting one already works for
    any `employees.edit` holder via the existing self-service routes
    (/onboarding/documents/<doc_id>/) — every onboarding.edit holder in this
    codebase already holds employees.edit too, so no separate by-id route is
    duplicated here (same reasoning EmployeeDocumentView/CustomFieldFileValueView
    already document for the equivalent HR-on-active-employee case).
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def get(self, request: Request, user_id: str) -> Response:
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        from apps.accounts.models import EmployeeDocument as ED
        from apps.accounts.serializers import EmployeeDocumentSerializer
        docs = ED.objects.filter(user=target)
        return success('Documents retrieved.', data=EmployeeDocumentSerializer(docs, many=True, context={'request': request}).data)

    def post(self, request: Request, user_id: str) -> Response:
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        if target.onboarding_status == User.ONBOARDING_COMPLETE:
            return error('Onboarding is already complete.')

        from apps.accounts.models import EmployeeDocument as ED
        from apps.accounts.serializers import EmployeeDocumentSerializer
        from apps.accounts.views import _get_document_type_config
        from django.db import transaction

        serializer = EmployeeDocumentSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        file_obj    = serializer.validated_data['file']
        doc_type    = serializer.validated_data['document_type']
        type_config = _get_document_type_config(doc_type)
        if not type_config:
            return error('Invalid document type.', http_status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            doc = serializer.save(user=target, file_name=file_obj.name[:255], file_size=file_obj.size)
            if not type_config.allow_multiple:
                ED.objects.filter(user=target, document_type=doc_type).exclude(pk=doc.pk).delete()

        _audit_hr_onboarding(request, target, 'onboarding_document_uploaded_by_hr', {'document_type': doc_type})
        logger.info('Document %s uploaded for %s by %s (HR onboarding)', doc_type, target.email, request.user.email)
        return success(
            'Document uploaded.',
            data=EmployeeDocumentSerializer(doc, context={'request': request}).data,
            http_status=status.HTTP_201_CREATED,
        )


class HREmployeeCustomFieldFileValueView(APIView):
    """
    GET  /onboarding/employees/<user_id>/custom-file-fields/ → list this employee's file-type custom values
    POST /onboarding/employees/<user_id>/custom-file-fields/ → upload/replace a value for {field_key, file}

    user_id-keyed sibling of EmployeeCustomFieldFileValueView (which is
    employee_id-keyed and therefore can't resolve a pre-approval candidate —
    same asymmetry as the document view above).
    """
    permission_classes = [IsAuthenticated]
    parser_classes     = [MultiPartParser, FormParser]

    def get(self, request: Request, user_id: str) -> Response:
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err
        from apps.accounts.models import CustomFieldFileValue
        from apps.accounts.serializers import CustomFieldFileValueSerializer
        values = CustomFieldFileValue.objects.filter(user=target)
        return success(
            'Custom field files retrieved.',
            data=CustomFieldFileValueSerializer(values, many=True, context={'request': request}).data,
        )

    def post(self, request: Request, user_id: str) -> Response:
        target, err = _resolve_onboarding_target(request, user_id)
        if err:
            return err

        from apps.accounts.models import CustomFieldFileValue
        from apps.accounts.serializers import CustomFieldFileValueSerializer
        from apps.accounts.views import _get_file_field_config
        from django.db import transaction

        field_key = (request.data.get('field_key') or '').strip()
        config = _get_file_field_config(field_key)
        if not config:
            return error('Invalid field_key — not a file-type custom field.', http_status=status.HTTP_400_BAD_REQUEST)

        serializer = CustomFieldFileValueSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        file_obj = serializer.validated_data['file']
        with transaction.atomic():
            value = serializer.save(
                user=target, field_key=field_key,
                file_name=file_obj.name[:255], file_size=file_obj.size,
            )
            if not config.allow_multiple:
                CustomFieldFileValue.objects.filter(user=target, field_key=field_key).exclude(pk=value.pk).delete()

        _audit_hr_onboarding(request, target, 'onboarding_custom_file_uploaded_by_hr', {'field_key': field_key})
        return success(
            'File uploaded.',
            data=CustomFieldFileValueSerializer(value, context={'request': request}).data,
            http_status=status.HTTP_201_CREATED,
        )

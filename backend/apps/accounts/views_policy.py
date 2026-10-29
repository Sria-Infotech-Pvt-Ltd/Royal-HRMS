"""
Company Policy acknowledgement and the Company Contact Matrix.

Acknowledgement
  POST /api/documents/<pk>/acknowledge/          the signed-in employee accepts the
                                                 current version (body: {"version": n})
  GET  /api/documents/<pk>/acknowledgements/     HR: who has / hasn't acknowledged
  GET  /api/documents/pending-acknowledgements/  the signed-in employee's outstanding ones

Contact Matrix
  GET    /api/company-contacts/        every signed-in user (company-wide + own branch)
  POST   /api/company-contacts/        documents.create
  PATCH  /api/company-contacts/<pk>/   documents.edit
  DELETE /api/company-contacts/<pk>/   documents.delete (soft delete)
"""
from __future__ import annotations

import logging

from django.db import IntegrityError
from django.db.models import Q
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import AuditLog, CompanyContact, Document, DocumentAcknowledgement, User
from core.permissions import has_perm as _has_perm
from core.responses import error, first_error, get_client_ip, success

logger = logging.getLogger(__name__)


def _unrestricted(user) -> bool:
    return _has_perm(user, 'settings.edit')


def _visible_to(document: Document, user) -> bool:
    """A branch-specific document is for that branch's employees only."""
    if document.branch_id is None or _unrestricted(user):
        return True
    return bool(user.branch) and document.branch.branch_name == user.branch


def _audit(request, action: str, object_id, changes: dict, branch: str = '') -> None:
    try:
        AuditLog.objects.create(
            user=request.user, action=action, module='documents', object_id=str(object_id),
            changes=changes, branch=branch, ip_address=get_client_ip(request),
        )
    except Exception:
        logger.warning('AuditLog write failed for %s id=%s', action, object_id)


# ─── Acknowledgement ──────────────────────────────────────────────────────────

def _ack_document(pk):
    try:
        return Document.objects.select_related('branch').get(pk=pk, is_active=True, requires_acknowledgement=True)
    except (Document.DoesNotExist, ValueError):
        return None


class DocumentAcknowledgeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not _has_perm(request.user, 'documents.view'):
            return error('You do not have permission to view documents.', http_status=status.HTTP_403_FORBIDDEN)
        doc = _ack_document(pk)
        if doc is None or not _visible_to(doc, request.user):
            return error('Document not found or does not need acknowledgement.', http_status=status.HTTP_404_NOT_FOUND)
        try:
            version = int(request.data.get('version'))
        except (TypeError, ValueError):
            return error('version is required.')
        if version != doc.version:
            # The page showed an older file — the employee must read the current one first.
            return error('This document has been updated. Please reopen it and read the latest version.',
                         http_status=status.HTTP_409_CONFLICT)
        try:
            ack, created = DocumentAcknowledgement.objects.get_or_create(
                document=doc, employee=request.user, version=doc.version,
                defaults={'ip_address': get_client_ip(request)},
            )
        except IntegrityError:
            ack, created = DocumentAcknowledgement.objects.get(document=doc, employee=request.user, version=doc.version), False
        if created:
            _audit(request, 'document_acknowledged', doc.id, {'title': doc.title, 'version': doc.version},
                   doc.branch.branch_name if doc.branch else '')
        return success(
            'Acknowledged.' if created else 'Already acknowledged.',
            data={'document': doc.id, 'version': ack.version, 'acknowledged_at': ack.acknowledged_at},
            http_status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class MyPendingAcknowledgementsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _has_perm(request.user, 'documents.view'):
            return success('No documents.', data=[])
        docs = Document.objects.filter(is_active=True, requires_acknowledgement=True).select_related('branch')
        if not _unrestricted(request.user):
            docs = docs.filter(Q(branch__isnull=True) | Q(branch__branch_name=request.user.branch or ''))
        done = set(
            DocumentAcknowledgement.objects.filter(employee=request.user, document__in=docs)
            .values_list('document_id', 'version')
        )
        pending = [
            {'id': d.id, 'title': d.title, 'category': d.category, 'version': d.version}
            for d in docs.order_by('-uploaded_at') if (d.id, d.version) not in done
        ]
        return success('Pending acknowledgements.', data=pending)


class DocumentAcknowledgementListView(APIView):
    """HR view: every active employee in the requester's scope and whether they
    acknowledged the current version. Same scope as the employee list:
    settings.edit = everyone, Managers = direct reports, others = own branch."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        if not _has_perm(request.user, 'documents.edit'):
            return error('You do not have permission to view acknowledgements.', http_status=status.HTTP_403_FORBIDDEN)
        doc = _ack_document(pk)
        if doc is None:
            return error('Document not found or does not need acknowledgement.', http_status=status.HTTP_404_NOT_FOUND)

        employees = User.objects.filter(is_active=True).exclude(employee_id__isnull=True).exclude(employee_id='')
        if doc.branch_id:
            employees = employees.filter(branch=doc.branch.branch_name)
        role = request.user.role
        if role and role.can_manage_team:
            employees = employees.filter(reporting_manager=request.user)
        elif not _unrestricted(request.user) and request.user.branch:
            employees = employees.filter(branch=request.user.branch)

        acks = dict(
            DocumentAcknowledgement.objects.filter(document=doc, version=doc.version, employee__in=employees)
            .values_list('employee_id', 'acknowledged_at')
        )
        rows = [
            {'employee_id': e.employee_id, 'name': e.full_name, 'branch': e.branch, 'department': e.department,
             'acknowledged_at': acks.get(e.pk)}
            for e in employees.order_by('full_name').only('id', 'employee_id', 'full_name', 'branch', 'department')
        ]
        return success('Acknowledgements.', data={
            'document': {'id': doc.id, 'title': doc.title, 'version': doc.version},
            'total': len(rows),
            'acknowledged': sum(1 for r in rows if r['acknowledged_at']),
            'employees': rows,
        })


# ─── Contact Matrix ───────────────────────────────────────────────────────────

class CompanyContactSerializer(serializers.ModelSerializer):
    branch_name = serializers.SerializerMethodField()

    class Meta:
        model = CompanyContact
        fields = ('id', 'name', 'designation', 'department', 'email', 'phone', 'purpose',
                  'escalation_level', 'branch', 'branch_name', 'display_order')

    def get_branch_name(self, obj) -> str:
        return obj.branch.branch_name if obj.branch else ''

    def validate_name(self, value: str) -> str:
        if not value.strip():
            raise serializers.ValidationError('Name is required.')
        return value.strip()

    def validate(self, attrs):
        if not (attrs.get('email') or attrs.get('phone')) and not (self.instance and (self.instance.email or self.instance.phone)):
            raise serializers.ValidationError('Enter an email or a phone number.')
        return attrs


def _branch_allowed(user, branch) -> bool:
    """Branch-scoped HR may only manage their own branch's contacts."""
    if _unrestricted(user):
        return True
    return branch is not None and branch.branch_name == user.branch


class CompanyContactListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = CompanyContact.objects.filter(is_active=True).select_related('branch')
        if not _unrestricted(request.user):
            qs = qs.filter(Q(branch__isnull=True) | Q(branch__branch_name=request.user.branch or ''))
        return success('Contact matrix.', data={
            'contacts': CompanyContactSerializer(qs, many=True).data,
            'can_manage': _has_perm(request.user, 'documents.create'),
        })

    def post(self, request):
        if not _has_perm(request.user, 'documents.create'):
            return error('You do not have permission to manage contacts.', http_status=status.HTTP_403_FORBIDDEN)
        ser = CompanyContactSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors)
        if not _branch_allowed(request.user, ser.validated_data.get('branch')):
            return error('You can only add contacts for your own branch.', http_status=status.HTTP_403_FORBIDDEN)
        contact = ser.save(created_by=request.user, updated_by=request.user)
        _audit(request, 'contact_created', contact.id, {'name': contact.name})
        return success('Contact added.', data=CompanyContactSerializer(contact).data, http_status=status.HTTP_201_CREATED)


class CompanyContactDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, request, pk):
        try:
            contact = CompanyContact.objects.select_related('branch').get(pk=pk, is_active=True)
        except (CompanyContact.DoesNotExist, ValueError):
            return None
        return contact if _branch_allowed(request.user, contact.branch) else None

    def patch(self, request, pk):
        if not _has_perm(request.user, 'documents.edit'):
            return error('You do not have permission to manage contacts.', http_status=status.HTTP_403_FORBIDDEN)
        contact = self._get(request, pk)
        if contact is None:
            return error('Contact not found.', http_status=status.HTTP_404_NOT_FOUND)
        ser = CompanyContactSerializer(contact, data=request.data, partial=True)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors)
        if 'branch' in ser.validated_data and not _branch_allowed(request.user, ser.validated_data['branch']):
            return error('You can only manage contacts for your own branch.', http_status=status.HTTP_403_FORBIDDEN)
        contact = ser.save(updated_by=request.user)
        _audit(request, 'contact_updated', contact.id, {k: v for k, v in request.data.items() if k != 'branch'})
        return success('Contact updated.', data=CompanyContactSerializer(contact).data)

    def delete(self, request, pk):
        if not _has_perm(request.user, 'documents.delete'):
            return error('You do not have permission to manage contacts.', http_status=status.HTTP_403_FORBIDDEN)
        contact = self._get(request, pk)
        if contact is None:
            return error('Contact not found.', http_status=status.HTTP_404_NOT_FOUND)
        contact.is_active = False
        contact.updated_by = request.user
        contact.save(update_fields=['is_active', 'updated_by', 'updated_at'])
        _audit(request, 'contact_deleted', contact.id, {'name': contact.name})
        return success('Contact removed.')

"""
GET/PUT /api/approvals/escalation-settings/     company escalation settings (edit: settings.edit)
GET     /api/approvals/escalations/             recent reminders / escalations (settings.edit)
GET     /api/approvals/delegations/             my delegations (given / received); ?all=1 for admins
POST    /api/approvals/delegations/             create (own approvals; admins for anyone)
POST    /api/approvals/delegations/<id>/revoke/ revoke
GET     /api/approvals/delegations/eligible/    who can receive my approvals (?workflow=leave|attendance)
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.permissions import has_perm
from core.responses import error, first_error, get_client_ip, success

from apps.approvals import services
from apps.approvals.models import ApprovalDelegation, ApprovalEscalation, ApprovalEscalationSettings

User = get_user_model()


def _person(u):
    return {'id': str(u.pk), 'name': u.full_name or '', 'employee_id': u.employee_id or '', 'branch': u.branch or ''} \
        if u else None


class _SettingsSerializer(serializers.Serializer):
    is_enabled = serializers.BooleanField()
    reminder_after_days = serializers.IntegerField(min_value=0, max_value=30)
    first_escalation_after_days = serializers.IntegerField(min_value=1, max_value=30)
    second_escalation_after_days = serializers.IntegerField(min_value=0, max_value=30)
    escalation_head = serializers.UUIDField(required=False, allow_null=True)
    applies_to_leave = serializers.BooleanField()
    applies_to_attendance = serializers.BooleanField()

    def validate(self, data):
        if data['reminder_after_days'] and data['reminder_after_days'] >= data['first_escalation_after_days']:
            raise serializers.ValidationError(
                {'reminder_after_days': 'The reminder must come before the first escalation.'})
        return data


def _settings_out(cfg, user):
    return {
        'is_enabled': cfg.is_enabled, 'reminder_after_days': cfg.reminder_after_days,
        'first_escalation_after_days': cfg.first_escalation_after_days,
        'second_escalation_after_days': cfg.second_escalation_after_days,
        'escalation_head': _person(cfg.escalation_head) if cfg.escalation_head_id else None,
        'applies_to_leave': cfg.applies_to_leave, 'applies_to_attendance': cfg.applies_to_attendance,
        'can_edit': has_perm(user, 'settings.edit'),
    }


class EscalationSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_perm(request.user, 'settings.view') and not has_perm(request.user, 'settings.edit'):
            return error('Permission denied.', http_status=403)
        return success('Escalation settings.', _settings_out(ApprovalEscalationSettings.current(), request.user))

    def put(self, request):
        if not has_perm(request.user, 'settings.edit'):
            return error('Permission denied.', http_status=403)
        ser = _SettingsSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors)
        d = ser.validated_data
        head = None
        if d.get('escalation_head'):
            head = User.objects.filter(pk=d['escalation_head'], is_active=True).first()
            if head is None:
                return error('Escalation head not found.', data={'escalation_head': ['Choose an active employee.']})
        cfg = ApprovalEscalationSettings.objects.first() or ApprovalEscalationSettings()
        for f in ('is_enabled', 'reminder_after_days', 'first_escalation_after_days', 'second_escalation_after_days',
                  'applies_to_leave', 'applies_to_attendance'):
            setattr(cfg, f, d[f])
        cfg.escalation_head, cfg.updated_by = head, request.user
        cfg.save()
        from apps.accounts.models import AuditLog
        AuditLog.objects.create(user=request.user, action='approval_escalation_settings_updated', module='approvals',
                                object_id=str(cfg.pk), changes={k: (str(v) if k == 'escalation_head' else v)
                                                                for k, v in d.items()},
                                ip_address=get_client_ip(request))
        return success('Escalation settings saved.', _settings_out(cfg, request.user))


class EscalationLogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_perm(request.user, 'settings.edit'):
            return error('Permission denied.', http_status=403)
        rows = ApprovalEscalation.objects.select_related('target')[:100]
        return success('Recent escalations.', [{
            'kind': r.kind, 'request_id': str(r.request_id), 'stage': r.stage, 'level': r.level,
            'action': r.action, 'action_label': r.get_action_display(), 'target': _person(r.target),
            'working_days_waited': r.working_days_waited, 'note': r.note, 'created_at': r.created_at.isoformat(),
        } for r in rows])


def _delegation_out(d, user, today):
    return {
        'id': str(d.pk), 'delegator': _person(d.delegator), 'delegate': _person(d.delegate),
        'start_date': d.start_date.isoformat(), 'end_date': d.end_date.isoformat(), 'workflows': d.workflows,
        'reason': d.reason, 'active': d.is_active_on(today), 'revoked': d.revoked_at is not None,
        'revoked_at': d.revoked_at.isoformat() if d.revoked_at else None,
        'can_revoke': d.revoked_at is None and d.end_date >= today and (
            user.pk in (d.delegator_id, d.created_by_id) or has_perm(user, 'settings.edit')),
        'given': d.delegator_id == user.pk, 'received': d.delegate_id == user.pk,
        'created_at': d.created_at.isoformat(),
    }


class _DelegationSerializer(serializers.Serializer):
    delegate = serializers.UUIDField()
    delegator = serializers.UUIDField(required=False, allow_null=True)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    workflows = serializers.ListField(child=serializers.ChoiceField(choices=services.WORKFLOWS), min_length=1)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=300, default='')


class DelegationListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        from django.utils import timezone
        qs = ApprovalDelegation.objects.select_related('delegator', 'delegate')
        if not (request.query_params.get('all') and has_perm(request.user, 'settings.edit')):
            qs = qs.filter(Q(delegator=request.user) | Q(delegate=request.user))
        today = timezone.localdate()
        return success('Delegations.', [_delegation_out(d, request.user, today) for d in qs[:200]])

    def post(self, request):
        ser = _DelegationSerializer(data=request.data)
        if not ser.is_valid():
            return error(first_error(ser.errors), data=ser.errors)
        d = ser.validated_data
        delegator = request.user
        if d.get('delegator') and str(d['delegator']) != str(request.user.pk):
            delegator = User.objects.filter(pk=d['delegator'], is_active=True).first()
            if delegator is None:
                return error('Approver not found.', http_status=404)
        delegate = User.objects.filter(pk=d['delegate']).first()
        if delegate is None:
            return error('Delegate not found.', data={'delegate': ['Choose an employee.']})
        try:
            obj = services.create_delegation(actor=request.user, delegator=delegator, delegate=delegate,
                                             start_date=d['start_date'], end_date=d['end_date'],
                                             workflows=d['workflows'], reason=d.get('reason', ''),
                                             ip=get_client_ip(request))
        except services.DelegationError as exc:
            return error(str(exc), data={exc.field: [str(exc)]} if exc.field else None,
                         http_status=status.HTTP_400_BAD_REQUEST)
        from django.utils import timezone
        return success('Delegation created.', _delegation_out(obj, request.user, timezone.localdate()),
                       http_status=status.HTTP_201_CREATED)


class DelegationRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone
        d = ApprovalDelegation.objects.select_related('delegator', 'delegate').filter(pk=pk).first()
        if d is None or (request.user.pk not in (d.delegator_id, d.delegate_id, d.created_by_id)
                         and not has_perm(request.user, 'settings.edit')):
            return error('Delegation not found.', http_status=404)
        try:
            services.revoke_delegation(actor=request.user, delegation=d, ip=get_client_ip(request))
        except services.DelegationError as exc:
            return error(str(exc), http_status=403 if 'Only' in str(exc) else 400)
        return success('Delegation revoked.', _delegation_out(d, request.user, timezone.localdate()))


class EligibleDelegatesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        workflow = request.query_params.get('workflow', 'leave')
        if workflow not in services.WORKFLOWS:
            return error('workflow must be leave or attendance.')
        if not services.can_approve_workflow(request.user, workflow):
            return success('Eligible delegates.', [])
        qs = User.objects.filter(is_active=True).exclude(pk=request.user.pk).select_related('role')
        branch = (request.user.branch or '').strip()
        if branch:
            qs = qs.filter(branch__iexact=branch)
        out = [_person(u) for u in qs.order_by('full_name')[:500]
               if services.can_approve_workflow(u, workflow) and services._same_scope(request.user, u)]
        return success('Eligible delegates.', out)


class EscalationHeadCandidatesView(APIView):
    """Who can be the escalation head: active users who approve leave or attendance (settings.edit only)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not has_perm(request.user, 'settings.edit'):
            return error('Permission denied.', http_status=403)
        qs = User.objects.filter(is_active=True).select_related('role').order_by('full_name')[:1000]
        out = [_person(u) for u in qs
               if services.can_approve_workflow(u, 'leave') or services.can_approve_workflow(u, 'attendance')]
        return success('Escalation head candidates.', out)

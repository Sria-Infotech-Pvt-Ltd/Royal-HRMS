"""
Public website API — no login.

  GET  /api/public/plans/                       published plans, prices, features
  POST /api/public/registrations/               sign up (amount computed here)
  GET  /api/public/registrations/<reference>/   status only — no personal data

Rate-limited per IP. A registration never creates a company: that needs a
verified payment (apps.tenants.payments) and Platform Admin approval.
"""
from __future__ import annotations

import logging

from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.tenants.models import CompanyRegistration
from apps.tenants.modules import CORE, FEATURES
from apps.tenants.registrations import RegistrationError, create_registration, public_plans
from apps.tenants.serializers_saas import RegistrationCreateSerializer
from apps.tenants.subscriptions import preview_modules
from core.responses import error, first_error, get_client_ip, success

logger = logging.getLogger(__name__)


class _PublicView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]


def plan_payload(plan) -> dict:
    included = set(plan.features or []) | set(preview_modules(plan))
    return {
        'code': plan.code, 'name': plan.name, 'description': plan.description,
        'price_per_employee': str(plan.price_per_employee), 'currency': plan.currency,
        'billing_periods': plan.billing_periods or ['monthly'], 'gst_rate': str(plan.gst_rate),
        'gst_inclusive': plan.gst_inclusive, 'min_employees': plan.min_employees,
        'max_employees': plan.max_employees,
        'features': [
            {'key': f['key'], 'label': f['label'], 'category': f['category'],
             'status': 'included' if f['kind'] == CORE or f['key'] in included
             else 'coming_soon' if f['kind'] == 'coming_soon' else 'not_included'}
            for f in FEATURES
        ],
    }


class PublicPlansView(_PublicView):
    throttle_scope = 'public_read'

    def get(self, request):
        return success('Plans retrieved.', [plan_payload(p) for p in public_plans()])


class PublicRegistrationView(_PublicView):
    throttle_scope = 'public_registration'

    def post(self, request):
        serializer = RegistrationCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        data = serializer.validated_data
        if data.get('website'):                                   # honeypot filled → bot
            logger.warning('Registration honeypot triggered from %s', get_client_ip(request))
            return error('Registration could not be submitted.')
        plan = public_plans().filter(code=data['plan']).first()
        if plan is None:
            return error('Choose one of the published plans.')
        try:
            reg, payment = create_registration(plan=plan, data=data, ip=get_client_ip(request))
        except RegistrationError as exc:
            return error(str(exc))
        return success('Registration received.', {
            'reference': reg.reference, 'plan': reg.plan_name, 'billing_period': reg.billing_period,
            'employee_count': reg.employee_count, 'subtotal': str(reg.subtotal), 'gst_amount': str(reg.gst_amount),
            'gst_rate': str(reg.gst_rate), 'gst_inclusive': reg.gst_inclusive, 'total': str(reg.total),
            'currency': reg.currency, 'payment_status': reg.payment_status, 'payment': payment,
        }, http_status=status.HTTP_201_CREATED)


_STATUS_TEXT = {
    'awaiting_payment': 'Waiting for payment.',
    'payment_failed': 'Payment failed. Please try again or contact us.',
    'under_review': 'Payment received. Your registration is being reviewed.',
    'setting_up': 'Approved. Your company account is being set up.',
    'active': 'Your company account is ready. Check your email for login details.',
    'setup_delayed': 'Approved. Account setup is taking longer than usual — our team is on it.',
    'rejected': 'Your registration was not approved. Our team will contact you.',
}


def public_status(reg: CompanyRegistration) -> str:
    if reg.approval_status == CompanyRegistration.APPROVAL_REJECTED:
        return 'rejected'
    if reg.approval_status == CompanyRegistration.APPROVAL_APPROVED:
        state = reg.client.provisioning_status if reg.client else 'pending'
        return {'active': 'active', 'failed': 'setup_delayed'}.get(state, 'setting_up')
    if reg.payment_status == CompanyRegistration.PAYMENT_PAID:
        return 'under_review'
    if reg.payment_status == CompanyRegistration.PAYMENT_FAILED:
        return 'payment_failed'
    return 'awaiting_payment'


class PublicRegistrationStatusView(_PublicView):
    throttle_scope = 'public_read'

    def get(self, request, reference):
        reg = (CompanyRegistration.objects.select_related('client')
               .filter(reference=(reference or '').strip().upper()).first())
        if reg is None:
            return error('Registration not found.', http_status=status.HTTP_404_NOT_FOUND)
        state = public_status(reg)
        return success('Registration status.', {
            'reference': reg.reference, 'plan': reg.plan_name, 'total': str(reg.total), 'currency': reg.currency,
            'status': state, 'message': _STATUS_TEXT[state], 'submitted_at': reg.created_at,
        })

"""
Platform Admin → SaaS: plans, customer subscriptions, history, dashboard.

  GET        saas/features/                      feature catalogue (apps.tenants.modules)
  GET/POST   saas/plans/                         list / create
  GET/PATCH  saas/plans/<id>/                    view / edit, activate, publish
  GET/POST   saas/subscriptions/                 companies + subscriptions / assign (dry_run = preview)
  GET        saas/subscriptions/<client_id>/     detail + history
  POST       saas/subscriptions/<client_id>/change-plan/   (dry_run = module difference preview)
  POST       saas/subscriptions/<client_id>/period/        end date
  POST       saas/subscriptions/<client_id>/status/        activate / deactivate
  GET/POST   saas/subscriptions/<client_id>/payments/      payment history / record a manual payment
  POST       saas/subscriptions/<client_id>/payments/<id>/verify|reject/
  GET        saas/subscriptions/<client_id>/payments/<id>/receipt/
  POST       saas/subscriptions/<client_id>/amount-due/    amount the customer owes
  POST       saas/subscriptions/<client_id>/waiver/        waive / un-waive payment (reason required)
  POST       saas/subscriptions/<client_id>/provision/     re-apply after a failed apply
  GET        saas/history/                       all subscription history
  GET        saas/dashboard/                     counts
  POST       companies/<id>/retry-provisioning/  failed companies only

Every change writes a PlatformAdminAuditLog row (and SubscriptionHistory
for subscription changes). New companies use the existing provisioning
(create_pending_client + finish_provisioning_task) — no second path.
"""
from __future__ import annotations

import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.http import content_disposition_header
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from apps.tenants import billing, validators
from apps.tenants.authentication import PlatformAdminAuthentication
from apps.tenants.models import (
    Client, CompanyRegistration, CompanySubscription, PlatformNotification, SubscriptionHistory, SubscriptionPayment,
    SubscriptionPlan,
)
from apps.tenants.registrations import RegistrationError
from apps.tenants.registrations import approve as approve_registration
from apps.tenants.registrations import reject as reject_registration
from apps.tenants.modules import catalogue
from apps.tenants.pricing import charge, period_end
from apps.tenants.permissions import IsPlatformAdmin
from apps.tenants.serializers_saas import (
    AssignSubscriptionSerializer, CompanySubscriptionSerializer, CustomerRowSerializer, NotificationSerializer,
    RecordPaymentSerializer, RegistrationSerializer, SubscriptionHistorySerializer, SubscriptionPaymentSerializer,
    SubscriptionPlanSerializer,
)
from apps.tenants.services import CompanyCodeTaken, InvalidModules, create_pending_client
from apps.tenants.subscriptions import (
    SubscriptionError, assign_subscription, change_plan, effective_modules, module_diff, preview_modules,
    set_status, summary, update_period,
)
from apps.tenants.tasks import finish_provisioning_task, retry_provisioning_task
from apps.tenants.views import _log_platform_action
from core.pagination import paginate, paginated_data
from core.responses import error, first_error, success

logger = logging.getLogger(__name__)


def _flag(request, name) -> bool:
    return str(request.data.get(name, '')).lower() in ('1', 'true', 'yes')


class _PlatformView(APIView):
    authentication_classes = [PlatformAdminAuthentication]
    permission_classes = [IsPlatformAdmin]


class FeatureCatalogueView(_PlatformView):
    def get(self, request):
        return success('Features retrieved.', catalogue())


class PlanListCreateView(_PlatformView):
    def get(self, request):
        plans = SubscriptionPlan.objects.all()
        return success('Plans retrieved.', SubscriptionPlanSerializer(plans, many=True).data)

    def post(self, request):
        serializer = SubscriptionPlanSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        plan = serializer.save(updated_by=request.user)
        _log_platform_action(request, 'saas_plan_created', changes={
            'code': plan.code, 'name': plan.name, 'price_per_employee': str(plan.price_per_employee),
            'features': plan.features, 'status': plan.status, 'is_public': plan.is_public,
        })
        return success('Plan created.', SubscriptionPlanSerializer(plan).data, http_status=status.HTTP_201_CREATED)


class PlanDetailView(_PlatformView):
    _AUDITED = ('code', 'name', 'description', 'price_per_employee', 'currency', 'billing_periods', 'gst_rate',
                'gst_inclusive', 'min_employees', 'max_employees', 'features', 'status', 'is_public',
                'display_order')

    def get(self, request, pk):
        return success('Plan retrieved.', SubscriptionPlanSerializer(get_object_or_404(SubscriptionPlan, pk=pk)).data)

    def patch(self, request, pk):
        plan = get_object_or_404(SubscriptionPlan, pk=pk)
        before = {f: str(getattr(plan, f)) if not isinstance(getattr(plan, f), (list, bool)) else getattr(plan, f)
                  for f in self._AUDITED}
        serializer = SubscriptionPlanSerializer(plan, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        serializer.save(updated_by=request.user)
        after = {f: str(getattr(plan, f)) if not isinstance(getattr(plan, f), (list, bool)) else getattr(plan, f)
                 for f in self._AUDITED}
        changes = {f: {'from': before[f], 'to': after[f]} for f in self._AUDITED if before[f] != after[f]}
        if changes:
            _log_platform_action(request, 'saas_plan_updated', changes={'code': plan.code, **changes})
        return success('Plan updated. Existing subscriptions are unchanged.', SubscriptionPlanSerializer(plan).data)


class SubscriptionListAssignView(_PlatformView):
    def get(self, request):
        clients = (Client.objects.exclude(schema_name='public').select_related('subscription__plan')
                   .prefetch_related('subscription__payments'))
        q = (request.query_params.get('search') or '').strip()
        if q:
            clients = clients.filter(Q(company_code__icontains=q) | Q(company_name__icontains=q))
        page_obj, paginator = paginate(clients.order_by('company_name'), request, default_page_size=25)
        return success('Customers retrieved.', paginated_data(
            paginator, page_obj, CustomerRowSerializer(page_obj.object_list, many=True).data))

    def post(self, request):
        serializer = AssignSubscriptionSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        data = serializer.validated_data
        plan = SubscriptionPlan.objects.filter(pk=data['plan'], status=SubscriptionPlan.STATUS_ACTIVE).first()
        if plan is None:
            return error('Choose an active plan.', data={'plan': ['Choose an active plan.']})
        problem = _plan_fit(plan, data.get('employee_count'), data.get('billing_period'))
        if problem:
            return error(problem[1], data={problem[0]: [problem[1]]})
        modules = preview_modules(plan)
        client = None
        if data.get('client'):
            client = Client.objects.exclude(schema_name='public').filter(pk=data['client']).first()
            if client is None:
                return error('Company not found.', http_status=404)
            if CompanySubscription.objects.filter(client=client).exists():
                return error('This company already has a subscription — change its plan instead.')
        if data.get('ends_on') and data['ends_on'] < data['starts_on']:
            return error('End date cannot be before the start date.')

        if _flag(request, 'dry_run'):
            current = sorted(client.enabled_modules or []) if client else []
            return success('Preview ready. Nothing has been saved.', {
                'plan': SubscriptionPlanSerializer(plan).data, 'modules': modules,
                'current_modules': current if client else None,
                'difference': module_diff(current, modules) if client else None,
                'new_company': client is None,
            })

        if client is not None:
            return self._assign_existing(request, client, plan, data)
        return self._assign_new(request, plan, modules, data)

    def _assign(self, request, client, plan, data, admin_email=''):
        """Save the subscription awaiting payment (never paid by assignment);
        a waiver given here provisions it straight away."""
        # End date: as sent (a date, or null = no end date). Only when the field
        # is left out entirely is it one billing period from the start.
        ends_on = data.get('ends_on') if 'ends_on' in data else period_end(data['starts_on'],
                                                                           data.get('billing_period', ''))
        sub = assign_subscription(
            client=client, plan=plan, starts_on=data['starts_on'], ends_on=ends_on,
            employee_count=data.get('employee_count'), billing_period=data.get('billing_period', ''),
            source=CompanySubscription.SOURCE_MANUAL, admin=request.user, notes=data.get('notes', ''), apply=False,
        )
        sub.amount_due = data.get('amount_due')
        if sub.amount_due is None and sub.employee_count:
            # Same server-side maths as a plan change, so the total is known
            # before the first payment.
            sub.amount_due = charge(sub.price_per_employee, sub.gst_rate, sub.gst_inclusive,
                                    sub.employee_count, sub.billing_period)['total']
        sub.provisioning_status = CompanySubscription.PROVISION_AWAITING_PAYMENT
        sub.pending_admin_email = admin_email
        sub.save(update_fields=['amount_due', 'provisioning_status', 'pending_admin_email', 'updated_at'])
        if data.get('waive_reason', '').strip():
            billing.waive_payment(sub=sub, admin=request.user, reason=data['waive_reason'])
            sub.refresh_from_db()
        return sub

    @staticmethod
    def _assigned_message(sub, new_company: bool) -> str:
        if sub.provisioning_status == CompanySubscription.PROVISION_AWAITING_PAYMENT:
            return ('Subscription saved — awaiting payment. ' + (
                'The company is set up' if new_company else 'Its modules are applied') +
                ' once payment is confirmed or waived.')
        if new_company:
            return ('Payment waived — company creation started. Provisioning runs in the background; the admin '
                    'receives the activation email when it finishes.')
        return 'Payment waived — subscription assigned and modules applied.'

    def _assign_existing(self, request, client, plan, data):
        before = sorted(client.enabled_modules or [])
        try:
            with transaction.atomic():
                sub = self._assign(request, client, plan, data)
        except (SubscriptionError, billing.PaymentError) as exc:
            return error(str(exc))
        _log_platform_action(request, 'saas_subscription_assigned', target_company=client, changes={
            'plan': plan.code, 'modules_before': before, 'modules_plan': effective_modules(sub),
            'amount_due': str(sub.amount_due) if sub.amount_due is not None else None,
            'payment_status': sub.payment_status, 'provisioning_status': sub.provisioning_status,
        })
        return success(self._assigned_message(sub, False), CompanySubscriptionSerializer(sub).data,
                       http_status=status.HTTP_201_CREATED)

    def _assign_new(self, request, plan, modules, data):
        company = data['new_company']
        try:
            with transaction.atomic():
                client = create_pending_client(
                    company_code=company['company_code'], company_name=company['company_name'], modules=modules,
                    contact_name=company['contact_name'], contact_phone=company['contact_phone'],
                    address=company['address'], gstin=company['gstin'],
                    expected_employee_count=company['expected_employee_count'] or data.get('employee_count'),
                    contract_start_date=company['contract_start_date'] or data['starts_on'],
                )
                # Registry row only — nothing is set up until payment is settled.
                Client.objects.filter(pk=client.pk).update(
                    provisioning_status=Client.PROVISIONING_AWAITING_PAYMENT, updated_at=timezone.now())
                sub = self._assign(request, client, plan, data, admin_email=company['admin_email'])
        except (InvalidModules, SubscriptionError, billing.PaymentError) as exc:
            return error(str(exc))
        except CompanyCodeTaken as exc:
            return error(f'Company code "{exc}" is already in use.')
        _log_platform_action(request, 'saas_company_created_with_subscription', target_company=client, changes={
            'company_name': client.company_name, 'plan': plan.code, 'modules': effective_modules(sub),
            'amount_due': str(sub.amount_due) if sub.amount_due is not None else None,
            'payment_status': sub.payment_status, 'provisioning_status': sub.provisioning_status,
        })
        return success(self._assigned_message(sub, True), CompanySubscriptionSerializer(sub).data,
                       http_status=status.HTTP_202_ACCEPTED)


def _plan_fit(plan, employee_count, billing_period=''):
    """(field, message) when the values fall outside what the plan offers, else None."""
    try:
        validators.employee_count_in_plan(employee_count, plan)
    except ValidationError as exc:
        return 'employee_count', str(exc.detail[0])
    if billing_period and plan.billing_periods and billing_period not in plan.billing_periods:
        return 'billing_period', f'The {plan.name} plan is billed {" or ".join(plan.billing_periods)} only.'
    return None


def _whole_number(raw, lo=1, hi=validators.MAX_EMPLOYEES):
    """int in [lo, hi] from request data, None when blank; ValueError otherwise."""
    if raw in (None, ''):
        return None
    if isinstance(raw, bool) or not str(raw).strip().isdigit():
        raise ValueError
    value = int(str(raw).strip())
    if not lo <= value <= hi:
        raise ValueError
    return value


def _change_pricing(sub, plan, employee_count):
    """Old vs new charges for a plan change preview (None when the employee count is unknown)."""
    if not employee_count:
        return None
    from apps.tenants.pricing import plan_charge
    new = plan_charge(plan, employee_count, sub.billing_period)
    return {
        'employee_count': employee_count, 'billing_period': sub.billing_period or 'monthly',
        'from': {'plan': sub.plan_name, 'price_per_employee': str(sub.price_per_employee), 'currency': sub.currency,
                 'amount_due': str(sub.amount_due) if sub.amount_due is not None else None},
        'to': {'plan': plan.name, 'price_per_employee': str(plan.price_per_employee), 'currency': plan.currency,
               'months': new['months'], 'subtotal': str(new['subtotal']), 'gst_rate': str(plan.gst_rate),
               'gst_inclusive': plan.gst_inclusive, 'gst_amount': str(new['gst_amount']),
               'amount_due': str(new['total'])},
    }


def _subscription_or_404(client_id):
    return get_object_or_404(CompanySubscription.objects.select_related('client', 'plan'), client_id=client_id)


class SubscriptionDetailView(_PlatformView):
    def get(self, request, client_id):
        client = get_object_or_404(Client.objects.exclude(schema_name='public'), pk=client_id)
        sub = CompanySubscription.objects.filter(client=client).select_related('plan').first()
        history = (SubscriptionHistory.objects.filter(subscription=sub).select_related('admin', 'subscription__client')
                   if sub else [])
        payments = (SubscriptionPayment.objects.filter(subscription=sub).select_related('recorded_by', 'reviewed_by')
                    if sub else [])
        return success('Subscription retrieved.', {
            'company': CustomerRowSerializer(client).data,
            'history': SubscriptionHistorySerializer(history, many=True).data,
            'payments': SubscriptionPaymentSerializer(payments, many=True).data,
        })


class SubscriptionChangePlanView(_PlatformView):
    def post(self, request, client_id):
        sub = _subscription_or_404(client_id)
        plan = SubscriptionPlan.objects.filter(pk=request.data.get('plan'), status=SubscriptionPlan.STATUS_ACTIVE).first()
        if plan is None:
            return error('Choose an active plan.')
        current = effective_modules(sub)
        new = preview_modules(plan, sub.extra_modules or [], sub.removed_modules or [])
        try:
            employee_count = _whole_number(request.data.get('employee_count'))
        except ValueError:
            msg = f'Employee count must be a whole number from 1 to {validators.MAX_EMPLOYEES}.'
            return error(msg, data={'employee_count': [msg]})
        # The plan must fit the numbers billing will use: the new count, else the current one.
        count = employee_count or sub.employee_count
        problem = _plan_fit(plan, count, sub.billing_period)
        if problem:
            return error(problem[1], data={problem[0]: [problem[1]]})
        if _flag(request, 'dry_run'):
            return success('Preview ready. Nothing has been saved.', {
                'from_plan': sub.plan_name, 'to_plan': plan.name, 'same_plan': plan.pk == sub.plan_id,
                'modules': new, 'difference': module_diff(current, new),
                'pricing': _change_pricing(sub, plan, count),
            })
        try:
            sub = change_plan(sub=sub, plan=plan, admin=request.user, note=str(request.data.get('note', ''))[:500],
                              employee_count=employee_count)
        except SubscriptionError as exc:
            return error(str(exc))
        _log_platform_action(request, 'saas_plan_changed', target_company=sub.client, changes={
            'to_plan': plan.code, 'difference': module_diff(current, effective_modules(sub)),
            'amount_due': str(sub.amount_due) if sub.amount_due is not None else None,
        })
        sub = CompanySubscription.objects.select_related('plan', 'client').prefetch_related('payments').get(pk=sub.pk)
        return success('Plan changed.', CompanySubscriptionSerializer(sub).data)


class SubscriptionPeriodView(_PlatformView):
    def post(self, request, client_id):
        sub = _subscription_or_404(client_id)
        from django.utils.dateparse import parse_date
        raw = request.data.get('ends_on')
        try:
            ends_on = parse_date(raw) if raw else None
        except ValueError:                       # well-formed but impossible, e.g. 2026-02-30
            ends_on = None
        if raw and ends_on is None:
            return error('End date must be a valid date (YYYY-MM-DD).', data={'ends_on': ['Enter a valid date.']})
        if ends_on is not None:
            from apps.tenants.serializers_saas import _sane_date
            try:
                _sane_date(ends_on, 'End date')
            except ValidationError as exc:
                return error(str(exc.detail[0]), data={'ends_on': exc.detail})
        before = sub.ends_on
        try:
            sub = update_period(sub=sub, ends_on=ends_on, admin=request.user, note=str(request.data.get('note', ''))[:500])
        except SubscriptionError as exc:
            return error(str(exc))
        _log_platform_action(request, 'saas_subscription_period_changed', target_company=sub.client, changes={
            'ends_on': {'from': before.isoformat() if before else None, 'to': ends_on.isoformat() if ends_on else None},
        })
        return success('Subscription period updated.', CompanySubscriptionSerializer(sub).data)


class SubscriptionStatusView(_PlatformView):
    def post(self, request, client_id):
        sub = _subscription_or_404(client_id)
        active = request.data.get('active')
        if not isinstance(active, bool):
            return error('"active" must be true or false.')
        sub = set_status(sub=sub, active=active, admin=request.user, note=str(request.data.get('note', ''))[:500])
        _log_platform_action(request, 'saas_subscription_activated' if active else 'saas_subscription_deactivated',
                             target_company=sub.client)
        return success('Subscription activated.' if active else 'Subscription deactivated.',
                       CompanySubscriptionSerializer(sub).data)


# ─── Manual payments ─────────────────────────────────────────────────────────

def _payment_log(request, action, sub, payment=None, **extra):
    changes = {'payment_status': sub.payment_status, 'provisioning_status': sub.provisioning_status, **extra}
    if payment is not None:
        changes.update({'payment_id': str(payment.pk), 'amount': str(payment.amount), 'currency': payment.currency,
                        'method': payment.method, 'paid_on': payment.paid_on.isoformat(),
                        'reference': payment.reference, 'payment_record_status': payment.status})
    _log_platform_action(request, action, target_company=sub.client, changes=changes)


def _fresh(sub):
    return CompanySubscription.objects.select_related('client', 'plan').get(pk=sub.pk)


class SubscriptionPaymentsView(_PlatformView):
    def get(self, request, client_id):
        sub = _subscription_or_404(client_id)
        payments = sub.payments.select_related('recorded_by', 'reviewed_by')
        return success('Payments retrieved.', SubscriptionPaymentSerializer(payments, many=True).data)

    def post(self, request, client_id):
        sub = _subscription_or_404(client_id)
        serializer = RecordPaymentSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        data = serializer.validated_data
        try:
            payment = billing.record_payment(
                sub=sub, amount=data['amount'], method=data['method'], paid_on=data['paid_on'],
                reference=data['reference'], notes=data['notes'], receipt=data.get('receipt'),
                admin=request.user, confirm=data['confirm'], allow_overpayment=data['allow_overpayment'])
        except billing.OverpaymentWarning as exc:
            # Nothing saved; the screen asks the admin to confirm and resends with allow_overpayment.
            return error(str(exc), data={'requires_confirmation': 'overpayment',
                                         'outstanding': f'{exc.outstanding:.2f}', 'pending': f'{exc.pending:.2f}'})
        except billing.PaymentError as exc:
            return error(str(exc))
        sub = _fresh(sub)
        _payment_log(request, 'saas_payment_recorded', sub, payment, confirmed=data['confirm'],
                     has_receipt=bool(payment.receipt))
        return success('Payment recorded and confirmed.' if data['confirm'] else
                       'Payment recorded — confirm it once the money is received.',
                       {'payment': SubscriptionPaymentSerializer(payment).data,
                        'subscription': CompanySubscriptionSerializer(sub).data},
                       http_status=status.HTTP_201_CREATED)


class SubscriptionPaymentActionView(_PlatformView):
    """POST .../payments/<id>/verify/  or  .../reject/ {"reason"}"""

    def post(self, request, client_id, payment_id, action):
        sub = _subscription_or_404(client_id)
        try:
            if action == 'verify':
                payment = billing.verify_payment(sub=sub, payment_id=payment_id, admin=request.user)
            else:
                payment = billing.reject_payment(sub=sub, payment_id=payment_id, admin=request.user,
                                                 reason=str(request.data.get('reason', ''))[:1000])
        except SubscriptionPayment.DoesNotExist:
            return error('Payment not found.', http_status=404)
        except billing.PaymentError as exc:
            return error(str(exc))
        sub = _fresh(sub)
        _payment_log(request, 'saas_payment_verified' if action == 'verify' else 'saas_payment_rejected', sub, payment,
                     **({} if action == 'verify' else {'reason': payment.rejection_reason}))
        return success('Payment confirmed.' if action == 'verify' else 'Payment rejected.',
                       {'payment': SubscriptionPaymentSerializer(payment).data,
                        'subscription': CompanySubscriptionSerializer(sub).data})


_RECEIPT_TYPES = ((b'%PDF-', 'application/pdf'), (b'\x89PNG', 'image/png'), (b'\xff\xd8\xff', 'image/jpeg'))


class SubscriptionPaymentReceiptView(_PlatformView):
    """Streams a receipt (private storage — proxied, never a public link)."""

    def get(self, request, client_id, payment_id):
        payment = get_object_or_404(SubscriptionPayment, pk=payment_id, subscription__client_id=client_id)
        if not payment.receipt:
            return error('No receipt was attached to this payment.', http_status=404)
        storage = payment.receipt.storage
        reader = getattr(storage, 'read_via_download_api', None)
        try:
            if reader:
                content = reader(payment.receipt.name)
            else:
                with payment.receipt.open('rb') as fh:
                    content = fh.read()
        except Exception:
            logger.warning('Could not fetch payment receipt %s', payment.receipt.name, exc_info=True)
            return error('Could not load the receipt. Please try again.', http_status=status.HTTP_502_BAD_GATEWAY)
        content_type = next((ct for magic, ct in _RECEIPT_TYPES if content.startswith(magic)), None)
        if content_type is None:
            return error('Could not load the receipt. Please try again.', http_status=status.HTTP_502_BAD_GATEWAY)
        response = HttpResponse(content, content_type=content_type)
        response['Content-Disposition'] = content_disposition_header(
            as_attachment=False, filename=payment.receipt_name or 'receipt')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class SubscriptionAmountDueView(_PlatformView):
    def post(self, request, client_id):
        sub = _subscription_or_404(client_id)
        from decimal import Decimal, InvalidOperation
        try:
            amount = Decimal(str(request.data.get('amount_due', '')).strip()).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError):
            return error('Amount due must be a number.', data={'amount_due': ['Enter a number.']})
        if not amount.is_finite():                                   # "NaN" / "Infinity" parse as Decimals
            return error('Amount due must be a number.', data={'amount_due': ['Enter a number.']})
        if amount > Decimal('9999999999.99'):
            return error('Amount due is too large.', data={'amount_due': ['Enter at most 9,999,999,999.99.']})
        before = sub.amount_due
        try:
            sub = billing.set_amount_due(sub=sub, amount=amount, admin=request.user,
                                         note=str(request.data.get('note', ''))[:500])
        except billing.PaymentError as exc:
            return error(str(exc))
        sub = _fresh(sub)
        _payment_log(request, 'saas_amount_due_changed', sub,
                     amount_due={'from': str(before) if before is not None else None, 'to': str(sub.amount_due)})
        return success('Amount due updated.', CompanySubscriptionSerializer(sub).data)


class SubscriptionWaiverView(_PlatformView):
    """POST {"waive": true, "reason": "..."} or {"waive": false, "note": "..."}"""

    def post(self, request, client_id):
        sub = _subscription_or_404(client_id)
        waive = request.data.get('waive')
        if not isinstance(waive, bool):
            return error('"waive" must be true or false.')
        try:
            if waive:
                sub = billing.waive_payment(sub=sub, admin=request.user, reason=str(request.data.get('reason', ''))[:1000])
            else:
                sub = billing.remove_waiver(sub=sub, admin=request.user, note=str(request.data.get('note', ''))[:500])
        except billing.PaymentError as exc:
            return error(str(exc))
        sub = _fresh(sub)
        _payment_log(request, 'saas_payment_waived' if waive else 'saas_payment_waiver_removed', sub,
                     **({'reason': sub.payment_waiver_reason} if waive else {}))
        return success('Payment waived.' if waive else 'Waiver removed.', CompanySubscriptionSerializer(sub).data)


class SubscriptionProvisionView(_PlatformView):
    """Re-apply an existing company's subscription after a failed apply."""

    def post(self, request, client_id):
        sub = _subscription_or_404(client_id)
        try:
            sub = billing.retry_apply(sub=sub, admin=request.user)
        except billing.PaymentError as exc:
            return error(str(exc))
        sub = _fresh(sub)
        _payment_log(request, 'saas_subscription_provision_retried', sub)
        if sub.provisioning_status == CompanySubscription.PROVISION_SUCCESS:
            return success('Subscription applied.', CompanySubscriptionSerializer(sub).data)
        return error(sub.provisioning_error or 'The subscription could not be applied.')


class SubscriptionHistoryListView(_PlatformView):
    def get(self, request):
        qs = SubscriptionHistory.objects.select_related('admin', 'subscription__client')
        page_obj, paginator = paginate(qs, request, default_page_size=50)
        return success('History retrieved.', paginated_data(
            paginator, page_obj, SubscriptionHistorySerializer(page_obj.object_list, many=True).data))


class SaasDashboardView(_PlatformView):
    def get(self, request):
        clients = Client.objects.exclude(schema_name='public')
        subs = CompanySubscription.objects.all()
        per_plan = list(subs.values('plan_name').annotate(customers=Count('id')).order_by('-customers'))
        return success('SaaS dashboard.', {
            'plans_total': SubscriptionPlan.objects.filter(is_legacy=False).count(),
            'plans_active': SubscriptionPlan.objects.filter(is_legacy=False, status=SubscriptionPlan.STATUS_ACTIVE).count(),
            'plans_public': SubscriptionPlan.objects.filter(is_public=True).count(),
            'customers_total': clients.count(),
            'customers_without_subscription': clients.filter(subscription__isnull=True).count(),
            'subscriptions_active': subs.filter(status=CompanySubscription.STATUS_ACTIVE).count(),
            'subscriptions_inactive': subs.filter(status=CompanySubscription.STATUS_INACTIVE).count(),
            'provisioning_failed': clients.filter(provisioning_status=Client.PROVISIONING_FAILED).count(),
            'by_source': dict(subs.values_list('source').annotate(n=Count('id'))),
            'by_plan': per_plan,
            'registrations_pending_approval': CompanyRegistration.objects.filter(
                payment_status='paid', approval_status='pending').count(),
            'registrations_awaiting_payment': CompanyRegistration.objects.filter(
                payment_status__in=['pending', 'failed'], approval_status='pending').count(),
            'registrations_rejected': CompanyRegistration.objects.filter(approval_status='rejected').count(),
            'registrations_paid': CompanyRegistration.objects.filter(payment_status='paid').count(),
        })


class RetryProvisioningView(_PlatformView):
    def post(self, request, pk):
        admin_email = str(request.data.get('admin_email') or '').strip()
        try:
            validate_email(admin_email)
        except DjangoValidationError:
            return error('Enter a valid email address for the company admin.',
                         data={'admin_email': ['Enter a valid email address.']})
        claimed = Client.objects.filter(pk=pk, provisioning_status=Client.PROVISIONING_FAILED).update(
            provisioning_status=Client.PROVISIONING_PENDING, updated_at=timezone.now())
        if not claimed:
            return error('Only a company whose provisioning failed can be retried.')
        client = Client.objects.get(pk=pk)
        try:
            retry_provisioning_task.delay(str(client.pk), admin_email)
        except Exception:
            Client.objects.filter(pk=pk).update(provisioning_status=Client.PROVISIONING_FAILED)
            logger.exception('Failed to queue provisioning retry for %s.', client.company_code)
            return error('Could not start the retry — the task queue is unreachable.',
                         http_status=status.HTTP_503_SERVICE_UNAVAILABLE)
        sub = CompanySubscription.objects.filter(client=client).first()
        if sub is not None:
            if sub.provisioning_status == CompanySubscription.PROVISION_FAILED:
                CompanySubscription.objects.filter(pk=sub.pk).update(
                    provisioning_status=CompanySubscription.PROVISION_PENDING, provisioning_error='')
            SubscriptionHistory.objects.create(subscription=sub, event=SubscriptionHistory.EVENT_PROVISIONING_RETRIED,
                                               before={}, after=summary(sub), admin=request.user)
        _log_platform_action(request, 'company_provisioning_retried', target_company=client)
        return success('Provisioning retry started — runs in the background.', http_status=status.HTTP_202_ACCEPTED)


# ─── Website registrations & notifications ───────────────────────────────────

_REG_FILTERS = {
    'pending_approval': Q(payment_status='paid', approval_status='pending'),
    'awaiting_payment': Q(payment_status__in=['pending', 'failed'], approval_status='pending'),
    'approved': Q(approval_status='approved'),
    'rejected': Q(approval_status='rejected'),
}


class RegistrationListView(_PlatformView):
    def get(self, request):
        qs = CompanyRegistration.objects.select_related('plan', 'client', 'reviewed_by').prefetch_related('payments')
        f = _REG_FILTERS.get(request.query_params.get('status', ''))
        if f is not None:
            qs = qs.filter(f)
        q = (request.query_params.get('search') or '').strip()
        if q:
            qs = qs.filter(Q(reference__icontains=q) | Q(company_name__icontains=q) | Q(company_code__icontains=q))
        page_obj, paginator = paginate(qs, request, default_page_size=25)
        return success('Registrations retrieved.', paginated_data(
            paginator, page_obj, RegistrationSerializer(page_obj.object_list, many=True).data))


class RegistrationDetailView(_PlatformView):
    def get(self, request, pk):
        reg = get_object_or_404(CompanyRegistration.objects.select_related('plan', 'client', 'reviewed_by'), pk=pk)
        return success('Registration retrieved.', RegistrationSerializer(reg).data)


class RegistrationApproveView(_PlatformView):
    """Approve a PAID registration: company + subscription are created with the
    same services as manual assignment, then provisioning is queued."""

    def post(self, request, pk):
        code = str(request.data.get('company_code') or '').strip() or None
        try:
            reg = approve_registration(registration_id=pk, admin=request.user, company_code=code)
        except CompanyRegistration.DoesNotExist:
            return error('Registration not found.', http_status=404)
        except RegistrationError as exc:
            return error(str(exc))
        client = reg.client
        try:
            finish_provisioning_task.delay(str(client.id), reg.admin_email, client.enabled_modules)
        except Exception:
            Client.objects.filter(pk=client.pk).update(provisioning_status=Client.PROVISIONING_FAILED)
            logger.exception('Failed to queue provisioning for registration %s.', reg.reference)
            return error('Approved, but provisioning could not be started (task queue unreachable). '
                         'Use "Retry provisioning".', http_status=status.HTTP_503_SERVICE_UNAVAILABLE)
        _log_platform_action(request, 'saas_registration_approved', target_company=client, changes={
            'reference': reg.reference, 'plan': reg.plan.code, 'modules': client.enabled_modules,
        })
        return success('Registration approved — the company is being set up. The admin receives the '
                       'activation email when it finishes.', RegistrationSerializer(reg).data)


class RegistrationRejectView(_PlatformView):
    def post(self, request, pk):
        try:
            reg = reject_registration(registration_id=pk, admin=request.user,
                                      reason=str(request.data.get('reason', '')))
        except CompanyRegistration.DoesNotExist:
            return error('Registration not found.', http_status=404)
        except RegistrationError as exc:
            return error(str(exc))
        _log_platform_action(request, 'saas_registration_rejected', changes={
            'reference': reg.reference, 'reason': reg.rejection_reason, 'refund_status': reg.refund_status,
        })
        return success('Registration rejected.', RegistrationSerializer(reg).data)


class NotificationListView(_PlatformView):
    def get(self, request):
        qs = PlatformNotification.objects.filter(recipient=request.user)
        return success('Notifications.', {
            'unread_count': qs.filter(is_read=False).count(),
            'results': NotificationSerializer(qs[:30], many=True).data,
        })


class NotificationReadView(_PlatformView):
    """POST {"ids": [...]} or {"all": true} — mark as read (own notifications only)."""

    def post(self, request):
        qs = PlatformNotification.objects.filter(recipient=request.user, is_read=False)
        if request.data.get('all') is not True:
            ids = request.data.get('ids')
            if not isinstance(ids, list):
                return error('Send "ids" (a list) or "all": true.')
            qs = qs.filter(pk__in=[i for i in ids if isinstance(i, str)])
        updated = qs.update(is_read=True)
        return success('Marked as read.', {'updated': updated})


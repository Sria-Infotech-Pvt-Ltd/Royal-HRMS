from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.hrms.serializers import validate_receipt_file
from apps.tenants.models import (
    Client, CompanyRegistration, CompanySubscription, SubscriptionHistory, SubscriptionPayment, SubscriptionPlan,
)
from apps.tenants.modules import resolve_modules, validate_features
from apps.tenants.serializers import ClientCreateSerializer
from apps.tenants import validators
from apps.tenants.subscriptions import effective_modules, preview_modules

BILLING_PERIODS = ('monthly', 'yearly')
# ISO 4217 codes a plan can be priced in (frontend/lib/currency.ts lists the same).
# Stored as-is; nothing is converted between currencies.
SUPPORTED_CURRENCIES = ('INR', 'USD', 'EUR', 'GBP', 'AED', 'SAR', 'CAD', 'AUD', 'SGD')


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    modules = serializers.SerializerMethodField()
    subscriber_count = serializers.SerializerMethodField()
    updated_by_name = serializers.CharField(source='updated_by.full_name', read_only=True, default=None)

    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'code', 'name', 'description', 'price_per_employee', 'currency', 'billing_periods',
            'gst_rate', 'gst_inclusive', 'min_employees', 'max_employees', 'features', 'modules',
            'status', 'is_public', 'display_order', 'is_legacy', 'subscriber_count',
            'updated_by_name', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'is_legacy', 'modules', 'subscriber_count', 'updated_by_name',
                            'created_at', 'updated_at']
        extra_kwargs = {
            'description': {'max_length': 1000},
            'min_employees': {'min_value': 1, 'max_value': validators.MAX_EMPLOYEES},
            'max_employees': {'min_value': 1, 'max_value': validators.MAX_EMPLOYEES},
        }

    def get_modules(self, obj):
        return preview_modules(obj)

    def get_subscriber_count(self, obj):
        return obj.subscriptions.count()

    def validate_code(self, value):
        value = value.strip()
        if self.instance and self.instance.code.lower() == value.lower():
            return self.instance.code                                  # existing codes stay editable as-is
        value = validators.plan_code(value)
        if self.instance and self.instance.code != value and self.instance.subscriptions.exists():
            raise serializers.ValidationError('The code cannot change once companies are on this plan.')
        return value

    def validate_features(self, value):
        clean, errors = validate_features(value)
        if errors:
            raise serializers.ValidationError(errors)
        return clean

    def validate_name(self, value):
        return validators.business_name(value, 'Plan name')

    def validate_billing_periods(self, value):
        if not isinstance(value, list) or any(v not in BILLING_PERIODS for v in value):
            raise serializers.ValidationError('Billing periods must be "monthly" and/or "yearly".')
        if not value:
            raise serializers.ValidationError('Choose at least one billing period.')
        return sorted(set(value))

    def validate_currency(self, value):
        value = value.strip().upper()
        unchanged = self.instance is not None and value == self.instance.currency
        if value not in SUPPORTED_CURRENCIES and not unchanged:
            raise serializers.ValidationError(
                f'Choose a supported currency: {", ".join(SUPPORTED_CURRENCIES)}.')
        return value

    def validate(self, data):
        price = data.get('price_per_employee', getattr(self.instance, 'price_per_employee', 0))
        if price is not None and price < 0:
            raise serializers.ValidationError({'price_per_employee': 'Price cannot be negative.'})
        rate = data.get('gst_rate', getattr(self.instance, 'gst_rate', 0))
        if rate is not None and not (0 <= rate <= 100):
            raise serializers.ValidationError({'gst_rate': 'GST rate must be between 0 and 100.'})
        lo = data.get('min_employees', getattr(self.instance, 'min_employees', None))
        hi = data.get('max_employees', getattr(self.instance, 'max_employees', None))
        if lo and hi and lo > hi:
            raise serializers.ValidationError({'max_employees': 'Maximum must be at least the minimum.'})
        if self.instance and self.instance.is_legacy and {'features', 'status', 'is_public'} & set(data):
            raise serializers.ValidationError('The legacy plan\'s features and status are fixed.')
        if data.get('is_public') and data.get('status', getattr(self.instance, 'status', None)) != \
                SubscriptionPlan.STATUS_ACTIVE:
            raise serializers.ValidationError({'is_public': 'Only active plans can be published.'})
        return data


class SubscriptionHistorySerializer(serializers.ModelSerializer):
    admin_name = serializers.CharField(source='admin.full_name', read_only=True, default=None)
    company_code = serializers.CharField(source='subscription.client.company_code', read_only=True)
    company_name = serializers.CharField(source='subscription.client.company_name', read_only=True)

    class Meta:
        model = SubscriptionHistory
        fields = ['id', 'company_code', 'company_name', 'event', 'before', 'after', 'note', 'admin_name',
                  'created_at']


class CompanySubscriptionSerializer(serializers.ModelSerializer):
    client_id = serializers.UUIDField(read_only=True)
    plan_code = serializers.CharField(source='plan.code', read_only=True)
    modules = serializers.SerializerMethodField()
    amount_received = serializers.SerializerMethodField()
    unconfirmed_payments = serializers.SerializerMethodField()
    plan_outdated = serializers.SerializerMethodField()
    latest_plan = serializers.SerializerMethodField()

    class Meta:
        model = CompanySubscription
        fields = [
            'id', 'client_id', 'plan', 'plan_code', 'plan_name', 'source', 'status', 'starts_on', 'ends_on',
            'employee_count', 'billing_period', 'price_per_employee', 'currency', 'gst_rate',
            'gst_inclusive', 'max_employees', 'plan_features', 'extra_modules', 'removed_modules',
            'modules', 'notes', 'payment_status', 'amount_due', 'amount_received', 'unconfirmed_payments',
            'payment_waiver_reason', 'provisioning_status', 'provisioning_error', 'provisioned_at',
            'plan_outdated', 'latest_plan', 'created_at', 'updated_at',
        ]

    def get_modules(self, obj):
        return effective_modules(obj)

    # Computed in Python so a prefetch of `payments` (the list view) is used.
    def get_amount_received(self, obj):
        total = sum((p.amount for p in obj.payments.all() if p.status == SubscriptionPayment.STATUS_VERIFIED),
                    Decimal('0'))
        return f'{total:.2f}'

    def get_plan_outdated(self, obj) -> bool:
        """The plan was edited after this subscription took its snapshot. The
        subscription keeps its terms (snapshot rule) until the plan is applied
        again (change plan to the same plan)."""
        plan = obj.plan
        if plan is None or plan.is_legacy or obj.source == CompanySubscription.SOURCE_LEGACY:
            return False
        return (sorted(obj.plan_features or []) != sorted(plan.features or [])
                or obj.price_per_employee != plan.price_per_employee or obj.gst_rate != plan.gst_rate
                or obj.gst_inclusive != plan.gst_inclusive or obj.currency != plan.currency
                or obj.max_employees != plan.max_employees)

    def get_latest_plan(self, obj):
        if not self.get_plan_outdated(obj):
            return None
        plan = obj.plan
        return {'modules': preview_modules(plan), 'price_per_employee': str(plan.price_per_employee),
                'currency': plan.currency, 'gst_rate': str(plan.gst_rate), 'gst_inclusive': plan.gst_inclusive,
                'max_employees': plan.max_employees}

    def get_unconfirmed_payments(self, obj):
        return sum(1 for p in obj.payments.all() if p.status == SubscriptionPayment.STATUS_RECORDED)


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    method_label = serializers.CharField(source='get_method_display', read_only=True)
    has_receipt = serializers.SerializerMethodField()
    recorded_by_name = serializers.CharField(source='recorded_by.full_name', read_only=True, default=None)
    reviewed_by_name = serializers.CharField(source='reviewed_by.full_name', read_only=True, default=None)

    class Meta:
        model = SubscriptionPayment
        fields = ['id', 'amount', 'currency', 'method', 'method_label', 'paid_on', 'reference', 'notes',
                  'has_receipt', 'receipt_name', 'status', 'rejection_reason', 'recorded_by_name',
                  'reviewed_by_name', 'reviewed_at', 'created_at']

    def get_has_receipt(self, obj):
        return bool(obj.receipt)


class RecordPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    method = serializers.ChoiceField(choices=SubscriptionPayment.METHOD_CHOICES)
    paid_on = serializers.DateField()
    reference = serializers.CharField(required=False, allow_blank=True, default='', max_length=100,
                                      validators=[validators.payment_reference])
    notes = serializers.CharField(required=False, allow_blank=True, default='', max_length=1000)
    receipt = serializers.FileField(required=False, allow_null=True, validators=[validate_receipt_file])
    confirm = serializers.BooleanField(required=False, default=False)

    def validate_paid_on(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError('Payment date cannot be in the future.')
        if value < EARLIEST_DATE:
            raise serializers.ValidationError(f'Payment date must be after {EARLIEST_DATE:%Y}.')
        return value


class CustomerRowSerializer(serializers.ModelSerializer):
    """A company with its subscription (None when not assigned yet)."""
    subscription = serializers.SerializerMethodField()
    # What the company's users can actually use — the same list the login
    # module claim and the API gate use (apps.tenants.access).
    effective_modules = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = ['id', 'company_code', 'company_name', 'contact_name', 'contact_phone',
                  'expected_employee_count', 'is_active', 'provisioning_status', 'enabled_modules',
                  'effective_modules', 'created_at', 'subscription']

    def get_effective_modules(self, obj):
        from apps.tenants.access import visible_modules
        return visible_modules(obj)

    def get_subscription(self, obj):
        sub = getattr(obj, 'subscription', None)
        return CompanySubscriptionSerializer(sub).data if sub else None


EARLIEST_DATE = date(2000, 1, 1)


def _sane_date(value, what='Date'):
    latest = timezone.localdate() + timedelta(days=5 * 366)
    if value < EARLIEST_DATE or value > latest:
        raise serializers.ValidationError(f'{what} must be between {EARLIEST_DATE:%Y} and {latest:%Y}.')
    return value


class SaasNewCompanySerializer(ClientCreateSerializer):
    """A new company added from SaaS → Add customer: same fields as the
    Companies form, with the stricter formats website sign-ups already use
    (the code becomes part of the database schema name)."""
    company_code = serializers.CharField(max_length=20)

    def validate_company_code(self, value):
        from apps.tenants.registrations import RegistrationError, normalise_code
        try:
            return normalise_code(value)
        except RegistrationError as exc:
            raise serializers.ValidationError(str(exc))

    def validate_company_name(self, value):
        return validators.business_name(value, 'Company name')

    def validate_contact_name(self, value):
        return validators.person_name(value)

    def validate_contact_phone(self, value):
        return validators.phone(value)


class AssignSubscriptionSerializer(serializers.Serializer):
    """Either client (an existing company) or new_company (created and provisioned)."""
    client = serializers.UUIDField(required=False, allow_null=True)
    new_company = SaasNewCompanySerializer(required=False, allow_null=True)
    plan = serializers.UUIDField()
    starts_on = serializers.DateField()
    ends_on = serializers.DateField(required=False, allow_null=True)
    employee_count = serializers.IntegerField(required=False, allow_null=True, min_value=1,
                                              max_value=validators.MAX_EMPLOYEES)
    billing_period = serializers.ChoiceField(choices=('', *BILLING_PERIODS), required=False, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='', max_length=1000)
    # Payment: amount owed, or an explicit waiver. Recording the payment
    # itself (with optional receipt) is a separate call to the payments API.
    amount_due = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True,
                                          min_value=Decimal('0.01'))
    waive_reason = serializers.CharField(required=False, allow_blank=True, default='', max_length=1000)

    def validate_starts_on(self, value):
        return _sane_date(value, 'Start date')

    def validate_ends_on(self, value):
        return _sane_date(value, 'End date') if value else value

    def validate(self, data):
        if bool(data.get('client')) == bool(data.get('new_company')):
            raise serializers.ValidationError('Choose an existing company or enter a new one.')
        if data.get('ends_on') and data['ends_on'] < data['starts_on']:
            raise serializers.ValidationError({'ends_on': 'End date cannot be before the start date.'})
        return data


# ─── Website registrations ───────────────────────────────────────────────────

class RegistrationCreateSerializer(serializers.Serializer):
    """Public sign-up form. `website` is a honeypot: real users never fill it."""
    plan = serializers.SlugField(max_length=40)
    billing_period = serializers.ChoiceField(choices=BILLING_PERIODS, default='monthly')
    employee_count = serializers.IntegerField(min_value=1, max_value=100000)
    company_name = serializers.CharField(max_length=200)
    company_code = serializers.CharField(max_length=20)
    contact_name = serializers.CharField(max_length=150)
    admin_email = serializers.EmailField()
    contact_phone = serializers.RegexField(r'^[0-9+\-\s()]{7,20}$', max_length=20,
                                           error_messages={'invalid': 'Enter a valid phone number.'})
    address = serializers.CharField(required=False, allow_blank=True, default='', max_length=500)
    gstin = serializers.CharField(required=False, allow_blank=True, default='', max_length=15)
    accept_terms = serializers.BooleanField()
    website = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_gstin(self, value):
        return ClientCreateSerializer().validate_gstin(value)

    def validate_company_name(self, value):
        return validators.business_name(value, 'Company name')

    def validate_contact_name(self, value):
        return validators.person_name(value)

    def validate_accept_terms(self, value):
        if not value:
            raise serializers.ValidationError('Please accept the terms to continue.')
        return value


class PaymentTransactionSerializer(serializers.Serializer):
    gateway = serializers.CharField()
    order_id = serializers.CharField()
    payment_id = serializers.CharField(allow_null=True)
    amount_minor = serializers.IntegerField()
    currency = serializers.CharField()
    status = serializers.CharField()
    failure_reason = serializers.CharField()
    created_at = serializers.DateTimeField()


class RegistrationSerializer(serializers.ModelSerializer):
    plan_code = serializers.CharField(source='plan.code', read_only=True)
    reviewed_by_name = serializers.CharField(source='reviewed_by.full_name', read_only=True, default=None)
    client_id = serializers.UUIDField(source='client.id', read_only=True, default=None)
    provisioning_status = serializers.CharField(source='client.provisioning_status', read_only=True, default=None)
    modules = serializers.SerializerMethodField()
    payments = PaymentTransactionSerializer(many=True, read_only=True)

    class Meta:
        model = CompanyRegistration
        fields = [
            'id', 'reference', 'company_name', 'company_code', 'contact_name', 'admin_email', 'contact_phone',
            'address', 'gstin', 'employee_count', 'plan', 'plan_code', 'plan_name', 'billing_period',
            'price_per_employee', 'months', 'subtotal', 'gst_rate', 'gst_inclusive', 'gst_amount', 'total',
            'currency', 'payment_status', 'paid_at', 'approval_status', 'rejection_reason', 'refund_status',
            'reviewed_by_name', 'reviewed_at', 'client_id', 'provisioning_status', 'modules', 'payments',
            'created_at',
        ]

    def get_modules(self, obj):
        return resolve_modules(obj.plan_features or [])


class NotificationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    kind = serializers.CharField()
    title = serializers.CharField()
    message = serializers.CharField()
    link = serializers.CharField()
    is_read = serializers.BooleanField()
    created_at = serializers.DateTimeField()

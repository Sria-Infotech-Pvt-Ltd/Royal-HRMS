from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.tenants.models import ALL_MODULES, Client, PlatformAdmin, PlatformAdminAuditLog, PlatformSMTPSettings


class PlatformAdminLoginSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class PlatformAdminForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value: str) -> str:
        # Same enumeration-safe pattern as accounts.ForgotPasswordSerializer —
        # never raise here for an unknown/inactive email, so the view's own
        # "same response either way" branch is what actually decides what
        # gets sent back, not field validation short-circuiting first.
        admin = PlatformAdmin.objects.filter(email__iexact=value, is_active=True).first()
        if admin:
            self.context['admin'] = admin
        return value


class PlatformAdminVerifyOtpSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp   = serializers.CharField(min_length=6, max_length=6)

    def validate_otp(self, value: str) -> str:
        if not value.isdigit():
            raise serializers.ValidationError('OTP must contain digits only.')
        return value


class PlatformAdminResetPasswordSerializer(serializers.Serializer):
    reset_token      = serializers.UUIDField()
    new_password     = serializers.CharField(min_length=8, max_length=128, write_only=True)
    confirm_password = serializers.CharField(min_length=8, max_length=128, write_only=True)

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs


class PlatformAdminChangePasswordSerializer(serializers.Serializer):
    old_password     = serializers.CharField(min_length=1, max_length=128, write_only=True)
    new_password     = serializers.CharField(min_length=8, max_length=128, write_only=True)
    confirm_password = serializers.CharField(min_length=8, max_length=128, write_only=True)

    def validate_new_password(self, value: str) -> str:
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def validate(self, attrs: dict) -> dict:
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError(
                {'new_password': 'New password must be different from the current password.'}
            )
        return attrs


class PlatformAdminAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PlatformAdmin
        fields = ['id', 'email', 'full_name', 'is_active', 'last_login', 'created_at']


class PlatformAdminInviteSerializer(serializers.Serializer):
    email     = serializers.EmailField()
    full_name = serializers.CharField(max_length=150)

    def validate_email(self, value: str) -> str:
        if PlatformAdmin.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A platform admin with this email already exists.')
        return value


class PlatformAdminAuditLogSerializer(serializers.ModelSerializer):
    admin_email          = serializers.SerializerMethodField(read_only=True)
    target_company_code  = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = PlatformAdminAuditLog
        fields = ['id', 'admin_email', 'action', 'target_company_code', 'changes', 'ip_address', 'created_at']

    def get_admin_email(self, obj: PlatformAdminAuditLog) -> str:
        return obj.admin.email if obj.admin else '(deleted admin)'

    def get_target_company_code(self, obj: PlatformAdminAuditLog) -> str:
        return obj.target_company.company_code if obj.target_company else ''


class ClientSerializer(serializers.ModelSerializer):
    has_pending_password = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = Client
        fields = [
            'id', 'company_code', 'company_name', 'enabled_modules',
            'is_active', 'provisioning_status',
            'has_pending_password', 'created_at', 'updated_at',
        ]

    def get_has_pending_password(self, obj: Client) -> bool:
        return bool(obj.pending_admin_password)


class ClientCreateSerializer(serializers.Serializer):
    company_code = serializers.CharField(max_length=50)
    company_name = serializers.CharField(max_length=200)
    admin_email  = serializers.EmailField()
    modules      = serializers.ListField(child=serializers.CharField(), required=False, allow_null=True, default=None)

    def validate_modules(self, value):
        if value is None:
            return None
        unknown = set(value) - set(ALL_MODULES)
        if unknown:
            raise serializers.ValidationError(f'Unknown module(s): {", ".join(sorted(unknown))}. Valid: {", ".join(ALL_MODULES)}')
        return value


class PlatformSMTPSettingsSerializer(serializers.ModelSerializer):
    is_configured = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = PlatformSMTPSettings
        fields = ['host', 'port', 'username', 'password', 'use_tls', 'from_email', 'sender_name', 'is_configured', 'updated_at']
        read_only_fields = ['is_configured', 'updated_at']
        extra_kwargs = {'password': {'write_only': True, 'required': False, 'allow_blank': True}}

    def get_is_configured(self, obj: PlatformSMTPSettings) -> bool:
        return obj.is_configured()

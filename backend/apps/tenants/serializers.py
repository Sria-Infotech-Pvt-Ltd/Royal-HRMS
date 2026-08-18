from rest_framework import serializers

from apps.tenants.models import ALL_MODULES, Client, PlatformSMTPSettings


class PlatformAdminLoginSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ClientSerializer(serializers.ModelSerializer):
    has_pending_password = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model  = Client
        fields = [
            'id', 'company_code', 'company_name', 'enabled_modules',
            'custom_domain', 'is_active', 'provisioning_status',
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

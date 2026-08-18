from rest_framework import serializers

from apps.tenants.models import ALL_MODULES, Client


class PlatformAdminLoginSerializer(serializers.Serializer):
    email    = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Client
        fields = ['id', 'company_code', 'company_name', 'enabled_modules', 'is_active', 'created_at', 'updated_at']


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

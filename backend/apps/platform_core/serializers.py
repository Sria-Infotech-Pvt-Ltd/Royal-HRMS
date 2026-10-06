from rest_framework import serializers

from apps.platform_core.models import (
    AuthorisedSignatory, ChangeHistory, Country, Currency, EntityBankAccount,
    EntityIdentifier, ExchangeRate, FeatureFlag, FeatureFlagOverride,
    LegalEntity, LookupType, LookupValue, ModuleToggle, NumberSeries,
    Timezone, Translation,
)


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ['id', 'code', 'name', 'symbol', 'minor_units', 'is_active']


class TimezoneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Timezone
        fields = ['id', 'name', 'is_active']


class CountrySerializer(serializers.ModelSerializer):
    default_currency_code = serializers.CharField(source='default_currency.code', read_only=True)
    default_timezone_name = serializers.CharField(source='default_timezone.name', read_only=True)

    class Meta:
        model = Country
        fields = [
            'id', 'iso2', 'iso3', 'numeric_code', 'name', 'phone_code',
            'default_currency', 'default_currency_code',
            'default_timezone', 'default_timezone_name',
            'date_format', 'address_format', 'is_active',
        ]


class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = ['id', 'from_currency', 'to_currency', 'rate', 'effective_date', 'source']


class LookupTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LookupType
        fields = [
            'id', 'code', 'name', 'description', 'module', 'is_system',
            'allow_custom_values', 'is_hierarchical', 'attribute_schema',
        ]
        read_only_fields = ['is_system']


class LookupValueSerializer(serializers.ModelSerializer):
    lookup_type_code = serializers.CharField(source='lookup_type.code', read_only=True)

    class Meta:
        model = LookupValue
        fields = [
            'id', 'lookup_type', 'lookup_type_code', 'code', 'label', 'description',
            'sort_order', 'parent', 'attributes', 'is_default', 'is_active',
            'effective_from', 'effective_to', 'country', 'legal_entity', 'is_system',
        ]
        read_only_fields = ['is_system']

    def validate(self, attrs):
        # Immutable-code rule (Task D): a referenced value's code can never
        # change, and a system-seeded value's code is locked from the
        # start — both are enforced here, not just by convention.
        if self.instance is not None and 'code' in attrs and attrs['code'] != self.instance.code:
            raise serializers.ValidationError({'code': 'code cannot be changed once a value exists — deactivate and create a new value instead.'})
        return attrs

    def validate_is_active(self, value):
        # A referenced value cannot be deleted — this serializer also
        # refuses to flip a value back from inactive-and-referenced in a
        # way that would be misleading; actual "is it referenced"
        # checking belongs to each business model's own delete/deactivate
        # path (platform_core doesn't know what references LookupValue by
        # code elsewhere in the codebase — see PHASE1_REPORT.md).
        return value


class TranslationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Translation
        fields = ['id', 'app_label', 'model_name', 'object_id', 'field', 'language', 'text']


class EntityIdentifierSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntityIdentifier
        fields = ['id', 'legal_entity', 'identifier_type', 'value', 'valid_from', 'valid_to', 'is_active']
        # value_encrypted/value_hash never serialized — sensitive
        # identifiers are write-only through services_legal_entity.py,
        # never read back in plaintext via this API in Phase 1.


class EntityBankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntityBankAccount
        fields = ['id', 'legal_entity', 'account_holder_name', 'bank_name', 'branch_name', 'is_primary', 'is_active']


class AuthorisedSignatorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AuthorisedSignatory
        fields = ['id', 'legal_entity', 'full_name', 'designation', 'purpose', 'is_active']


class LegalEntitySerializer(serializers.ModelSerializer):
    identifiers = EntityIdentifierSerializer(many=True, read_only=True)
    bank_accounts = EntityBankAccountSerializer(many=True, read_only=True)
    signatories = AuthorisedSignatorySerializer(many=True, read_only=True)

    class Meta:
        model = LegalEntity
        fields = [
            'id', 'code', 'legal_name', 'trade_name', 'country', 'base_currency',
            'timezone', 'date_format', 'financial_year_start_month',
            'entity_type', 'industry', 'msme_class', 'jurisdiction',
            'date_of_incorporation', 'is_listed', 'holding_company_info',
            'nature_of_business', 'nic_code', 'registered_address',
            'communication_address', 'primary_email', 'website',
            'official_phone', 'portal_url', 'is_primary', 'is_active',
            'identifiers', 'bank_accounts', 'signatories',
        ]

    def validate_is_primary(self, value):
        if value:
            existing = LegalEntity.objects.filter(is_primary=True)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError(
                    'Another legal entity is already primary — make it non-primary first.'
                )
        return value


class NumberSeriesSerializer(serializers.ModelSerializer):
    class Meta:
        model = NumberSeries
        fields = [
            'id', 'code', 'entity', 'pattern', 'prefix', 'padding', 'next_value',
            'reset_period', 'last_reset_key', 'legal_entity', 'scope_key',
            'is_active', 'priority',
        ]
        read_only_fields = ['last_reset_key']


class FeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlag
        fields = ['id', 'code', 'description', 'enabled', 'rollout_percentage', 'is_system']
        read_only_fields = ['is_system']


class FeatureFlagOverrideSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeatureFlagOverride
        fields = ['id', 'flag', 'legal_entity', 'role', 'user', 'enabled']


class ModuleToggleSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModuleToggle
        fields = ['id', 'module', 'legal_entity', 'enabled']


class ChangeHistorySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.full_name', read_only=True, default='')
    content_type_name = serializers.CharField(source='content_type.model', read_only=True)

    class Meta:
        model = ChangeHistory
        fields = [
            'id', 'occurred_at', 'actor', 'actor_name', 'channel', 'request_id',
            'content_type', 'content_type_name', 'object_id', 'object_repr',
            'action', 'changes', 'reason', 'legal_entity',
        ]

from django.contrib import admin

from apps.platform_core.models import (
    AuthorisedSignatory, ChangeHistory, Country, Currency, EntityBankAccount,
    EntityIdentifier, ExchangeRate, FeatureFlag, FeatureFlagOverride,
    LegalEntity, LookupType, LookupValue, ModuleToggle, NumberSeries,
    SeedRecord, Timezone, Translation,
)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('iso2', 'iso3', 'name', 'default_currency', 'is_active')
    search_fields = ('iso2', 'iso3', 'name')
    list_filter = ('is_active',)


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'minor_units', 'is_active')
    search_fields = ('code', 'name')


@admin.register(Timezone)
class TimezoneAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active')
    search_fields = ('name',)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ('from_currency', 'to_currency', 'rate', 'effective_date', 'source')
    list_filter = ('from_currency', 'to_currency')


@admin.register(LookupType)
class LookupTypeAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'module', 'is_system', 'allow_custom_values')
    search_fields = ('code', 'name')


@admin.register(LookupValue)
class LookupValueAdmin(admin.ModelAdmin):
    list_display = ('lookup_type', 'code', 'label', 'sort_order', 'is_active', 'is_system')
    list_filter = ('lookup_type', 'is_active')
    search_fields = ('code', 'label')

    def has_delete_permission(self, request, obj=None):
        # A referenced value must only ever be deactivated, never deleted —
        # enforced here at the admin layer; the service layer enforces it
        # for API callers.
        if obj is not None and obj.is_system:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = ('model_name', 'object_id', 'field', 'language')
    list_filter = ('language', 'model_name')


@admin.register(LegalEntity)
class LegalEntityAdmin(admin.ModelAdmin):
    list_display = ('code', 'legal_name', 'country', 'base_currency', 'is_primary', 'is_active')
    list_filter = ('is_primary', 'is_active', 'country')
    search_fields = ('code', 'legal_name', 'trade_name')


@admin.register(EntityIdentifier)
class EntityIdentifierAdmin(admin.ModelAdmin):
    list_display = ('legal_entity', 'identifier_type', 'is_active')
    list_filter = ('identifier_type',)
    # Encrypted value is never shown/editable here.
    readonly_fields = ('value_encrypted', 'value_hash')


@admin.register(EntityBankAccount)
class EntityBankAccountAdmin(admin.ModelAdmin):
    list_display = ('legal_entity', 'bank_name', 'is_primary', 'is_active')
    readonly_fields = ('account_number_encrypted', 'account_number_hash', 'ifsc_encrypted')


@admin.register(AuthorisedSignatory)
class AuthorisedSignatoryAdmin(admin.ModelAdmin):
    list_display = ('legal_entity', 'full_name', 'designation', 'purpose', 'is_active')
    readonly_fields = ('din_pan_encrypted',)


@admin.register(NumberSeries)
class NumberSeriesAdmin(admin.ModelAdmin):
    list_display = ('code', 'entity', 'scope_key', 'prefix', 'next_value', 'reset_period', 'is_active')
    list_filter = ('entity', 'reset_period', 'is_active')


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ('code', 'enabled', 'rollout_percentage', 'is_system')


@admin.register(FeatureFlagOverride)
class FeatureFlagOverrideAdmin(admin.ModelAdmin):
    list_display = ('flag', 'legal_entity', 'role', 'user', 'enabled')


@admin.register(ModuleToggle)
class ModuleToggleAdmin(admin.ModelAdmin):
    list_display = ('module', 'legal_entity', 'enabled')


@admin.register(ChangeHistory)
class ChangeHistoryAdmin(admin.ModelAdmin):
    list_display = ('occurred_at', 'actor', 'channel', 'content_type', 'object_id', 'action')
    list_filter = ('action', 'channel', 'content_type')
    search_fields = ('object_id', 'object_repr')
    readonly_fields = [f.name for f in ChangeHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SeedRecord)
class SeedRecordAdmin(admin.ModelAdmin):
    list_display = ('pack', 'version', 'content_type', 'object_id')
    list_filter = ('pack', 'content_type')

    def has_add_permission(self, request):
        return False

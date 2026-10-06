"""
Phase 1 Task J — admin APIs for every platform_core model. Follows this
codebase's existing convention (plain APIView + core/responses.py's
success()/error() envelope + core/pagination.py's paginate(), not DRF's
own ViewSet/PageNumberPagination) rather than introducing a second
pattern alongside the one already used everywhere else.

Permission: settings.view for reads, settings.edit for writes — the
EXISTING HasSettingsPermission class, per Phase 1's explicit instruction
not to add any new permission-granting migrations in this phase.
"""
from __future__ import annotations

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from core.pagination import paginate, paginated_data
from core.permissions import HasSettingsPermission
from core.responses import error, first_error, success

from apps.platform_core.models import (
    AuthorisedSignatory, ChangeHistory, Country, Currency, EntityBankAccount,
    EntityIdentifier, ExchangeRate, FeatureFlag, FeatureFlagOverride,
    LegalEntity, LookupType, LookupValue, ModuleToggle, NumberSeries,
    Timezone, Translation,
)
from apps.platform_core.serializers import (
    AuthorisedSignatorySerializer, ChangeHistorySerializer, CountrySerializer,
    CurrencySerializer, EntityBankAccountSerializer, EntityIdentifierSerializer,
    ExchangeRateSerializer, FeatureFlagOverrideSerializer, FeatureFlagSerializer,
    LegalEntitySerializer, LookupTypeSerializer, LookupValueSerializer,
    ModuleToggleSerializer, NumberSeriesSerializer, TimezoneSerializer,
    TranslationSerializer,
)


class _BaseListCreateView(APIView):
    """GET (paginated, optional ?search=) + POST. Subclasses set `model`,
    `serializer_class`, and optionally `search_fields`."""
    permission_classes = [HasSettingsPermission]
    model = None
    serializer_class = None
    search_fields: list[str] = []
    ordering = None

    def get_queryset(self, request):
        qs = self.model.objects.all()
        if self.ordering:
            qs = qs.order_by(*self.ordering)
        search = request.query_params.get('search')
        if search and self.search_fields:
            from django.db.models import Q
            q = Q()
            for field in self.search_fields:
                q |= Q(**{f'{field}__icontains': search})
            qs = qs.filter(q)
        return qs

    def get(self, request):
        qs = self.get_queryset(request)
        page_obj, paginator = paginate(qs, request)
        data = self.serializer_class(page_obj, many=True).data
        return success(f'{self.model._meta.verbose_name_plural.title()} retrieved.', paginated_data(paginator, page_obj, data))

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        obj = serializer.save()
        return success(f'{self.model._meta.verbose_name.title()} created.', self.serializer_class(obj).data, http_status=201)


class _BaseDetailView(APIView):
    permission_classes = [HasSettingsPermission]
    model = None
    serializer_class = None

    def get_object(self, pk):
        return self.model.objects.filter(pk=pk).first()

    def get(self, request, pk):
        obj = self.get_object(pk)
        if obj is None:
            return error('Not found.', http_status=404)
        return success('Retrieved.', self.serializer_class(obj).data)

    def patch(self, request, pk):
        obj = self.get_object(pk)
        if obj is None:
            return error('Not found.', http_status=404)
        serializer = self.serializer_class(obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        obj = serializer.save()
        return success('Updated.', self.serializer_class(obj).data)

    def delete(self, request, pk):
        obj = self.get_object(pk)
        if obj is None:
            return error('Not found.', http_status=404)
        if hasattr(obj, 'is_active'):
            obj.is_active = False
            obj.save(update_fields=['is_active'])
            return success('Deactivated.')
        obj.delete()
        return success('Deleted.')


# ─── Geography & currency ───────────────────────────────────────────────────

class CountryListCreateView(_BaseListCreateView):
    model = Country
    serializer_class = CountrySerializer
    search_fields = ['iso2', 'iso3', 'name']
    ordering = ['name']


class CountryDetailView(_BaseDetailView):
    model = Country
    serializer_class = CountrySerializer


class CurrencyListCreateView(_BaseListCreateView):
    model = Currency
    serializer_class = CurrencySerializer
    search_fields = ['code', 'name']
    ordering = ['code']


class CurrencyDetailView(_BaseDetailView):
    model = Currency
    serializer_class = CurrencySerializer


class TimezoneListView(_BaseListCreateView):
    model = Timezone
    serializer_class = TimezoneSerializer
    search_fields = ['name']
    ordering = ['name']


class ExchangeRateListCreateView(_BaseListCreateView):
    model = ExchangeRate
    serializer_class = ExchangeRateSerializer
    ordering = ['-effective_date']


class ExchangeRateDetailView(_BaseDetailView):
    model = ExchangeRate
    serializer_class = ExchangeRateSerializer


# ─── Lookup engine ──────────────────────────────────────────────────────────

class LookupTypeListCreateView(_BaseListCreateView):
    model = LookupType
    serializer_class = LookupTypeSerializer
    search_fields = ['code', 'name']
    ordering = ['code']


class LookupTypeDetailView(_BaseDetailView):
    model = LookupType
    serializer_class = LookupTypeSerializer

    def delete(self, request, pk):
        obj = self.get_object(pk)
        if obj is None:
            return error('Not found.', http_status=404)
        if obj.is_system:
            return error('This lookup type is system-defined and cannot be deleted.', http_status=403)
        obj.delete()
        return success('Deleted.')


class LookupValueListCreateView(_BaseListCreateView):
    model = LookupValue
    serializer_class = LookupValueSerializer
    search_fields = ['code', 'label']
    ordering = ['lookup_type', 'sort_order']

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        type_code = request.query_params.get('type')
        if type_code:
            qs = qs.filter(lookup_type__code=type_code)
        return qs


class LookupValueDetailView(_BaseDetailView):
    model = LookupValue
    serializer_class = LookupValueSerializer

    def delete(self, request, pk):
        # Values can only ever be deactivated, never deleted (Task D rule)
        # — this overrides the base class's "real delete if no is_active"
        # fallback, which doesn't apply here since LookupValue DOES have
        # is_active, so the base class's own behavior already deactivates.
        # Kept explicit for clarity rather than relying on that fallthrough.
        obj = self.get_object(pk)
        if obj is None:
            return error('Not found.', http_status=404)
        obj.is_active = False
        obj.save(update_fields=['is_active'])
        return success('Deactivated — historical records using this value are unaffected.')


class TranslationListCreateView(_BaseListCreateView):
    model = Translation
    serializer_class = TranslationSerializer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        for param, field in (('model_name', 'model_name'), ('object_id', 'object_id'), ('language', 'language')):
            value = request.query_params.get(param)
            if value:
                qs = qs.filter(**{field: value})
        return qs


# ─── Legal entities ─────────────────────────────────────────────────────────

class LegalEntityListCreateView(_BaseListCreateView):
    model = LegalEntity
    serializer_class = LegalEntitySerializer
    search_fields = ['code', 'legal_name', 'trade_name']
    ordering = ['code']


class LegalEntityDetailView(_BaseDetailView):
    model = LegalEntity
    serializer_class = LegalEntitySerializer


class EntityIdentifierListCreateView(_BaseListCreateView):
    model = EntityIdentifier
    serializer_class = EntityIdentifierSerializer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        entity_id = request.query_params.get('legal_entity')
        if entity_id:
            qs = qs.filter(legal_entity_id=entity_id)
        return qs


class EntityBankAccountListCreateView(_BaseListCreateView):
    model = EntityBankAccount
    serializer_class = EntityBankAccountSerializer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        entity_id = request.query_params.get('legal_entity')
        if entity_id:
            qs = qs.filter(legal_entity_id=entity_id)
        return qs


class AuthorisedSignatoryListCreateView(_BaseListCreateView):
    model = AuthorisedSignatory
    serializer_class = AuthorisedSignatorySerializer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        entity_id = request.query_params.get('legal_entity')
        if entity_id:
            qs = qs.filter(legal_entity_id=entity_id)
        return qs


# ─── Number series ──────────────────────────────────────────────────────────

class NumberSeriesListCreateView(_BaseListCreateView):
    model = NumberSeries
    serializer_class = NumberSeriesSerializer
    search_fields = ['code', 'entity', 'scope_key']
    ordering = ['entity', 'scope_key']


class NumberSeriesDetailView(_BaseDetailView):
    model = NumberSeries
    serializer_class = NumberSeriesSerializer


class NumberSeriesPreviewView(APIView):
    permission_classes = [HasSettingsPermission]

    def get(self, request, code):
        from apps.platform_core.services_numbering import preview
        try:
            value = preview(code)
        except NumberSeries.DoesNotExist:
            return error('No active number series with that code.', http_status=404)
        return success('Preview.', {'next_value': value})


# ─── Feature flags & module toggles ─────────────────────────────────────────

class FeatureFlagListCreateView(_BaseListCreateView):
    model = FeatureFlag
    serializer_class = FeatureFlagSerializer
    search_fields = ['code', 'description']
    ordering = ['code']


class FeatureFlagDetailView(_BaseDetailView):
    model = FeatureFlag
    serializer_class = FeatureFlagSerializer

    def delete(self, request, pk):
        obj = self.get_object(pk)
        if obj is None:
            return error('Not found.', http_status=404)
        if obj.is_system:
            return error('This flag is system-defined and cannot be deleted — disable it instead.', http_status=403)
        obj.delete()
        return success('Deleted.')


class FeatureFlagOverrideListCreateView(_BaseListCreateView):
    model = FeatureFlagOverride
    serializer_class = FeatureFlagOverrideSerializer

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        flag_code = request.query_params.get('flag')
        if flag_code:
            qs = qs.filter(flag__code=flag_code)
        return qs


class ModuleToggleListCreateView(_BaseListCreateView):
    model = ModuleToggle
    serializer_class = ModuleToggleSerializer
    ordering = ['module']


class ModuleToggleDetailView(_BaseDetailView):
    model = ModuleToggle
    serializer_class = ModuleToggleSerializer


# ─── Change history ─────────────────────────────────────────────────────────

class ChangeHistoryListView(APIView):
    """Read-only, append-only — no POST/PATCH/DELETE endpoint exists for
    this resource at all (matches the model's own enforcement)."""
    permission_classes = [HasSettingsPermission]

    def get(self, request):
        qs = ChangeHistory.objects.select_related('actor', 'content_type').all()
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        actor = request.query_params.get('actor')
        date_from = request.query_params.get('from')
        date_to = request.query_params.get('to')
        if content_type:
            qs = qs.filter(content_type__model=content_type)
        if object_id:
            qs = qs.filter(object_id=object_id)
        if actor:
            qs = qs.filter(actor_id=actor)
        if date_from:
            qs = qs.filter(occurred_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(occurred_at__date__lte=date_to)

        page_obj, paginator = paginate(qs, request)
        data = ChangeHistorySerializer(page_obj, many=True).data
        return success('Change history retrieved.', paginated_data(paginator, page_obj, data))

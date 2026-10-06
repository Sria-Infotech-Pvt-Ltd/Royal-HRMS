from django.urls import path

from apps.platform_core import views, views_meta

urlpatterns = [
    path('entities/', views_meta.EntityDefinitionListCreateView.as_view(), name='platform-entity-list'),
    path('entities/<int:pk>/', views_meta.EntityDefinitionDetailView.as_view(), name='platform-entity-detail'),
    path('entities/<int:pk>/publish/', views_meta.EntityDefinitionPublishView.as_view(), name='platform-entity-publish'),
    path('fields/', views_meta.FieldDefinitionListCreateView.as_view(), name='platform-field-list'),
    path('fields/<int:pk>/', views_meta.FieldDefinitionDetailView.as_view(), name='platform-field-detail'),
    path('form-layouts/', views_meta.FormLayoutListCreateView.as_view(), name='platform-form-layout-list'),
    path('form-layouts/<int:pk>/', views_meta.FormLayoutDetailView.as_view(), name='platform-form-layout-detail'),
    path('entities/<str:entity_code>/resolve-layout/', views_meta.ResolveLayoutView.as_view(), name='platform-resolve-layout'),

    path('custom/<str:entity_code>/records/', views_meta.CustomRecordListCreateView.as_view(), name='platform-custom-record-list'),
    path('custom/<str:entity_code>/records/<uuid:pk>/', views_meta.CustomRecordDetailView.as_view(), name='platform-custom-record-detail'),

    path('countries/', views.CountryListCreateView.as_view(), name='platform-country-list'),
    path('countries/<int:pk>/', views.CountryDetailView.as_view(), name='platform-country-detail'),
    path('currencies/', views.CurrencyListCreateView.as_view(), name='platform-currency-list'),
    path('currencies/<int:pk>/', views.CurrencyDetailView.as_view(), name='platform-currency-detail'),
    path('timezones/', views.TimezoneListView.as_view(), name='platform-timezone-list'),
    path('exchange-rates/', views.ExchangeRateListCreateView.as_view(), name='platform-exchange-rate-list'),
    path('exchange-rates/<int:pk>/', views.ExchangeRateDetailView.as_view(), name='platform-exchange-rate-detail'),

    path('lookup-types/', views.LookupTypeListCreateView.as_view(), name='platform-lookup-type-list'),
    path('lookup-types/<int:pk>/', views.LookupTypeDetailView.as_view(), name='platform-lookup-type-detail'),
    path('lookup-values/', views.LookupValueListCreateView.as_view(), name='platform-lookup-value-list'),
    path('lookup-values/<int:pk>/', views.LookupValueDetailView.as_view(), name='platform-lookup-value-detail'),
    path('translations/', views.TranslationListCreateView.as_view(), name='platform-translation-list'),

    path('legal-entities/', views.LegalEntityListCreateView.as_view(), name='platform-legal-entity-list'),
    path('legal-entities/<uuid:pk>/', views.LegalEntityDetailView.as_view(), name='platform-legal-entity-detail'),
    path('entity-identifiers/', views.EntityIdentifierListCreateView.as_view(), name='platform-entity-identifier-list'),
    path('entity-bank-accounts/', views.EntityBankAccountListCreateView.as_view(), name='platform-entity-bank-account-list'),
    path('entity-signatories/', views.AuthorisedSignatoryListCreateView.as_view(), name='platform-entity-signatory-list'),

    path('number-series/', views.NumberSeriesListCreateView.as_view(), name='platform-number-series-list'),
    path('number-series/<int:pk>/', views.NumberSeriesDetailView.as_view(), name='platform-number-series-detail'),
    path('number-series/<str:code>/preview/', views.NumberSeriesPreviewView.as_view(), name='platform-number-series-preview'),

    path('feature-flags/', views.FeatureFlagListCreateView.as_view(), name='platform-feature-flag-list'),
    path('feature-flags/<int:pk>/', views.FeatureFlagDetailView.as_view(), name='platform-feature-flag-detail'),
    path('feature-flag-overrides/', views.FeatureFlagOverrideListCreateView.as_view(), name='platform-feature-flag-override-list'),
    path('module-toggles/', views.ModuleToggleListCreateView.as_view(), name='platform-module-toggle-list'),
    path('module-toggles/<int:pk>/', views.ModuleToggleDetailView.as_view(), name='platform-module-toggle-detail'),

    path('history/', views.ChangeHistoryListView.as_view(), name='platform-change-history-list'),
]

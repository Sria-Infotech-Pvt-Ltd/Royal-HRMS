from django.urls import path

from apps.tenants.views import (
    CompanyDetailView,
    CompanyListCreateView,
    CompanyRevealPasswordView,
    PlatformAdminLoginView,
    PlatformAdminLogoutView,
    PlatformAdminMeView,
    PlatformAdminTokenRefreshView,
    PlatformSMTPSettingsView,
)

urlpatterns = [
    path('login/',         PlatformAdminLoginView.as_view(),        name='platform-admin-login'),
    path('logout/',        PlatformAdminLogoutView.as_view(),       name='platform-admin-logout'),
    path('token/refresh/', PlatformAdminTokenRefreshView.as_view(), name='platform-admin-token-refresh'),
    path('me/',            PlatformAdminMeView.as_view(),           name='platform-admin-me'),

    path('companies/',                       CompanyListCreateView.as_view(),    name='platform-admin-company-list'),
    path('companies/<uuid:pk>/',             CompanyDetailView.as_view(),        name='platform-admin-company-detail'),
    path('companies/<uuid:pk>/reveal-password/', CompanyRevealPasswordView.as_view(), name='platform-admin-company-reveal-password'),

    path('smtp-settings/', PlatformSMTPSettingsView.as_view(), name='platform-admin-smtp-settings'),
]

from django.urls import path

from apps.tenants.views import (
    CompanyDetailView,
    CompanyListCreateView,
    CompanyRevealPasswordView,
    PlatformAdminAccountDetailView,
    PlatformAdminAccountListCreateView,
    PlatformAdminAuditLogListView,
    PlatformAdminChangePasswordView,
    PlatformAdminDashboardStatsView,
    PlatformAdminForgotPasswordView,
    PlatformAdminLoginView,
    PlatformAdminLogoutView,
    PlatformAdminMeView,
    PlatformAdminResetPasswordView,
    PlatformAdminTokenRefreshView,
    PlatformAdminVerifyOtpView,
    PlatformSMTPSettingsView,
)

urlpatterns = [
    path('login/',           PlatformAdminLoginView.as_view(),          name='platform-admin-login'),
    path('logout/',          PlatformAdminLogoutView.as_view(),         name='platform-admin-logout'),
    path('token/refresh/',   PlatformAdminTokenRefreshView.as_view(),   name='platform-admin-token-refresh'),
    path('me/',              PlatformAdminMeView.as_view(),             name='platform-admin-me'),
    path('forgot-password/', PlatformAdminForgotPasswordView.as_view(), name='platform-admin-forgot-password'),
    path('verify-otp/',      PlatformAdminVerifyOtpView.as_view(),      name='platform-admin-verify-otp'),
    path('reset-password/',  PlatformAdminResetPasswordView.as_view(),  name='platform-admin-reset-password'),
    path('change-password/', PlatformAdminChangePasswordView.as_view(), name='platform-admin-change-password'),

    path('companies/',                       CompanyListCreateView.as_view(),    name='platform-admin-company-list'),
    path('companies/<uuid:pk>/',             CompanyDetailView.as_view(),        name='platform-admin-company-detail'),
    path('companies/<uuid:pk>/reveal-password/', CompanyRevealPasswordView.as_view(), name='platform-admin-company-reveal-password'),

    path('admins/',           PlatformAdminAccountListCreateView.as_view(), name='platform-admin-account-list'),
    path('admins/<uuid:pk>/', PlatformAdminAccountDetailView.as_view(),     name='platform-admin-account-detail'),

    path('audit-logs/',      PlatformAdminAuditLogListView.as_view(),   name='platform-admin-audit-log-list'),
    path('dashboard-stats/', PlatformAdminDashboardStatsView.as_view(), name='platform-admin-dashboard-stats'),

    path('smtp-settings/', PlatformSMTPSettingsView.as_view(), name='platform-admin-smtp-settings'),
]

from django.urls import path

from apps.tenants.views import (
    CompanyDetailView,
    CompanyListCreateView,
    PlatformAdminLoginView,
    PlatformAdminLogoutView,
    PlatformAdminMeView,
    PlatformAdminTokenRefreshView,
)

urlpatterns = [
    path('login/',         PlatformAdminLoginView.as_view(),        name='platform-admin-login'),
    path('logout/',        PlatformAdminLogoutView.as_view(),       name='platform-admin-logout'),
    path('token/refresh/', PlatformAdminTokenRefreshView.as_view(), name='platform-admin-token-refresh'),
    path('me/',            PlatformAdminMeView.as_view(),           name='platform-admin-me'),

    path('companies/',           CompanyListCreateView.as_view(), name='platform-admin-company-list'),
    path('companies/<uuid:pk>/', CompanyDetailView.as_view(),     name='platform-admin-company-detail'),
]

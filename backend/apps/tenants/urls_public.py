from django.urls import path

from apps.tenants.views_public import PublicPlansView, PublicRegistrationStatusView, PublicRegistrationView

urlpatterns = [
    path('plans/', PublicPlansView.as_view(), name='public-plans'),
    path('registrations/', PublicRegistrationView.as_view(), name='public-registration'),
    path('registrations/<str:reference>/', PublicRegistrationStatusView.as_view(), name='public-registration-status'),
]

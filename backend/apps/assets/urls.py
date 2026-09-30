from django.urls import path

from apps.assets.views import (
    AssetDetailView,
    AssetListCreateView,
    AssignAssetView,
    EmployeeAssetsView,
    ReturnAssetView,
)

urlpatterns = [
    path('', AssetListCreateView.as_view(), name='asset-list-create'),
    path('<uuid:pk>/', AssetDetailView.as_view(), name='asset-detail'),

    path('employees/<uuid:employee_id>/', EmployeeAssetsView.as_view(), name='employee-assets'),
    path('employees/<uuid:employee_id>/assign/', AssignAssetView.as_view(), name='asset-assign'),
    path('assignments/<uuid:assignment_id>/return/', ReturnAssetView.as_view(), name='asset-return'),
]

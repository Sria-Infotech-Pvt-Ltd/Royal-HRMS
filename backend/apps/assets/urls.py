from django.urls import path

from apps.assets.views import (
    AssetCategoryDetailView,
    AssetCategoryListCreateView,
    AssetDetailView,
    AssetListCreateView,
    AssetTypeDetailView,
    AssetTypeListCreateView,
    AssignAssetView,
    CompleteMaintenanceView,
    EmployeeAssetsView,
    ReturnAssetView,
    SendToMaintenanceView,
)

urlpatterns = [
    path('categories/', AssetCategoryListCreateView.as_view(), name='asset-category-list-create'),
    path('categories/<int:pk>/', AssetCategoryDetailView.as_view(), name='asset-category-detail'),
    path('types/', AssetTypeListCreateView.as_view(), name='asset-type-list-create'),
    path('types/<int:pk>/', AssetTypeDetailView.as_view(), name='asset-type-detail'),

    path('', AssetListCreateView.as_view(), name='asset-list-create'),
    path('<uuid:pk>/', AssetDetailView.as_view(), name='asset-detail'),
    path('<uuid:pk>/send-to-maintenance/', SendToMaintenanceView.as_view(), name='asset-send-to-maintenance'),
    path('maintenance/<uuid:pk>/complete/', CompleteMaintenanceView.as_view(), name='asset-maintenance-complete'),

    path('employees/<uuid:employee_id>/', EmployeeAssetsView.as_view(), name='employee-assets'),
    path('employees/<uuid:employee_id>/assign/', AssignAssetView.as_view(), name='asset-assign'),
    path('assignments/<uuid:assignment_id>/return/', ReturnAssetView.as_view(), name='asset-return'),
]

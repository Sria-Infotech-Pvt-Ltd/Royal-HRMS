from django.urls import path

from apps.branch.views import (
    BranchDetailView,
    BranchDistributionView,
    BranchGeofencingView,
    BranchListCreateView,
    BranchPreviewCodeView,
    BranchReassignAdminView,
    BranchStatsView,
    CityListView,
    StateListView,
)
from apps.branch.views_access import (
    EmployeeBranchAccessDetailView,
    EmployeeBranchAccessListCreateView,
)

urlpatterns = [
    # Cascading dropdowns
    path('states/', StateListView.as_view(), name='state-list'),
    path('states/<int:state_id>/cities/', CityListView.as_view(), name='city-list'),

    # Branch utilities (declared before <int:pk> for clarity; <int:pk> only matches integers anyway)
    path('branches/preview-code/', BranchPreviewCodeView.as_view(), name='branch-preview-code'),
    path('branches/stats/', BranchStatsView.as_view(), name='branch-stats'),
    path('branches/distribution/', BranchDistributionView.as_view(), name='branch-distribution'),

    # Branch CRUD (single base URL)
    path('branches/', BranchListCreateView.as_view(), name='branch-list-create'),
    path('branches/<int:pk>/',                BranchDetailView.as_view(),        name='branch-detail'),
    path('branches/<int:pk>/geofencing/',     BranchGeofencingView.as_view(),    name='branch-geofencing'),
    path('branches/<int:pk>/reassign-admin/', BranchReassignAdminView.as_view(), name='branch-reassign-admin'),

    # Multi-branch access management
    path('employee-access/',          EmployeeBranchAccessListCreateView.as_view(), name='employee-branch-access-list'),
    path('employee-access/<uuid:pk>/', EmployeeBranchAccessDetailView.as_view(),    name='employee-branch-access-detail'),
]
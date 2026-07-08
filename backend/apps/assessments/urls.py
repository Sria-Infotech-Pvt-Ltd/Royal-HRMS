from django.urls import path

from .views.admin import (
    AssessmentDetailView,
    AssessmentItemDetailView,
    AssessmentItemListCreateView,
    AssessmentListCreateView,
    AssignAssessmentView,
    CandidateResultsView,
)
from .views.portal import CompleteAssessmentView, MyAssessmentView, RespondToItemView, RetryAssessmentView
from .views.sections import AssessmentSectionDetailView, AssessmentSectionListCreateView
from .views.settings import AssessmentSettingsView

urlpatterns = [
    # HR — global settings
    path('settings/', AssessmentSettingsView.as_view(), name='assessment-settings'),

    # HR — assessment CRUD
    path('',                             AssessmentListCreateView.as_view(),     name='assessment-list'),
    path('<uuid:assessment_id>/',        AssessmentDetailView.as_view(),         name='assessment-detail'),
    path('<uuid:assessment_id>/items/',  AssessmentItemListCreateView.as_view(), name='assessment-item-list'),
    path('items/<uuid:item_id>/',        AssessmentItemDetailView.as_view(),     name='assessment-item-detail'),

    # HR — sections
    path('<uuid:assessment_id>/sections/',                  AssessmentSectionListCreateView.as_view(), name='assessment-section-list'),
    path('<uuid:assessment_id>/sections/<uuid:section_id>/', AssessmentSectionDetailView.as_view(),    name='assessment-section-detail'),

    # HR — assignment and results
    path('assign/',                                     AssignAssessmentView.as_view(),   name='assessment-assign'),
    path('candidates/<uuid:candidate_id>/results/',     CandidateResultsView.as_view(),   name='assessment-results'),

    # Candidate portal
    path('my/',                                                          MyAssessmentView.as_view(),      name='my-assessments'),
    path('<uuid:assignment_id>/respond/<uuid:item_id>/',                 RespondToItemView.as_view(),     name='assessment-respond'),
    path('<uuid:assignment_id>/complete/', CompleteAssessmentView.as_view(), name='assessment-complete'),
    path('<uuid:assignment_id>/retry/',   RetryAssessmentView.as_view(),    name='assessment-retry'),
] 
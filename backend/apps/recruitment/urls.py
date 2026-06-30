from django.urls import path

from .views import (
    CandidateDetailView,
    CandidateEmailLogView,
    CandidateHRDecisionView,
    CandidateListCreateView,
    CandidateReviewListView,
    CandidateStatsView,
    CandidateStatusChoicesView,
    CandidateStatusView,
    ResendPortalLoginView,
    SendPortalLoginView,
)

urlpatterns = [
    path('candidates/',                                   CandidateListCreateView.as_view(),      name='candidate-list-create'),
    path('candidates/stats/',                             CandidateStatsView.as_view(),           name='candidate-stats'),
    path('candidates/review/',                            CandidateReviewListView.as_view(),      name='candidate-review'),
    path('candidates/status-choices/',                    CandidateStatusChoicesView.as_view(),   name='candidate-status-choices'),
    path('candidates/<int:pk>/',                          CandidateDetailView.as_view(),          name='candidate-detail'),
    path('candidates/<int:pk>/status/',                   CandidateStatusView.as_view(),          name='candidate-status'),
    path('candidates/<int:pk>/hr-decision/',              CandidateHRDecisionView.as_view(),  name='candidate-hr-decision'),
    path('candidates/<int:pk>/send-portal-login/',        SendPortalLoginView.as_view(),      name='candidate-send-portal-login'),
    path('candidates/<int:pk>/resend-portal-login/',      ResendPortalLoginView.as_view(),    name='candidate-resend-portal-login'),
    path('emails/',                                       CandidateEmailLogView.as_view(),    name='candidate-email-logs'),
]

from django.urls import path

from .views import (
    CandidateBulkImportView,
    CandidateBulkImportSampleView,
    CandidateDetailView,
    CandidateEmailLogView,
    CandidateHRDecisionView,
    CandidateListCreateView,
    CandidateReviewListView,
    CandidateStatsView,
    CandidateStatusChoicesView,
    CandidateStatusView,
    ReferralAllView,
    ReferralBonusApproveView,
    ReferralBonusDetailView,
    ReferralBonusListView,
    ReferralBonusPayView,
    ReferralListCreateView,
    ReferralRuleDetailView,
    ReferralRuleListCreateView,
    ResendPortalLoginView,
    SendCandidateEmailView,
    SendPortalLoginView,
)

urlpatterns = [
    path('candidates/',                                   CandidateListCreateView.as_view(),      name='candidate-list-create'),
    path('candidates/bulk-import/',                       CandidateBulkImportView.as_view(),        name='candidate-bulk-import'),
    path('candidates/bulk-import/sample/',                CandidateBulkImportSampleView.as_view(),  name='candidate-bulk-import-sample'),
    path('candidates/review/',                            CandidateReviewListView.as_view(),      name='candidate-review'),
    path('candidates/stats/',                             CandidateStatsView.as_view(),           name='candidate-stats'),
    path('candidates/status-choices/',                    CandidateStatusChoicesView.as_view(),   name='candidate-status-choices'),
    path('candidates/<int:pk>/',                          CandidateDetailView.as_view(),          name='candidate-detail'),
    path('candidates/<int:pk>/status/',                   CandidateStatusView.as_view(),          name='candidate-status'),
    path('candidates/<int:pk>/hr-decision/',              CandidateHRDecisionView.as_view(),      name='candidate-hr-decision'),
    path('candidates/<str:pk>/send-email/',               SendCandidateEmailView.as_view(),       name='candidate-send-email'),
    path('candidates/<int:pk>/send-portal-login/',        SendPortalLoginView.as_view(),          name='candidate-send-portal-login'),
    path('candidates/<int:pk>/resend-portal-login/',      ResendPortalLoginView.as_view(),        name='candidate-resend-portal-login'),
    path('emails/',                                       CandidateEmailLogView.as_view(),        name='candidate-email-logs'),

    # Referrals
    path('referrals/',                                    ReferralListCreateView.as_view(),       name='referral-list-create'),
    path('referrals/all/',                                ReferralAllView.as_view(),              name='referral-all'),

    # Referral rules
    path('referral-rules/',                               ReferralRuleListCreateView.as_view(),   name='referral-rule-list-create'),
    path('referral-rules/<int:pk>/',                      ReferralRuleDetailView.as_view(),       name='referral-rule-detail'),

    # Referral bonuses
    path('referral-bonuses/',                             ReferralBonusListView.as_view(),        name='referral-bonus-list'),
    path('referral-bonuses/<int:pk>/',                    ReferralBonusDetailView.as_view(),      name='referral-bonus-detail'),
    path('referral-bonuses/<int:pk>/approve/',            ReferralBonusApproveView.as_view(),     name='referral-bonus-approve'),
    path('referral-bonuses/<int:pk>/pay/',                ReferralBonusPayView.as_view(),         name='referral-bonus-pay'),
]
 
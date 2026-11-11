from django.urls import path

from apps.approvals.views import (
    DelegationListCreateView, DelegationRevokeView, EligibleDelegatesView, EscalationHeadCandidatesView,
    EscalationLogView, EscalationSettingsView,
)

urlpatterns = [
    path('escalation-settings/', EscalationSettingsView.as_view(), name='approvals-escalation-settings'),
    path('escalation-settings/head-candidates/', EscalationHeadCandidatesView.as_view(),
         name='approvals-escalation-head-candidates'),
    path('escalations/', EscalationLogView.as_view(), name='approvals-escalations'),
    path('delegations/', DelegationListCreateView.as_view(), name='approvals-delegations'),
    path('delegations/eligible/', EligibleDelegatesView.as_view(), name='approvals-delegations-eligible'),
    path('delegations/<uuid:pk>/revoke/', DelegationRevokeView.as_view(), name='approvals-delegation-revoke'),
]

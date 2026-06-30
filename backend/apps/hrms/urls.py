from django.urls import path

from .views import (
    ExpenseApprovalView,
    ExpenseDetailView,
    ExpenseListCreateView,
    ExpenseStatsView,
    LeaveApprovalView,
    LeaveBalanceAdjustView,
    LeaveBalanceView,
    LeaveCalendarView,
    LeavePolicyView,
    LeaveRequestDetailView,
    LeaveRequestListCreateView,
    LeaveStatsView,
)

urlpatterns = [
    # Expenses
    path('expenses/',                                ExpenseListCreateView.as_view(), name='expense-list-create'),
    path('expenses/stats/',                          ExpenseStatsView.as_view(),      name='expense-stats'),
    path('expenses/<str:expense_id>/',               ExpenseDetailView.as_view(),     name='expense-detail'),
    path('expenses/<str:expense_id>/approve/',       ExpenseApprovalView.as_view(),   name='expense-approve'),

    # Leave — policy
    path('leave/policy/',                LeavePolicyView.as_view(),       name='leave-policy-list'),
    path('leave/policy/<str:leave_type>/', LeavePolicyView.as_view(),     name='leave-policy-detail'),

    # Leave — balance
    path('leave/balance/',              LeaveBalanceView.as_view(),       name='leave-balance'),
    path('leave/balance/credit/',       LeaveBalanceView.as_view(),       name='leave-balance-credit'),
    path('leave/balance/<str:balance_id>/', LeaveBalanceAdjustView.as_view(), name='leave-balance-adjust'),

    # Leave — requests
    path('leave/requests/',                          LeaveRequestListCreateView.as_view(), name='leave-request-list'),
    path('leave/requests/<str:request_id>/',         LeaveRequestDetailView.as_view(),     name='leave-request-detail'),
    path('leave/requests/<str:request_id>/approve/', LeaveApprovalView.as_view(),          name='leave-request-approve'),

    # Leave — stats & calendar
    path('leave/stats/',    LeaveStatsView.as_view(),    name='leave-stats'),
    path('leave/calendar/', LeaveCalendarView.as_view(), name='leave-calendar'),
]

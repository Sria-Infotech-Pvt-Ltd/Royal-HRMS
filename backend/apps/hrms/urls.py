from django.urls import path

from .views import (
    BirthdayView,
    CarryForwardHistoryView,
    CarryForwardPreviewView,
    CarryForwardRunView,
    CarryForwardYearsView,
    ExpenseCategoryListView,
    ExpenseDetailView,
    ExpenseListCreateView,
    ExpenseStatsView,
    ExpenseStatusListView,
    HolidayDetailView,
    HolidayListCreateView,
    LeaveApprovalView,
    LeaveBalanceAdjustView,
    LeaveBalanceView,
    LeaveCalendarView,
    LeaveOpeningBalanceImportView,
    LeaveOpeningBalanceSampleView,
    LeaveOpeningBalanceValidateView,
    LeavePolicyView,
    LeaveRequestDetailView,
    LeaveRequestListCreateView,
    LeaveStatsView,
)

urlpatterns = [
    # Birthdays
    path('birthdays/', BirthdayView.as_view(), name='birthday-list'),

    # Expenses
    path('expenses/',                                ExpenseListCreateView.as_view(),   name='expense-list-create'),
    path('expenses/categories/',                     ExpenseCategoryListView.as_view(), name='expense-categories'),
    path('expenses/status/',                       ExpenseStatusListView.as_view(),   name='expense-statuses'),
    path('expenses/stats/',                          ExpenseStatsView.as_view(),        name='expense-stats'),
    path('expenses/<int:expense_number>/',            ExpenseDetailView.as_view(),     name='expense-detail'),

    # Leave — policy
    path('leave/policy/',                LeavePolicyView.as_view(),       name='leave-policy-list'),
    path('leave/policy/<str:leave_type>/', LeavePolicyView.as_view(),     name='leave-policy-detail'),

    # Leave — balance (import paths must come before the <str:balance_id> catch-all)
    path('leave/balance/',                   LeaveBalanceView.as_view(),              name='leave-balance'),
    path('leave/balance/credit/',            LeaveBalanceView.as_view(),              name='leave-balance-credit'),
    path('leave/balance/import/',             LeaveOpeningBalanceImportView.as_view(),  name='leave-balance-import'),
    path('leave/balance/import/validate/',   LeaveOpeningBalanceValidateView.as_view(), name='leave-balance-import-validate'),
    path('leave/balance/import/sample/',     LeaveOpeningBalanceSampleView.as_view(),   name='leave-balance-import-sample'),
    path('leave/balance/<str:balance_id>/',  LeaveBalanceAdjustView.as_view(),        name='leave-balance-adjust'),

    # Leave — requests
    path('leave/requests/',                          LeaveRequestListCreateView.as_view(), name='leave-request-list'),
    path('leave/requests/<str:request_id>/',         LeaveRequestDetailView.as_view(),     name='leave-request-detail'),
    path('leave/requests/<str:request_id>/approve/', LeaveApprovalView.as_view(),          name='leave-request-approve'),

    # Leave — stats & calendar
    path('leave/stats/',    LeaveStatsView.as_view(),    name='leave-stats'),
    path('leave/calendar/', LeaveCalendarView.as_view(), name='leave-calendar'),

    # Leave — carry forward
    path('leave/carry-forward/years/',   CarryForwardYearsView.as_view(),   name='carry-forward-years'),
    path('leave/carry-forward/preview/', CarryForwardPreviewView.as_view(), name='carry-forward-preview'),
    path('leave/carry-forward/run/',     CarryForwardRunView.as_view(),     name='carry-forward-run'),
    path('leave/carry-forward/history/', CarryForwardHistoryView.as_view(), name='carry-forward-history'),

    # Holiday Calendar
    path('leave/holidays/',              HolidayListCreateView.as_view(), name='holiday-list'),
    path('leave/holidays/<str:holiday_id>/', HolidayDetailView.as_view(), name='holiday-detail'),
]

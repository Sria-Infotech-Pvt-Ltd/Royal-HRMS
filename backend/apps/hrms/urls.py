from django.urls import path

from .views import (
    BirthdaySettingsView,
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
    SeparationActivityListView,
    SeparationApprovalStageActionView,
    SeparationClearanceActionView,
    SeparationClearanceListView,
    SeparationDocumentDetailView,
    SeparationDocumentListCreateView,
    SeparationHandoverTaskDetailView,
    SeparationHandoverTaskListCreateView,
    SeparationReasonListView,
    SeparationRequestDetailView,
    SeparationRequestListCreateView,
    SeparationSettlementFinalizeView,
    SeparationSettlementView,
    SeparationTypeListView,
    WorkFromHomeApprovalView,
    WorkFromHomeRequestDetailView,
    WorkFromHomeRequestListCreateView,
    WFHSavedLocationDetailView,
    WFHSavedLocationListCreateView,
)

urlpatterns = [
    # Birthdays
    path('birthdays/',          BirthdayView.as_view(),         name='birthday-list'),
    path('birthdays/settings/', BirthdaySettingsView.as_view(), name='birthday-settings'),

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

    # Work From Home
    path('wfh/requests/',                          WorkFromHomeRequestListCreateView.as_view(), name='wfh-request-list'),
    path('wfh/requests/<str:request_id>/',         WorkFromHomeRequestDetailView.as_view(),     name='wfh-request-detail'),
    path('wfh/requests/<str:request_id>/approve/', WorkFromHomeApprovalView.as_view(),          name='wfh-request-approve'),
    path('wfh/saved-locations/',                   WFHSavedLocationListCreateView.as_view(),    name='wfh-saved-location-list-create'),
    path('wfh/saved-locations/<uuid:location_id>/', WFHSavedLocationDetailView.as_view(),        name='wfh-saved-location-detail'),

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

    # Separation — field choices
    path('separation/types/',   SeparationTypeListView.as_view(),   name='separation-type-list'),
    path('separation/reasons/', SeparationReasonListView.as_view(), name='separation-reason-list'),

    # Separation Requests
    path('separation/requests/',                  SeparationRequestListCreateView.as_view(), name='separation-request-list'),
    path('separation/requests/<str:request_id>/', SeparationRequestDetailView.as_view(),     name='separation-request-detail'),

    # Separation — approval stages
    path(
        'separation/requests/<str:request_id>/stages/<str:stage_id>/action/',
        SeparationApprovalStageActionView.as_view(), name='separation-stage-action',
    ),

    # Separation — KT / handover tasks
    path('separation/requests/<str:request_id>/tasks/',               SeparationHandoverTaskListCreateView.as_view(), name='separation-task-list'),
    path('separation/requests/<str:request_id>/tasks/<str:task_id>/', SeparationHandoverTaskDetailView.as_view(),     name='separation-task-detail'),

    # Separation — clearances
    path('separation/requests/<str:request_id>/clearances/',                            SeparationClearanceListView.as_view(),   name='separation-clearance-list'),
    path('separation/requests/<str:request_id>/clearances/<str:clearance_id>/action/',  SeparationClearanceActionView.as_view(), name='separation-clearance-action'),

    # Separation — settlement (Full & Final)
    path('separation/requests/<str:request_id>/settlement/',          SeparationSettlementView.as_view(),         name='separation-settlement'),
    path('separation/requests/<str:request_id>/settlement/finalize/', SeparationSettlementFinalizeView.as_view(), name='separation-settlement-finalize'),

    # Separation — documents
    path('separation/requests/<str:request_id>/documents/',                   SeparationDocumentListCreateView.as_view(), name='separation-document-list'),
    path('separation/requests/<str:request_id>/documents/<str:document_id>/', SeparationDocumentDetailView.as_view(),     name='separation-document-detail'),

    # Separation — activity log
    path('separation/requests/<str:request_id>/activities/', SeparationActivityListView.as_view(), name='separation-activity-list'),
]

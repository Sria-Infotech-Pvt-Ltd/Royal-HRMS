from django.urls import path
from apps.accounts.views import (
    ApprovalWorkflowRuleView,
    AuditLogListView,
    EmployeeApprovalMatrixView,
    EmployeeCodeSettingsView,
    EmployeeDetailView,
    EmployeeDocumentView,
    EmployeeReportingManagerView,
    HRListView,
    ManagerListView,
    MyProfileView,
    OnboardingView,
    OnboardingApprovalView,
    CompanyRetrieveUpdateView,
    DepartmentDetailView,
    DepartmentListCreateView,
    DesignationDetailView,
    DesignationListCreateView,
    DocumentDetailView,
    DocumentListCreateView,
    DocumentStatsView,
    EmployeeListCreateView,
    LoginView,
    LogoutView,
    TokenRefreshAPIView,
    ForgotPasswordView,
    VerifyOTPView,
    ResetPasswordView,
    ChangePasswordView,
    RoleListCreateView,
    RoleDetailView,
    PermissionListView,
    PermissionDetailView,
    SMTPSettingsListCreateView,
    SMTPSettingsDetailView,
    SMTPActivateView,
    SMTPTestEmailView,
    EmailTemplateCategoryListCreateView,
    EmailTemplateCategoryDetailView,
    EmailTemplateListCreateView,
    EmailTemplateDetailView,
    EmailTemplatePreviewView,
)

urlpatterns = [
    # Auth
    path('login/',           LoginView.as_view(),          name='login'),
    path('logout/',          LogoutView.as_view(),          name='logout'),
    path('token/refresh/',   TokenRefreshAPIView.as_view(), name='token-refresh'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot-password'),
    path('verify-otp/',      VerifyOTPView.as_view(),       name='verify-otp'),
    path('reset-password/',  ResetPasswordView.as_view(),   name='reset-password'),
    path('change-password/', ChangePasswordView.as_view(),  name='change-password'),

    # Employees
    path('employees/',                                           EmployeeListCreateView.as_view(),       name='employee-list-create'),
    path('employees/me/',                                        MyProfileView.as_view(),                name='my-profile'),
    path('employees/hrs/',                                       HRListView.as_view(),                   name='employee-hr-list'),
    path('employees/managers/',                                  ManagerListView.as_view(),              name='employee-manager-list'),
    path('employees/<str:employee_id>/reporting-manager/',       EmployeeReportingManagerView.as_view(), name='employee-reporting-manager'),
    path('employees/<str:employee_id>/approval-matrix/',         EmployeeApprovalMatrixView.as_view(),   name='employee-approval-matrix'),
    path('employees/<str:employee_id>/hr/',                      EmployeeDetailView.as_view(),           name='employee-hr-assign'),
    path('employees/<str:employee_id>/',                         EmployeeDetailView.as_view(),           name='employee-detail'),

    # Onboarding (self-service wizard — unified view)
    path('onboarding/',                              OnboardingView.as_view(),         name='onboarding'),
    path('onboarding/step/<int:step>/',              OnboardingView.as_view(),         name='onboarding-step'),
    path('onboarding/documents/',                    EmployeeDocumentView.as_view(),   name='onboarding-documents'),
    path('onboarding/documents/<str:doc_id>/',       EmployeeDocumentView.as_view(),   name='onboarding-document-detail'),
    path('onboarding/approvals/',                    OnboardingApprovalView.as_view(), name='onboarding-approvals'),
    path('onboarding/approvals/<str:user_id>/',      OnboardingApprovalView.as_view(), name='onboarding-approve'),

    # Organisation structure
    path('departments/',           DepartmentListCreateView.as_view(), name='department-list'),
    path('departments/<int:pk>/',  DepartmentDetailView.as_view(),     name='department-detail'),
    path('designations/',          DesignationListCreateView.as_view(), name='designation-list'),
    path('designations/<int:pk>/', DesignationDetailView.as_view(),     name='designation-detail'),

    # Roles
    path('roles/',         RoleListCreateView.as_view(), name='role-list-create'),
    path('roles/<int:pk>/', RoleDetailView.as_view(),    name='role-detail'),

    # Permissions
    path('permissions/',         PermissionListView.as_view(),   name='permission-list'),
    path('permissions/<int:pk>/', PermissionDetailView.as_view(), name='permission-detail'),

    # Company (singleton)
    path('settings/company/',          CompanyRetrieveUpdateView.as_view(),  name='company'),
    path('settings/employee-code/',    EmployeeCodeSettingsView.as_view(),   name='employee-code-settings'),
    path('settings/approval-rules/',   ApprovalWorkflowRuleView.as_view(),   name='approval-workflow-rules'),

    # Audit Log (read-only)
    path('settings/audit/', AuditLogListView.as_view(), name='audit-log-list'),

    # SMTP Settings — unlimited named configs, one active at a time
    path('settings/smtp/',                    SMTPSettingsListCreateView.as_view(), name='smtp-list'),
    path('settings/smtp/<int:pk>/',           SMTPSettingsDetailView.as_view(),     name='smtp-detail'),
    path('settings/smtp/<int:pk>/activate/',  SMTPActivateView.as_view(),           name='smtp-activate'),
    path('settings/smtp/test/',               SMTPTestEmailView.as_view(),          name='smtp-test'),

    # Email Template Categories (dynamic headings)
    path('settings/email-template-categories/',          EmailTemplateCategoryListCreateView.as_view(), name='email-template-category-list'),
    path('settings/email-template-categories/<int:pk>/', EmailTemplateCategoryDetailView.as_view(),     name='email-template-category-detail'),

    # Email Templates
    path('settings/email-templates/',              EmailTemplateListCreateView.as_view(), name='email-template-list'),
    path('settings/email-templates/<int:pk>/',     EmailTemplateDetailView.as_view(),     name='email-template-detail'),
    path('settings/email-templates/<int:pk>/preview/', EmailTemplatePreviewView.as_view(), name='email-template-preview'),

    # Document Center (admin)
    path('documents/',           DocumentListCreateView.as_view(), name='document-list-create'),
    path('documents/stats/',     DocumentStatsView.as_view(),      name='document-stats'),
    path('documents/<str:pk>/',  DocumentDetailView.as_view(),     name='document-detail'),
]

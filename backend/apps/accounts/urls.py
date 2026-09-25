from django.urls import path
from apps.accounts.views_email_log import (
    EmailLogDetailView,
    EmailLogListView,
    EmailLogResendView,
)
from apps.accounts.views_reset_password import EmployeePasswordResetView
from apps.accounts.views_hire import (
    HireActionDetailView,
    HireActionDocumentDetailView,
    HireActionDocumentListCreateView,
    HireActionListCreateView,
    HireActionPhotoView,
)
from apps.accounts.views_hire_complete import HireActionCompleteView
from apps.accounts.views_hire_scan import HireActionScanDocumentView
from apps.accounts.views_onboarding_hr import (
    HREmployeeCustomFieldFileValueView,
    HREmployeeOnboardingDocumentView,
    HREmployeeOnboardingSubmitView,
    HREmployeeOnboardingView,
)
from apps.accounts.views_education_experience import (
    EducationDetailView,
    EducationListView,
    ExperienceDetailView,
    ExperienceListView,
    HREmployeeEducationDetailView,
    HREmployeeEducationListView,
    HREmployeeExperienceDetailView,
    HREmployeeExperienceListView,
    HREmployeeTotalExperienceView,
    TotalExperienceView,
)
from apps.accounts.views_family_nomination import (
    FamilyMemberDetailView,
    FamilyMemberListView,
    HREmployeeFamilyMemberDetailView,
    HREmployeeFamilyMemberListView,
    HREmployeeNomineeDetailView,
    HREmployeeNomineeListView,
    NomineeDetailView,
    NomineeListView,
)
from apps.accounts.views_assets import (
    AssetDetailView,
    AssetListView,
    HREmployeeAssetDetailView,
    HREmployeeAssetListView,
)
from apps.accounts.views import (
    ApprovalWorkflowRuleView,
    AuditLogListView,
    CustomFieldFileValueView,
    DocumentTypeConfigPublicView,
    DocumentTypeConfigView,
    EmployeeApprovalMatrixView,
    EmployeeBulkImportView,
    EmployeeCodeSettingsView,
    EmployeeBankChangeReviewView,
    EmployeeCustomFieldFileValueView,
    EmployeeDetailView,
    EmployeeDocumentView,
    EmployeeProfileDocumentView,
    EmployeeConfirmView,
    EmployeeActionHistoryView,
    EmployeeAuditTrailView,
    EmployeePromotionHistoryView,
    EmployeeRevealSensitiveView,
    EmployeeReportingManagerView,
    HRListView,
    ManagerListView,
    MyEmploymentLetterPdfView,
    MyProfileView,
    EducationExperienceFieldConfigView,
    OnboardingFieldConfigPublicView,
    OnboardingFieldConfigView,
    OnboardingSectionDetailView,
    OnboardingSectionListCreateView,
    OnboardingSectionPublicView,
    OnboardingView,
    OnboardingApprovalView,
    CompanyDirectorDetailView,
    CompanyDirectorListCreateView,
    CompanyFinancialYearView,
    CompanyGSTRegistrationDetailView,
    CompanyGSTRegistrationListCreateView,
    CompanyRetrieveUpdateView,
    EmployeeBulkImportSampleView,
    DocumentDetailView,
    DocumentListCreateView,
    DocumentStatsView,
    EmployeeListCreateView,
    EmployeeStatsView,
    JobTemplateListCreateView,
    JobTemplateDetailView,
    LoginView,
    LogoutView,
    OrgOverviewView,
    OrgUnitDeactivateView,
    OrgUnitDetailView,
    OrgUnitListCreateView,
    PlacementDetailView,
    PositionActivateView,
    PositionDeactivateView,
    PositionDetailView,
    PositionListCreateView,
    PositionPlacementEndView,
    PositionPlacementListCreateView,
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
    ResolveTemplateVariablesView,
)
from apps.accounts.views_profile_photo import ProfilePhotoView
from apps.accounts.views_pincode import PincodeLookupView

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
    path('employees/stats/',                                     EmployeeStatsView.as_view(),             name='employee-stats'),
    path('employees/bulk-import/',                               EmployeeBulkImportView.as_view(),       name='employee-bulk-import'),
    path('employees/bulk-import/sample/',                        EmployeeBulkImportSampleView.as_view(), name='employee-bulk-import-sample'),
    path('employees/me/',                                        MyProfileView.as_view(),                name='my-profile'),
    path('employees/me/photo/',                                  ProfilePhotoView.as_view(),             name='my-profile-photo'),
    path('employees/me/employment-letter/',                      MyEmploymentLetterPdfView.as_view(),    name='my-employment-letter-pdf'),
    path('employees/hrs/',                                       HRListView.as_view(),                   name='employee-hr-list'),
    path('employees/managers/',                                  ManagerListView.as_view(),              name='employee-manager-list'),
    path('employees/<str:employee_id>/promotions/',               EmployeePromotionHistoryView.as_view(), name='employee-promotion-history'),
    path('employees/<str:employee_id>/action-history/',           EmployeeActionHistoryView.as_view(), name='employee-action-history'),
    path('employees/<str:employee_id>/audit-trail/',              EmployeeAuditTrailView.as_view(), name='employee-audit-trail'),
    path('employees/<str:employee_id>/reporting-manager/',       EmployeeReportingManagerView.as_view(), name='employee-reporting-manager'),
    path('employees/<str:employee_id>/approval-matrix/',         EmployeeApprovalMatrixView.as_view(),   name='employee-approval-matrix'),
    path('employees/<str:employee_id>/documents/',               EmployeeProfileDocumentView.as_view(),  name='employee-documents'),
    path('employees/<str:employee_id>/custom-file-fields/',      EmployeeCustomFieldFileValueView.as_view(), name='employee-custom-file-fields'),
    path('employees/<str:employee_id>/reveal-sensitive/',        EmployeeRevealSensitiveView.as_view(),  name='employee-reveal-sensitive'),
    path('employees/<str:employee_id>/confirm/',                  EmployeeConfirmView.as_view(),          name='employee-confirm'),
    path('employees/<str:employee_id>/bank-change/<str:decision>/', EmployeeBankChangeReviewView.as_view(), name='employee-bank-change-review'),
    path('employees/<str:employee_id>/hr/',                      EmployeeDetailView.as_view(),           name='employee-hr-assign'),
    path('employees/<uuid:pk>/reset-password/',                   EmployeePasswordResetView.as_view(),    name='employee-reset-password'),
    path('employees/<str:employee_id>/',                         EmployeeDetailView.as_view(),           name='employee-detail'),

    # Onboarding (self-service wizard — unified view)
    path('onboarding/',                              OnboardingView.as_view(),         name='onboarding'),
    path('onboarding/step/<int:step>/',              OnboardingView.as_view(),         name='onboarding-step'),
    path('onboarding/documents/',                    EmployeeDocumentView.as_view(),   name='onboarding-documents'),
    path('onboarding/documents/<str:doc_id>/',       EmployeeDocumentView.as_view(),   name='onboarding-document-detail'),
    path('onboarding/custom-file-fields/',              CustomFieldFileValueView.as_view(), name='onboarding-custom-file-fields'),
    path('onboarding/custom-file-fields/<str:value_id>/', CustomFieldFileValueView.as_view(), name='onboarding-custom-file-field-detail'),
    path('onboarding/approvals/',                    OnboardingApprovalView.as_view(), name='onboarding-approvals'),
    path('onboarding/approvals/<str:user_id>/',      OnboardingApprovalView.as_view(), name='onboarding-approve'),
    path('onboarding/field-config/',                 OnboardingFieldConfigPublicView.as_view(), name='onboarding-field-config'),
    path(
        'onboarding/education-experience-field-config/',
        EducationExperienceFieldConfigView.as_view(), name='education-experience-field-config',
    ),
    path(
        'onboarding/education-experience-field-config/<str:config_id>/',
        EducationExperienceFieldConfigView.as_view(), name='education-experience-field-config-detail',
    ),
    path('onboarding/sections/',                     OnboardingSectionPublicView.as_view(),     name='onboarding-sections-public'),
    path('onboarding/document-type-config/',         DocumentTypeConfigPublicView.as_view(), name='onboarding-document-type-config'),

    # Education and Work Experience — both genuinely unbounded add/remove
    # lists, bespoke steps not part of the generic OnboardingFieldConfig/
    # step-N system (see views_education_experience.py).
    path('onboarding/education/',                    EducationListView.as_view(),      name='onboarding-education'),
    path('onboarding/education/<str:pk>/',           EducationDetailView.as_view(),    name='onboarding-education-detail'),
    path('onboarding/experience/',                   ExperienceListView.as_view(),     name='onboarding-experience'),
    path('onboarding/experience/summary/',           TotalExperienceView.as_view(),    name='onboarding-experience-summary'),
    path('onboarding/experience/<str:pk>/',          ExperienceDetailView.as_view(),   name='onboarding-experience-detail'),

    # Family members, EPF nominees, and company assets — same bespoke-step
    # shape as Education/Experience above (see views_family_nomination.py /
    # views_assets.py).
    path('onboarding/family/',                       FamilyMemberListView.as_view(),   name='onboarding-family'),
    path('onboarding/family/<str:pk>/',              FamilyMemberDetailView.as_view(), name='onboarding-family-detail'),
    path('onboarding/nominees/',                     NomineeListView.as_view(),        name='onboarding-nominees'),
    path('onboarding/nominees/<str:pk>/',            NomineeDetailView.as_view(),      name='onboarding-nominees-detail'),
    path('onboarding/assets/',                       AssetListView.as_view(),          name='onboarding-assets'),
    path('onboarding/assets/<str:pk>/',              AssetDetailView.as_view(),        name='onboarding-assets-detail'),

    # PIN code -> District/State lookup, used by the address fields in step
    # 0 of both wizards (see views_pincode.py).
    path('onboarding/pincode-lookup/<str:pincode>/', PincodeLookupView.as_view(),      name='onboarding-pincode-lookup'),

    # Onboarding — HR/Admin completes the wizard on an employee's behalf
    # (onboarding.edit permission). user_id-keyed, not employee_id-keyed —
    # see views_onboarding_hr.py's module docstring for why.
    path('onboarding/employees/<str:user_id>/',                     HREmployeeOnboardingView.as_view(),           name='onboarding-employee-summary'),
    path('onboarding/employees/<str:user_id>/step/<int:step>/',     HREmployeeOnboardingView.as_view(),           name='onboarding-employee-step'),
    path('onboarding/employees/<str:user_id>/submit/',              HREmployeeOnboardingSubmitView.as_view(),     name='onboarding-employee-submit'),
    path('onboarding/employees/<str:user_id>/documents/',           HREmployeeOnboardingDocumentView.as_view(),   name='onboarding-employee-documents'),
    path('onboarding/employees/<str:user_id>/custom-file-fields/',  HREmployeeCustomFieldFileValueView.as_view(), name='onboarding-employee-custom-file-fields'),
    path('onboarding/employees/<str:user_id>/education/',            HREmployeeEducationListView.as_view(),        name='onboarding-employee-education'),
    path('onboarding/employees/<str:user_id>/education/<str:pk>/',   HREmployeeEducationDetailView.as_view(),      name='onboarding-employee-education-detail'),
    path('onboarding/employees/<str:user_id>/experience/',           HREmployeeExperienceListView.as_view(),       name='onboarding-employee-experience'),
    path('onboarding/employees/<str:user_id>/experience/summary/',   HREmployeeTotalExperienceView.as_view(),      name='onboarding-employee-experience-summary'),
    path('onboarding/employees/<str:user_id>/experience/<str:pk>/',  HREmployeeExperienceDetailView.as_view(),     name='onboarding-employee-experience-detail'),
    path('onboarding/employees/<str:user_id>/family/',               HREmployeeFamilyMemberListView.as_view(),     name='onboarding-employee-family'),
    path('onboarding/employees/<str:user_id>/family/<str:pk>/',      HREmployeeFamilyMemberDetailView.as_view(),   name='onboarding-employee-family-detail'),
    path('onboarding/employees/<str:user_id>/nominees/',             HREmployeeNomineeListView.as_view(),          name='onboarding-employee-nominees'),
    path('onboarding/employees/<str:user_id>/nominees/<str:pk>/',    HREmployeeNomineeDetailView.as_view(),        name='onboarding-employee-nominees-detail'),
    path('onboarding/employees/<str:user_id>/assets/',               HREmployeeAssetListView.as_view(),            name='onboarding-employee-assets'),
    path('onboarding/employees/<str:user_id>/assets/<str:pk>/',      HREmployeeAssetDetailView.as_view(),          name='onboarding-employee-assets-detail'),

    # Onboarding field configuration (HR settings screen)
    path('settings/onboarding-fields/',              OnboardingFieldConfigView.as_view(), name='onboarding-field-settings'),
    path('settings/onboarding-fields/<str:field_key>/', OnboardingFieldConfigView.as_view(), name='onboarding-field-settings-detail'),
    path('settings/onboarding-sections/',             OnboardingSectionListCreateView.as_view(), name='onboarding-section-settings'),
    path('settings/onboarding-sections/<uuid:pk>/',   OnboardingSectionDetailView.as_view(),     name='onboarding-section-settings-detail'),
    path('settings/document-types/',                 DocumentTypeConfigView.as_view(), name='document-type-settings'),
    path('settings/document-types/<str:type_key>/',  DocumentTypeConfigView.as_view(), name='document-type-settings-detail'),

    # Org Structure — the frontend /dashboard/org-chart page now calls these
    # instead of the old computed-from-User.department endpoint (removed)
    path('org-structure/overview/',                       OrgOverviewView.as_view(),              name='org-overview'),

    # Two-stage Hire flow
    path('hire-actions/',              HireActionListCreateView.as_view(), name='hire-action-list'),
    path('hire-actions/<uuid:pk>/',    HireActionDetailView.as_view(),     name='hire-action-detail'),
    path('hire-actions/<uuid:pk>/complete/', HireActionCompleteView.as_view(), name='hire-action-complete'),
    path('hire-actions/<uuid:pk>/scan-document/', HireActionScanDocumentView.as_view(), name='hire-action-scan-document'),
    path('hire-actions/<uuid:pk>/photo/',      HireActionPhotoView.as_view(),      name='hire-action-photo'),
    path('hire-actions/<uuid:pk>/documents/',  HireActionDocumentListCreateView.as_view(), name='hire-action-document-list'),
    path('hire-actions/<uuid:pk>/documents/<uuid:doc_id>/', HireActionDocumentDetailView.as_view(), name='hire-action-document-detail'),

    path('org-structure/units/',                          OrgUnitListCreateView.as_view(),        name='org-unit-list'),
    path('org-structure/units/<uuid:pk>/',                OrgUnitDetailView.as_view(),            name='org-unit-detail'),
    path('org-structure/units/<uuid:pk>/deactivate/',     OrgUnitDeactivateView.as_view(),        name='org-unit-deactivate'),
    path('org-structure/positions/',                      PositionListCreateView.as_view(),       name='position-list'),
    path('org-structure/positions/<uuid:pk>/',            PositionDetailView.as_view(),           name='position-detail'),
    path('org-structure/positions/<uuid:pk>/deactivate/', PositionDeactivateView.as_view(),       name='position-deactivate'),
    path('org-structure/positions/<uuid:pk>/activate/',   PositionActivateView.as_view(),         name='position-activate'),
    path('org-structure/positions/<uuid:pk>/placements/',     PositionPlacementListCreateView.as_view(), name='position-placement-list'),
    path('org-structure/positions/<uuid:pk>/placements/end/', PositionPlacementEndView.as_view(),      name='position-placement-end'),
    path('org-structure/placements/<uuid:pk>/',           PlacementDetailView.as_view(),          name='placement-detail'),
    path('org-structure/job-templates/',           JobTemplateListCreateView.as_view(), name='job-template-list'),
    path('org-structure/job-templates/<uuid:pk>/', JobTemplateDetailView.as_view(),     name='job-template-detail'),

    # Roles
    path('roles/',         RoleListCreateView.as_view(), name='role-list-create'),
    path('roles/<int:pk>/', RoleDetailView.as_view(),    name='role-detail'),

    # Permissions
    path('permissions/',         PermissionListView.as_view(),   name='permission-list'),
    path('permissions/<int:pk>/', PermissionDetailView.as_view(), name='permission-detail'),

    # Company (singleton)
    path('settings/company/',                     CompanyRetrieveUpdateView.as_view(),     name='company'),
    path('settings/company/financial-year/',      CompanyFinancialYearView.as_view(),      name='company-financial-year'),
    path('settings/company/gst-registrations/',           CompanyGSTRegistrationListCreateView.as_view(), name='company-gst-registration-list'),
    path('settings/company/gst-registrations/<uuid:pk>/', CompanyGSTRegistrationDetailView.as_view(),     name='company-gst-registration-detail'),
    path('settings/company/directors/',                   CompanyDirectorListCreateView.as_view(),        name='company-director-list'),
    path('settings/company/directors/<uuid:pk>/',          CompanyDirectorDetailView.as_view(),            name='company-director-detail'),
    path('settings/employee-code/',    EmployeeCodeSettingsView.as_view(),   name='employee-code-settings'),
    path('settings/approval-rules/',   ApprovalWorkflowRuleView.as_view(),   name='approval-workflow-rules'),

    # Audit Log (read-only)
    path('settings/audit/', AuditLogListView.as_view(), name='audit-log-list'),

    # Email Log (system-wide) — every send_template_email() attempt, with resend for failures
    path('settings/email-logs/',                  EmailLogListView.as_view(),   name='email-log-list'),
    path('settings/email-logs/<uuid:pk>/',         EmailLogDetailView.as_view(), name='email-log-detail'),
    path('settings/email-logs/<uuid:pk>/resend/',  EmailLogResendView.as_view(), name='email-log-resend'),

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
    path('settings/email-templates/resolve-context/',   ResolveTemplateVariablesView.as_view(), name='email-template-resolve-context'),

    # Document Center (admin)
    path('documents/',           DocumentListCreateView.as_view(), name='document-list-create'),
    path('documents/stats/',     DocumentStatsView.as_view(),      name='document-stats'),
    path('documents/<str:pk>/',  DocumentDetailView.as_view(),     name='document-detail'),
]

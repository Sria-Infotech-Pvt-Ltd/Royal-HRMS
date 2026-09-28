export const API = {
  auth: {
    login: "/login/",
    logout: "/logout/",
    forgotPassword: "/forgot-password/",
    verifyOtp: "/verify-otp/",
    resetPassword: "/reset-password/",
    changePassword: "/change-password/",
    inviteCheck: (token: string) => `/invite/${token}/`,
  },

  // No-auth-required — used by the pre-login screen to show the real
  // company name/logo instead of a hardcoded product brand string.
  companyPublicBranding: "/company/public-branding/",

  announcements: {
    list: "/announcements/",
    detail: (id: string | number) => `/announcements/${id}/`,
    view: (id: string | number) => `/announcements/${id}/view/`,
    react: (id: string | number) => `/announcements/${id}/react/`,
  },

  branches: {
    list: "/branch/branches/",
    stats: "/branch/branches/stats/",
    distribution: "/branch/branches/distribution/",
    previewCode: "/branch/branches/preview-code/",
    detail: (id: string | number) => `/branch/branches/${id}/`,
    states: "/branch/states/",
    cities: (stateId: string | number) => `/branch/states/${stateId}/cities/`,
  },

  orgStructure: {
    overview: "/org-structure/overview/",
    units: {
      list: "/org-structure/units/",
      detail: (id: string) => `/org-structure/units/${id}/`,
      deactivate: (id: string) => `/org-structure/units/${id}/deactivate/`,
    },
    positions: {
      list: "/org-structure/positions/",
      detail: (id: string) => `/org-structure/positions/${id}/`,
      deactivate: (id: string) => `/org-structure/positions/${id}/deactivate/`,
      activate: (id: string) => `/org-structure/positions/${id}/activate/`,
      placements: (id: string) => `/org-structure/positions/${id}/placements/`,
      placementsEnd: (id: string) => `/org-structure/positions/${id}/placements/end/`,
    },
    placements: {
      detail: (id: string) => `/org-structure/placements/${id}/`,
    },
    jobTemplates: {
      list: "/org-structure/job-templates/",
      detail: (id: string) => `/org-structure/job-templates/${id}/`,
    },
  },

  employees: {
    list: "/employees/",
    stats: "/employees/stats/",
    hrList: "/employees/hrs/",
    managerList: "/employees/managers/",
    me: "/employees/me/",
    myPhoto: "/employees/me/photo/",
    myEmploymentLetterPdf: "/employees/me/employment-letter/",
    detail: (id: string) => `/employees/${id}/`,
    promotions: (id: string) => `/employees/${id}/promotions/`,
    actionHistory: (id: string) => `/employees/${id}/action-history/`,
    auditTrail: (id: string) => `/employees/${id}/audit-trail/`,
    profile: (id: string) => `/employees/${id}/profile/`,
    reportingManager: (id: string) => `/employees/${id}/reporting-manager/`,
    hr: (id: string) => `/employees/${id}/hr/`,
    approvalMatrix: (id: string) => `/employees/${id}/approval-matrix/`,
    documents: (id: string) => `/employees/${id}/documents/`,
    customFileFields: (id: string) => `/employees/${id}/custom-file-fields/`,
    resetPassword: (id: string) => `/employees/${id}/reset-password/`,
    resendInvite: (id: string) => `/employees/${id}/resend-invite/`,
    inviteStatus: (id: string) => `/employees/${id}/invite-status/`,
    revealSensitive: (id: string) => `/employees/${id}/reveal-sensitive/`,
    confirm: (id: string) => `/employees/${id}/confirm/`,
    bankChangeReview: (id: string, decision: "approve" | "reject") => `/employees/${id}/bank-change/${decision}/`,
    branches:    "/branch/branches/",
    bulkImport:  "/employees/bulk-import/",
    bulkImportSample: "/employees/bulk-import/sample/",
  },

  hireActions: {
    list:         "/hire-actions/",
    detail:       (id: string) => `/hire-actions/${id}/`,
    complete:     (id: string) => `/hire-actions/${id}/complete/`,
    scanDocument: (id: string) => `/hire-actions/${id}/scan-document/`,
    photo:        (id: string) => `/hire-actions/${id}/photo/`,
    documents:       (id: string) => `/hire-actions/${id}/documents/`,
    documentDetail:  (id: string, docId: string) => `/hire-actions/${id}/documents/${docId}/`,
  },

  roles: {
    list: "/roles/",
    detail: (id: string | number) => `/roles/${id}/`,
  },

  permissions: {
    list: "/permissions/",
  },

  settings: {
    audit: "/settings/audit/",
    emailLogs: "/settings/email-logs/",
    emailLogDetail: (id: string) => `/settings/email-logs/${id}/`,
    emailLogResend: (id: string) => `/settings/email-logs/${id}/resend/`,
    company: "/settings/company/",
    financialYear: "/settings/company/financial-year/",
    employeeCode: "/settings/employee-code/",
    emailTemplates: "/settings/email-templates/",
    resolveTemplateContext: "/settings/email-templates/resolve-context/",
    approvalRules: "/settings/approval-rules/",
    assessmentConfig: "/assessments/settings/",
    onboardingFields: {
      list: "/settings/onboarding-fields/",
      detail: (fieldKey: string) => `/settings/onboarding-fields/${fieldKey}/`,
    },
    onboardingSections: {
      list: "/settings/onboarding-sections/",
      detail: (id: string) => `/settings/onboarding-sections/${id}/`,
    },
    documentTypes: {
      list: "/settings/document-types/",
      detail: (typeKey: string) => `/settings/document-types/${typeKey}/`,
    },
    gstRegistrations: {
      list: "/settings/company/gst-registrations/",
      detail: (id: string) => `/settings/company/gst-registrations/${id}/`,
    },
    directors: {
      list: "/settings/company/directors/",
      detail: (id: string) => `/settings/company/directors/${id}/`,
    },
  },

  hrms: {
    birthdays: "/birthdays/",
    birthdaySettings: "/birthdays/settings/",
  },

  referrals: {
    list: "/recruitment/referrals/",
    all: "/recruitment/referrals/all/",
    create: "/recruitment/referrals/",
  },

  referralRules: {
    list: "/recruitment/referral-rules/",
    create: "/recruitment/referral-rules/",
    detail: (id: number) => `/recruitment/referral-rules/${id}/`,
  },

  recruitment: {
    candidates: "/recruitment/candidates/",
    bulkImport: "/recruitment/candidates/bulk-import/",
    bulkImportSample: "/recruitment/candidates/bulk-import/sample/",
    stats: "/recruitment/candidates/stats/",
    review: "/recruitment/candidates/review/",
    detail: (id: number) => `/recruitment/candidates/${id}/`,
    status: "/recruitment/candidates/status-choices/",
    candidateStatus: (id: number) => `/recruitment/candidates/${id}/status/`,
    hrDecision: (id: number) => `/recruitment/candidates/${id}/hr-decision/`,
    sendPortalLogin: (id: number) => `/recruitment/candidates/${id}/send-portal-login/`,
    sendEmail: (id: number | string) => `/recruitment/candidates/${id}/send-email/`,
    // Superseded by API.settings.emailLogs (system-wide) — no longer used by
    // the Email Logs page, kept here in case anything else still reads it.
    emailLogs: "/recruitment/emails/",
  },

  onboarding: {
    profile: "/onboarding/",
    profileStep: (step: number) => `/onboarding/step/${step}/`,
    fieldConfig: "/onboarding/field-config/",
    educationExperienceFieldConfig: "/onboarding/education-experience-field-config/",
    educationExperienceFieldConfigDetail: (id: string) => `/onboarding/education-experience-field-config/${id}/`,
    sections: "/onboarding/sections/",
    documentTypeConfig: "/onboarding/document-type-config/",
    pincodeLookup: (pincode: string) => `/onboarding/pincode-lookup/${pincode}/`,
    documents: "/onboarding/documents/",
    documentDetail: (docId: string) => `/onboarding/documents/${docId}/`,
    customFileFields: "/onboarding/custom-file-fields/",
    customFileFieldDetail: (valueId: number | string) => `/onboarding/custom-file-fields/${valueId}/`,
    education: "/onboarding/education/",
    educationDetail: (id: string) => `/onboarding/education/${id}/`,
    experience: "/onboarding/experience/",
    experienceSummary: "/onboarding/experience/summary/",
    experienceDetail: (id: string) => `/onboarding/experience/${id}/`,
    family: "/onboarding/family/",
    familyDetail: (id: string) => `/onboarding/family/${id}/`,
    nominees: "/onboarding/nominees/",
    nomineeDetail: (id: string) => `/onboarding/nominees/${id}/`,
    assets: "/onboarding/assets/",
    assetDetail: (id: string) => `/onboarding/assets/${id}/`,
    submit: "/onboarding/",
    approvals: "/onboarding/approvals/",
    pipeline: "/onboarding/approvals/?view=pipeline",
    approve: (userId: string) => `/onboarding/approvals/${userId}/`,

    // HR/Admin completing an employee's onboarding on their behalf
    // (onboarding.edit permission) — user_id-keyed, mirrors `approve` above.
    employees: {
      summary: (userId: string) => `/onboarding/employees/${userId}/`,
      step: (userId: string, step: number) => `/onboarding/employees/${userId}/step/${step}/`,
      submit: (userId: string) => `/onboarding/employees/${userId}/submit/`,
      documents: (userId: string) => `/onboarding/employees/${userId}/documents/`,
      customFileFields: (userId: string) => `/onboarding/employees/${userId}/custom-file-fields/`,
      education: (userId: string) => `/onboarding/employees/${userId}/education/`,
      educationDetail: (userId: string, id: string) => `/onboarding/employees/${userId}/education/${id}/`,
      experience: (userId: string) => `/onboarding/employees/${userId}/experience/`,
      experienceSummary: (userId: string) => `/onboarding/employees/${userId}/experience/summary/`,
      experienceDetail: (userId: string, id: string) => `/onboarding/employees/${userId}/experience/${id}/`,
      family: (userId: string) => `/onboarding/employees/${userId}/family/`,
      familyDetail: (userId: string, id: string) => `/onboarding/employees/${userId}/family/${id}/`,
      nominees: (userId: string) => `/onboarding/employees/${userId}/nominees/`,
      nomineeDetail: (userId: string, id: string) => `/onboarding/employees/${userId}/nominees/${id}/`,
      assets: (userId: string) => `/onboarding/employees/${userId}/assets/`,
      assetDetail: (userId: string, id: string) => `/onboarding/employees/${userId}/assets/${id}/`,
    },
  },

  approvals: {
    leaveRequests: "/leave/requests/",
    approveLeave: (id: string) => `/leave/requests/${id}/approve/`,
    wfhRequests: "/wfh/requests/",
    approveWfh: (id: string) => `/wfh/requests/${id}/approve/`,
    expenseList: "/expenses/",
    approveExpense: (id: string) => `/expenses/${id}/approve/`,
  },

  hrHelp: {
    list: "/hr-help/requests/",
    detail: (id: string) => `/hr-help/requests/${id}/`,
  },

  // ESS "Documents" self-service submission list — deliberately separate
  // from the org-wide Document Center (see documents/_data.ts's own
  // DOCUMENTS_BASE, which stays untouched for that shared repository).
  myDocuments: {
    submissions: "/document-submissions/",
  },

  expenses: {
    list: "/expenses/",
    stats: "/expenses/stats/",
    categories: "/expenses/categories/",
    updateStatus: "/expenses/status/",
    detail: (id: string) => `/expenses/${id}/`,
    approve: (id: string) => `/expenses/${id}/approve/`,
  },

  performance: {
    cycles:            "/performance/cycles/",
    cycleDetail:       (id: string) => `/performance/cycles/${id}/`,
    myGoals:           "/performance/goals/me/",
    myGoalDetail:      (id: string) => `/performance/goals/me/${id}/`,
    myReview:          "/performance/reviews/me/",
    submitMyReview:    "/performance/reviews/me/submit/",
    teamReviews:       "/performance/reviews/team/",
    reviewDetail:      (id: string) => `/performance/reviews/${id}/`,
    submitManagerReview: (id: string) => `/performance/reviews/${id}/submit/`,
    calibrateReview:   (id: string) => `/performance/reviews/${id}/calibrate/`,
    publishReview:     (id: string) => `/performance/reviews/${id}/publish/`,
    acknowledgeReview: (id: string) => `/performance/reviews/${id}/acknowledge/`,
    hrQueue:           "/performance/reviews/hr-queue/",
    bannerSummary:     "/performance/banner-summary/",
  },

  separation: {
    list:            "/separation/requests/",
    detail:          (id: string) => `/separation/requests/${id}/`,
    stageAction:     (id: string, stageId: string) => `/separation/requests/${id}/stages/${stageId}/action/`,
    tasks:           (id: string) => `/separation/requests/${id}/tasks/`,
    taskDetail:      (id: string, taskId: string) => `/separation/requests/${id}/tasks/${taskId}/`,
    clearances:      (id: string) => `/separation/requests/${id}/clearances/`,
    clearanceAction: (id: string, clearanceId: string) => `/separation/requests/${id}/clearances/${clearanceId}/action/`,
    documents:       (id: string) => `/separation/requests/${id}/documents/`,
    documentDetail:  (id: string, documentId: string) => `/separation/requests/${id}/documents/${documentId}/`,
    activities:      (id: string) => `/separation/requests/${id}/activities/`,
    settlement:      (id: string) => `/separation/requests/${id}/settlement/`,
    settlementFinalize: (id: string) => `/separation/requests/${id}/settlement/finalize/`,
    types:           "/separation/types/",
    reasons:         "/separation/reasons/",
  },

  assessments: {
    // Candidate portal
    my: "/assessments/my/",
    respond: (assignmentId: string, itemId: string) => `/assessments/${assignmentId}/respond/${itemId}/`,
    complete: (assignmentId: string) => `/assessments/${assignmentId}/complete/`,
    retake: (assignmentId: string) => `/assessments/${assignmentId}/retry/`,
    // HR management
    list: "/assessments/",
    detail: (id: string) => `/assessments/${id}/`,
    items: (assessmentId: string) => `/assessments/${assessmentId}/items/`,
    itemDetail: (itemId: string) => `/assessments/items/${itemId}/`,
    sections: (assessmentId: string) => `/assessments/${assessmentId}/sections/`,
    sectionDetail: (assessmentId: string, sectionId: string) => `/assessments/${assessmentId}/sections/${sectionId}/`,
    assign: "/assessments/assign/",
    emailTemplateOptions: "/assessments/email-template-options/",
    results: (assessmentId: string) => `/assessments/${assessmentId}/results/`,
    candidateResults: (candidateId: string) => `/assessments/candidates/${candidateId}/results/`,
  },

  leave: {
    policy: "/leave/policy/",
    policyDetail: (leaveType: string) => `/leave/policy/${leaveType}/`,
    balance: "/leave/balance/",
    balanceCredit: "/leave/balance/credit/",
    balanceAdjust: (id: string) => `/leave/balance/${id}/`,
    balanceImportSample:   "/leave/balance/import/sample/", // + ?format=csv|xlsx
    balanceImport:         "/leave/balance/import/",
    balanceImportValidate: "/leave/balance/import/validate/",
    requests: "/leave/requests/",
    requestDetail: (id: string) => `/leave/requests/${id}/`,
    approve: (id: string) => `/leave/requests/${id}/approve/`,
    stats: "/leave/stats/",
    calendar: "/leave/calendar/",
    holidays: "/leave/holidays/",
    holidayDetail: (id: string) => `/leave/holidays/${id}/`,
    carryForward: {
      years:   "/leave/carry-forward/years/",
      preview: "/leave/carry-forward/preview/",
      run:     "/leave/carry-forward/run/",
      history: "/leave/carry-forward/history/",
    },
  },

  workFromHome: {
    requests:            "/wfh/requests/",
    requestDetail:       (id: string) => `/wfh/requests/${id}/`,
    approve:             (id: string) => `/wfh/requests/${id}/approve/`,
    savedLocations:      "/wfh/saved-locations/",
    savedLocationDetail: (id: string) => `/wfh/saved-locations/${id}/`,
  },

  attendance: {
    settings: "/attendance/settings/",
    punch: "/attendance/punch/",
    geofenceCheck: "/attendance/geofence-check/",
    today: "/attendance/today/",
    myShift: "/attendance/my-shift/",
    myWeeklyTimesheet: "/attendance/my-weekly-timesheet/",
    stats: "/attendance/stats/",
    summary: "/attendance/summary/",
    calendar: "/attendance/calendar/",
    correction: "/attendance/correction/",
    geofencing: (branchPk: number) => `/branch/branches/${branchPk}/geofencing/`,

    // HR Management
    dashboard: "/attendance/dashboard/",
    records: "/attendance/records/",
    recordCreate: "/attendance/records/create/",
    record: (id: string) => `/attendance/records/${id}/`,
    overtime: "/attendance/overtime/",
    overtimeCreate: "/attendance/overtime/create/",
    invalidPunches: "/attendance/invalid-punches/",
    invalidPunchAssign: (id: string) => `/attendance/invalid-punches/${id}/assign/`,
    invalidPunchDiscard: (id: string) => `/attendance/invalid-punches/${id}/discard/`,
    invalidPunchConvert: (id: string) => `/attendance/invalid-punches/${id}/convert/`,
    recordAudit: (id: string) => `/attendance/records/${id}/audit/`,
    unPunches: "/attendance/un-punches/",
    import: "/attendance/import/",
    importSample: "/attendance/import/sample/",
    export: "/attendance/export/",
    corrections: "/attendance/corrections/",
    correctionReview: (id: string) => `/attendance/corrections/${id}/review/`,
    myCorrections: "/attendance/corrections/my/",
    employeeCalendar: (employeeId: string, month: string) => `/attendance/employee-calendar/?employee_id=${employeeId}&month=${month}`,

    faceRegistration: {
      submit:  "/attendance/face-registration/",
      me:      "/attendance/face-registration/me/",
      pending: "/attendance/face-registration/pending/",
      review:  (id: string) => `/attendance/face-registration/${id}/review/`,

      // HR-initiated registration (register/update on someone's behalf, in person)
      register: "/attendance/face-registration/register/",
      employees: (search?: string) =>
        `/attendance/face-registration/employees/${search ? `?search=${encodeURIComponent(search)}` : ""}`,
      employeeStatus: (employeeUuid: string) => `/attendance/face-registration/employees/${employeeUuid}/status/`,
    },

    // Org-wide toggle (Attendance Settings -> Face ID Verification) — whether
    // face ID registration is mandatory and enforced at web clock-in/out.
    faceVerification: {
      status: "/attendance/face-verification/status/",
    },

    // Weekly Off Patterns (Settings) — existing backend CRUD, newly exposed to the frontend
    weeklyDayPolicies: "/attendance/weekly-days/",
    weeklyDayPolicy: (id: string) => `/attendance/weekly-days/${id}/`,

    // Working Hours Policies — doubles as "Shift" in the Hire wizard's Employment step
    workingHoursPolicies: "/attendance/working-hours/",
    workingHoursPolicy: (id: string) => `/attendance/working-hours/${id}/`,

    // Weekly Off Assignment (Attendance & Time tab)
    weeklyOffAssignments: "/attendance/weekly-off-assignments/",
    weeklyOffAssignmentsBulk: "/attendance/weekly-off-assignments/bulk/",
    weeklyOffAssignmentHistory: (employeeId: string) => `/attendance/weekly-off-assignments/${employeeId}/history/`,
  },

  voice: {
    parse: "/voice/parse/",
    transcribeFallback: "/voice/transcribe-fallback/",
    speak: "/voice/speak/",
  },

  notifications: {
    list: "/notifications/",
    unreadCount: "/notifications/unread-count/",
    markRead: (id: string) => `/notifications/${id}/read/`,
    markAllRead: "/notifications/read-all/",
    settings: "/notifications/settings/",
  },

  employeeDashboard: {
    kpis:              "/dashboard/employee/kpis/",
    leaveBalances:     "/dashboard/employee/leave-balances/",
    actionItems:       "/dashboard/employee/action-items/",
    recentRequests:    "/dashboard/employee/recent-requests/",
    attendanceSummary: "/dashboard/employee/attendance-summary/",
    attendanceStatus:  "/dashboard/employee/attendance-status/",
    announcement:      "/dashboard/announcement/",
    birthdaysToday:    "/dashboard/employee/birthdays/today/",
    myBirthdayWidgets: "/dashboard/birthdays/mine/",
  },

  payroll: {
    // Settings
    settings: "/payroll/settings/",
    salaryPreview: "/payroll/salary-preview/",

    // Salary structures
    structures: "/payroll/structures/",
    structure: (id: string) => `/payroll/structures/${id}/`,
    components: (structureId: string) => `/payroll/structures/${structureId}/components/`,
    component: (structureId: string, id: string) => `/payroll/structures/${structureId}/components/${id}/`,

    // Statutory config (per state)
    statutory: "/payroll/statutory/",
    statutoryDetail: (id: string) => `/payroll/statutory/${id}/`,
    statutoryByState: (stateId: string) => `/payroll/statutory/by-state/${stateId}/`,

    // Branch payroll config
    branchConfig: "/payroll/branch-config/",
    branchConfigDetail: (id: string) => `/payroll/branch-config/${id}/`,
    branchConfigByBranch: (branchId: string) => `/payroll/branch-config/by-branch/${branchId}/`,

    // Employee salary config (CTC)
    employeeSalary: "/payroll/employee-salary/",
    employeeSalaryDetail: (id: string) => `/payroll/employee-salary/${id}/`,
    employeeSalaryHistory: (employeeId: string) => `/payroll/employee-salary/history/${employeeId}/`,
    employeePayslipHistory: (employeeId: string) => `/payroll/employees/${employeeId}/payslips/`,

    // Payroll cycles
    cycles: "/payroll/cycles/",
    cycle: (id: string) => `/payroll/cycles/${id}/`,
    approveAttendance:   (id: string) => `/payroll/cycles/${id}/approve-attendance/`,
    managerApprovals:    (id: string) => `/payroll/cycles/${id}/manager-approvals/`,
    pendingApprovalCycles: "/payroll/cycles/pending-approval/",
    attendanceSummary:   (id: string) => `/payroll/cycles/${id}/attendance-summary/`,
    employeeDailyAttendance: (cycleId: string, employeeId: string) => `/payroll/cycles/${cycleId}/attendance-daily/${employeeId}/`,
    processCycle: (id: string) => `/payroll/cycles/${id}/process/`,
    eligibleEmployees: (id: string) => `/payroll/cycles/${id}/eligible-employees/`,
    markPaid: (id: string) => `/payroll/cycles/${id}/mark-paid/`,
    cancelCycle: (id: string) => `/payroll/cycles/${id}/cancel/`,
    cycleEcr:     (id: string) => `/payroll/cycles/${id}/ecr/`,
    cycleEcrPdf:  (id: string) => `/payroll/cycles/${id}/ecr/pdf/`,
    cycleEcrText: (id: string) => `/payroll/cycles/${id}/ecr-text/`,
    cycleEsic:    (id: string) => `/payroll/cycles/${id}/esic/`,

    // Payslips (HR)
    cyclePayslips: (cycleId: string) => `/payroll/cycles/${cycleId}/payslips/`,
    dispatchPayslips: (cycleId: string) => `/payroll/cycles/${cycleId}/payslips/dispatch/`,
    expenseSummary: (cycleId: string) => `/payroll/cycles/${cycleId}/expense-summary/`,
    referralBonusSummary: (cycleId: string) => `/payroll/cycles/${cycleId}/referral-bonus-summary/`,
    payslip: (id: string) => `/payroll/payslips/${id}/`,
    payslipReimbBonus: (id: string) => `/payroll/payslips/${id}/reimb-bonus/`,

    // Employee self-service
    myPayslips: "/payroll/my-payslips/",
    acknowledgePayslip: (id: string) => `/payroll/my-payslips/${id}/acknowledge/`,
    logPayslipDownload: (id: string) => `/payroll/my-payslips/${id}/log-download/`,
    payslipPdf: (id: string) => `/payroll/my-payslips/${id}/pdf/`,

    // Tax declarations
    taxDeclarations: "/payroll/tax-declarations/",
    myTaxDeclaration: "/payroll/tax-declarations/me/",
    submitTaxDeclaration: "/payroll/tax-declarations/me/submit/",
    approveTaxDeclaration: (id: string) => `/payroll/tax-declarations/${id}/approve/`,

    // Queries
    queries: "/payroll/queries/",
    resolveQuery: (id: string) => `/payroll/queries/${id}/resolve/`,

    // Adjustments
    adjustments: "/payroll/adjustments/",
    adjustmentDetail: (id: string) => `/payroll/adjustments/${id}/`,
    adjustmentsBulkImport: "/payroll/adjustments/bulk-import/",

    // Branch payroll status overview (admin only)
    branchStatus: "/payroll/branch-status/",
  },

  dashboard: {
    // System Admin
    kpis:                "/dashboard/system-admin/kpis/",
    announcement:        "/dashboard/system-admin/announcement/",
    pendingApprovals:    "/dashboard/system-admin/pending-approvals/",
    departmentHeadcount: "/dashboard/system-admin/department-headcount/",
    employeeLifecycle:   "/dashboard/system-admin/employee-lifecycle/",
    birthdaysToday:      "/dashboard/system-admin/birthdays/today/",
    birthdaysUpcoming:   "/dashboard/system-admin/birthdays/upcoming/",
    auditLogs:           "/dashboard/system-admin/audit-logs/",
    // HR
    hrKpis:                "/dashboard/hr/kpis/",
    hrActionQueue:         "/dashboard/hr/action-queue/",
    hrRecruitmentFunnel:   "/dashboard/hr/recruitment-funnel/",
    hrAttendanceSummary:   "/dashboard/hr/attendance-summary/",
    overview:              "/dashboard/hr/overview/",
    lifecycleRegister:     "/dashboard/hr/lifecycle-register/",
    attendanceOverview:    "/dashboard/module/attendance-overview/",
    leaveOverview:         "/dashboard/module/leave-overview/",
    payrollOverview:       "/dashboard/module/payroll-overview/",
    performanceOverview:   "/dashboard/module/performance-overview/",
    reportsOverview:       "/dashboard/module/reports-overview/",
    settingsOverview:      "/dashboard/module/settings-overview/",
    hrDepartmentHeadcount: "/dashboard/department-headcount/",
    hrEmployeeLifecycle:   "/dashboard/hr/employee-lifecycle/",
    hrBirthdaysToday:      "/dashboard/hr/birthdays/today/",
    hrBirthdaysUpcoming:   "/dashboard/hr/birthdays/upcoming/",
    // Manager / Team Lead dashboard
    manager:               "/dashboard/manager/",
  },
} as const;

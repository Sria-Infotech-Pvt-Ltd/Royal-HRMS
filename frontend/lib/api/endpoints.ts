export const API = {
  auth: {
    login: "/login/",
    logout: "/logout/",
    forgotPassword: "/forgot-password/",
    verifyOtp: "/verify-otp/",
    resetPassword: "/reset-password/",
    changePassword: "/change-password/",
  },

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

  departments: {
    list: "/departments/",
    detail: (id: string | number) => `/departments/${id}/`,
  },

  designations: {
    list: "/designations/",
    detail: (id: string | number) => `/designations/${id}/`,
  },

  employees: {
    list: "/employees/",
    stats: "/employees/stats/",
    hrList: "/employees/hrs/",
    managerList: "/employees/managers/",
    me: "/employees/me/",
    myPhoto: "/employees/me/photo/",
    detail: (id: string) => `/employees/${id}/`,
    profile: (id: string) => `/employees/${id}/profile/`,
    reportingManager: (id: string) => `/employees/${id}/reporting-manager/`,
    hr: (id: string) => `/employees/${id}/hr/`,
    approvalMatrix: (id: string) => `/employees/${id}/approval-matrix/`,
    documents: (id: string) => `/employees/${id}/documents/`,
    branches:    "/branch/branches/",
    bulkImport:  "/employees/bulk-import/",
    bulkImportSample: "/employees/bulk-import/sample/",
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
    company: "/settings/company/",
    financialYear: "/settings/company/financial-year/",
    employeeCode: "/settings/employee-code/",
    emailTemplates: "/settings/email-templates/",
    resolveTemplateContext: "/settings/email-templates/resolve-context/",
    approvalRules: "/settings/approval-rules/",
    assessmentConfig: "/assessments/settings/",
  },

  hrms: {
    birthdays: "/birthdays/",
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
    emailLogs: "/recruitment/emails/",
  },

  onboarding: {
    profile: "/onboarding/",
    profileStep: (step: number) => `/onboarding/step/${step}/`,
    documents: "/onboarding/documents/",
    documentDetail: (docId: string) => `/onboarding/documents/${docId}/`,
    submit: "/onboarding/",
    approvals: "/onboarding/approvals/",
    pipeline: "/onboarding/approvals/?view=pipeline",
    approve: (userId: string) => `/onboarding/approvals/${userId}/`,
  },

  approvals: {
    leaveRequests: "/leave/requests/",
    approveLeave: (id: string) => `/leave/requests/${id}/approve/`,
    expenseList: "/expenses/",
    approveExpense: (id: string) => `/expenses/${id}/approve/`,
  },

  expenses: {
    list: "/expenses/",
    stats: "/expenses/stats/",
    categories: "/expenses/categories/",
    updateStatus: "/expenses/status/",
    detail: (id: string) => `/expenses/${id}/`,
    approve: (id: string) => `/expenses/${id}/approve/`,
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

  attendance: {
    settings: "/attendance/settings/",
    punch: "/attendance/punch/",
    today: "/attendance/today/",
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

    // Weekly Off Assignment (Attendance & Time tab)
    weeklyOffAssignments: "/attendance/weekly-off-assignments/",
    weeklyOffAssignmentsBulk: "/attendance/weekly-off-assignments/bulk/",
    weeklyOffAssignmentHistory: (employeeId: string) => `/attendance/weekly-off-assignments/${employeeId}/history/`,
  },

  voice: {
    parse: "/voice/parse/",
  },

  notifications: {
    list: "/notifications/",
    unreadCount: "/notifications/unread-count/",
    markRead: (id: string) => `/notifications/${id}/read/`,
    markAllRead: "/notifications/read-all/",
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
  },

  payroll: {
    // Settings
    settings: "/payroll/settings/",

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

    // Payroll cycles
    cycles: "/payroll/cycles/",
    cycle: (id: string) => `/payroll/cycles/${id}/`,
    approveAttendance:   (id: string) => `/payroll/cycles/${id}/approve-attendance/`,
    managerApprovals:    (id: string) => `/payroll/cycles/${id}/manager-approvals/`,
    pendingApprovalCycles: "/payroll/cycles/pending-approval/",
    attendanceSummary:   (id: string) => `/payroll/cycles/${id}/attendance-summary/`,
    employeeDailyAttendance: (cycleId: string, employeeId: string) => `/payroll/cycles/${cycleId}/attendance-daily/${employeeId}/`,
    processCycle: (id: string) => `/payroll/cycles/${id}/process/`,
    markPaid: (id: string) => `/payroll/cycles/${id}/mark-paid/`,
    cancelCycle: (id: string) => `/payroll/cycles/${id}/cancel/`,
    cycleEcr:    (id: string) => `/payroll/cycles/${id}/ecr/`,
    cycleEcrPdf: (id: string) => `/payroll/cycles/${id}/ecr/pdf/`,

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
    hrDepartmentHeadcount: "/dashboard/department-headcount/",
    hrEmployeeLifecycle:   "/dashboard/hr/employee-lifecycle/",
    hrBirthdaysToday:      "/dashboard/hr/birthdays/today/",
    hrBirthdaysUpcoming:   "/dashboard/hr/birthdays/upcoming/",
    // Manager / Team Lead dashboard
    manager:               "/dashboard/manager/",
  },
} as const;

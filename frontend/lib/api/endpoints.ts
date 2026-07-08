export const API = {
  auth: {
    login:          "/login/",
    logout:         "/logout/",
    forgotPassword: "/forgot-password/",
    verifyOtp:      "/verify-otp/",
    resetPassword:  "/reset-password/",
    changePassword: "/change-password/",
  },

  announcements: {
    list:   "/announcements/",
    detail: (id: string | number) => `/announcements/${id}/`,
    view:   (id: string | number) => `/announcements/${id}/view/`,
    react:  (id: string | number) => `/announcements/${id}/react/`,
  },

  branches: {
    list:         "/branch/branches/",
    stats:        "/branch/branches/stats/",
    distribution: "/branch/branches/distribution/",
    previewCode:  "/branch/branches/preview-code/",
    detail:       (id: string | number) => `/branch/branches/${id}/`,
    states:       "/branch/states/",
    cities:       (stateId: string | number) => `/branch/states/${stateId}/cities/`,
  },

  departments: {
    list:   "/departments/",
    detail: (id: string | number) => `/departments/${id}/`,
  },

  designations: {
    list:   "/designations/",
    detail: (id: string | number) => `/designations/${id}/`,
  },

  employees: {
    list:              "/employees/",
    hrList:            "/employees/hrs/",
    managerList:       "/employees/managers/",
    me:                "/employees/me/",
    detail:            (id: string) => `/employees/${id}/`,
    profile:           (id: string) => `/employees/${id}/profile/`,
    reportingManager:  (id: string) => `/employees/${id}/reporting-manager/`,
    hr:                (id: string) => `/employees/${id}/hr/`,
    approvalMatrix:    (id: string) => `/employees/${id}/approval-matrix/`,
    branches:          "/branch/branches/",
  },

  roles: {
    list:   "/roles/",
    detail: (id: string | number) => `/roles/${id}/`,
  },

  permissions: {
    list: "/permissions/",
  },

  settings: {
    audit:          "/settings/audit/",
    company:        "/settings/company/",
    employeeCode:   "/settings/employee-code/",
    emailTemplates: "/settings/email-templates/",
    approvalRules:  "/settings/approval-rules/",
  },

  recruitment: {
    candidates:      "/recruitment/candidates/",
    stats:           "/recruitment/candidates/stats/",
    review:          "/recruitment/candidates/review/",
    detail:          (id: number) => `/recruitment/candidates/${id}/`,
    status:          "/recruitment/candidates/status-choices/",
    candidateStatus: (id: number) => `/recruitment/candidates/${id}/status/`,
    hrDecision:      (id: number) => `/recruitment/candidates/${id}/hr-decision/`,
    sendPortalLogin: (id: number) => `/recruitment/candidates/${id}/send-portal-login/`,
    emailLogs:       "/recruitment/emails/",
  },

  onboarding: {
    profile:        "/onboarding/",
    profileStep:    (step: number) => `/onboarding/step/${step}/`,
    documents:      "/onboarding/documents/",
    documentDetail: (docId: string) => `/onboarding/documents/${docId}/`,
    submit:         "/onboarding/",
    approvals:      "/onboarding/approvals/",
    pipeline:       "/onboarding/approvals/?view=pipeline",
    approve:        (userId: string) => `/onboarding/approvals/${userId}/`,
  },

  approvals: {
    leaveRequests:  "/leave/requests/",
    approveLeave:   (id: string) => `/leave/requests/${id}/approve/`,
    expenseList:    "/expenses/",
    approveExpense: (id: string) => `/expenses/${id}/approve/`,
  },

  expenses: {
    list:         "/expenses/",
    stats:        "/expenses/stats/",
    categories:   "/expenses/categories/",
    updateStatus: "/expenses/status/",
    detail:       (id: string) => `/expenses/${id}/`,
    approve:      (id: string) => `/expenses/${id}/approve/`,
  },

  assessments: {
    // Candidate portal
    my:               "/assessments/my/",
    respond:          (assignmentId: string, itemId: string) => `/assessments/${assignmentId}/respond/${itemId}/`,
    complete:         (assignmentId: string) => `/assessments/${assignmentId}/complete/`,
    retake:           (assignmentId: string) => `/assessments/${assignmentId}/retry/`,
    // HR management
    list:             "/assessments/",
    detail:           (id: string) => `/assessments/${id}/`,
    items:            (assessmentId: string) => `/assessments/${assessmentId}/items/`,
    itemDetail:       (itemId: string) => `/assessments/items/${itemId}/`,
    assign:           "/assessments/assign/",
    results:          (assessmentId: string) => `/assessments/${assessmentId}/results/`,
    candidateResults: (candidateId: string) => `/assessments/candidates/${candidateId}/results/`,
  },

  leave: {
    policy:       "/leave/policy/",
    policyDetail: (leaveType: string) => `/leave/policy/${leaveType}/`,
    balance:      "/leave/balance/",
    balanceCredit: "/leave/balance/credit/",
    balanceAdjust: (id: string) => `/leave/balance/${id}/`,
    requests:     "/leave/requests/",
    requestDetail: (id: string) => `/leave/requests/${id}/`,
    approve:      (id: string) => `/leave/requests/${id}/approve/`,
    stats:        "/leave/stats/",
    calendar:     "/leave/calendar/",
  },

  attendance: {
    settings:    "/attendance/settings/",
    punch:       "/attendance/punch/",
    today:       "/attendance/today/",
    stats:       "/attendance/stats/",
    summary:     "/attendance/summary/",
    calendar:    "/attendance/calendar/",
    correction:  "/attendance/correction/",
    geofencing:  (branchPk: number) => `/branch/branches/${branchPk}/geofencing/`,

    // HR Management
    dashboard:      "/attendance/dashboard/",
    records:        "/attendance/records/",
    record:         (id: string) => `/attendance/records/${id}/`,
    overtime:       "/attendance/overtime/",
    overtimeCreate: "/attendance/overtime/create/",
    invalidPunches:       "/attendance/invalid-punches/",
    invalidPunchAssign:   (id: string) => `/attendance/invalid-punches/${id}/assign/`,
    invalidPunchDiscard:  (id: string) => `/attendance/invalid-punches/${id}/discard/`,
    invalidPunchConvert:  (id: string) => `/attendance/invalid-punches/${id}/convert/`,
    recordAudit:          (id: string) => `/attendance/records/${id}/audit/`,
    unPunches:      "/attendance/un-punches/",
    import:         "/attendance/import/",
    export:         "/attendance/export/",
    corrections:       "/attendance/corrections/",
    correctionReview:  (id: string) => `/attendance/corrections/${id}/review/`,
  },

  notifications: {
    list:        "/notifications/",
    unreadCount: "/notifications/unread-count/",
    markRead:    (id: string) => `/notifications/${id}/read/`,
    markAllRead: "/notifications/read-all/",
  },
} as const;

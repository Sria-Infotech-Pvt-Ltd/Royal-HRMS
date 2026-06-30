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
    me:                "/employees/me/",
    detail:            (id: string) => `/employees/${id}/`,
    profile:           (id: string) => `/employees/${id}/profile/`,
    reportingManager:  (id: string) => `/employees/${id}/reporting-manager/`,
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
    profile:        "/onboarding/profile/",
    profileStep:    (step: number) => `/onboarding/profile/step/${step}/`,
    documents:      "/onboarding/documents/",
    documentDetail: (docId: string) => `/onboarding/documents/${docId}/`,
    submit:         "/onboarding/submit/",
    approvals:      "/onboarding/approvals/",
    approve:        (userId: string) => `/onboarding/approvals/${userId}/approve/`,
  },

  expenses: {
    list:  "/expenses/",
    stats: "/expenses/stats/",
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
} as const;

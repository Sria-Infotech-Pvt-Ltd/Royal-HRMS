export interface NavSection {
  section: string;
}
export interface NavItem {
  id: string;
  icon: string;
  label: string;
  badge?: string;
  path: string;
  permission: string | string[] | null; // null = always visible; string[] = any one grants access
  comingSoon?: boolean;       // true = non-clickable, shows "Soon" badge
}
export type NavEntry = NavSection | NavItem;

export function isSection(e: NavEntry): e is NavSection {
  return "section" in e;
}

const ALL_NAV: NavEntry[] = [
  { section: "Main" },
  { id: "dashboard", icon: "ti-layout-dashboard", label: "Dashboard", path: "/dashboard", permission: null },
  { id: "announcements", icon: "ti-speakerphone", label: "Announcements", path: "/dashboard/announcements", permission: "announcements.view" },

  { section: "Recruitment" },
  { id: "interview-list", icon: "ti-users", label: "Interview List", path: "/dashboard/interview-list", permission: "recruitment.view" },
  { id: "candidate-review", icon: "ti-user-check", label: "Review & Onboarding", path: "/dashboard/candidate-review", permission: "recruitment.view" },
  { id: "assessments", icon: "ti-clipboard-check", label: "Assessments", path: "/dashboard/assessments", permission: "assessments.view" },
  { id: "face-id-registrations", icon: "ti-face-id", label: "Face ID Registrations", path: "/dashboard/face-id-registrations", permission: "facial_recognition.approve" },

  { section: "Workforce" },
  { id: "employees", icon: "ti-id-badge", label: "Employees", path: "/dashboard/employees", permission: "employees.view" },
  { id: "org-chart", icon: "ti-sitemap", label: "Org Chart", path: "/dashboard/org-chart", permission: "org_chart.view" },
  { id: "branches", icon: "ti-building-skyscraper", label: "Branches", path: "/dashboard/branches", permission: "branches.view" },

  { section: "Time & Pay" },
  { id: "attendance", icon: "ti-clock", label: "Attendance", path: "/dashboard/attendance", permission: "attendance.create" },
  { id: "payroll", icon: "ti-report-money", label: "Payroll", path: "/dashboard/payroll", permission: "payroll.view" },
  { id: "leave", icon: "ti-beach", label: "Leave Management", path: "/dashboard/leave", permission: "leave.view" },
  { id: "work-from-home", icon: "ti-home-2", label: "Work From Home", path: "/dashboard/work-from-home", permission: "wfh.view" },
  { id: "expenses", icon: "ti-wallet", label: "Expenses", path: "/dashboard/expenses", permission: "expenses.view" },

  { section: "HR Ops" },
  { id: "approvals", icon: "ti-checks", label: "Approvals", path: "/dashboard/approvals", permission: ["leave.approve", "expenses.approve"] },
  // permission: null — every employee can create/view their own request here,
  // not just Manager/HR; the page itself scopes what each viewer sees.
  { id: "separation", icon: "ti-logout", label: "Separation & Exit", path: "/dashboard/separation", permission: null },
  { id: "documents", icon: "ti-folder", label: "Document Center", path: "/dashboard/documents", permission: "documents.view" },

  { section: "My" },
  { id: "my-attendance", icon: "ti-clock-check", label: "My Attendance", path: "/dashboard/my-attendance", permission: null },
  { id: "my-requests", icon: "ti-list-check", label: "My Requests", path: "/dashboard/my-requests", permission: null },
  // permission: null, matching my-attendance above — the backend's MyPayslipsView
  // is IsAuthenticated-only today. Switch this to "payroll.view_own" once the
  // backend actually adds that codename (see the payroll-permissions request
  // sent to the backend team) — until then, null is what's actually correct.
  { id: "my-payslip", icon: "ti-receipt", label: "My Payslips", path: "/dashboard/my-payslip", permission: null },
  { id: "referrals", icon: "ti-user-plus", label: "My Referrals", path: "/dashboard/referrals", permission: null },
  { id: "profile", icon: "ti-user-circle", label: "My Profile", path: "/dashboard/profile", permission: null },

  { section: "System" },
  { id: "audit", icon: "ti-shield-check", label: "Audit Log", path: "/dashboard/settings/audit", permission: "audit.view" },
  { id: "settings", icon: "ti-settings", label: "Settings", path: "/dashboard/settings", permission: "settings.view" },
];

export function buildNav(permissions: string[]): NavEntry[] {
  const permSet = new Set(permissions);
  const result: NavEntry[] = [];
  let pendingSection: NavEntry | null = null;
  let sectionHasItem = false;

  for (const entry of ALL_NAV) {
    if (isSection(entry)) {
      pendingSection = entry;
      sectionHasItem = false;
    } else {
      const item = entry as NavItem;
      const permVisible = item.permission === null
        || (Array.isArray(item.permission)
          ? item.permission.some(p => permSet.has(p))
          : permSet.has(item.permission));
      if (permVisible) {
        if (pendingSection && !sectionHasItem) result.push(pendingSection);
        result.push(item);
        sectionHasItem = true;
      }
    }
  }
  return result;
}

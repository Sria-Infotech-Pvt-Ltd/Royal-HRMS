import type { Notification, NotificationModule } from "@/types/notifications";

/** Where each notification module opens when its row is clicked in the bell, for a notice about the person's OWN request or account.
 *  Everything self-service opens the employee workspace (My Workspace), the current screens, not the old standalone pages. */
export const MODULE_ROUTES: Record<NotificationModule, string> = {
  leave:          "/dashboard/ess?tab=leave",
  attendance:     "/dashboard/ess?tab=attendance",
  regularization: "/dashboard/ess?tab=attendance",
  // The employee workspace's Announcements tab: readable by every employee, unlike the management page.
  announcement:   "/dashboard/ess?tab=announcements",
  holiday:        "/dashboard/ess?tab=attendance",
  permission:     "/dashboard/ess?tab=leave",
  expense:        "/dashboard/ess?tab=expenses",
  separation:     "/dashboard/separation",
  documents:      "/dashboard/ess?tab=documents",
  facial_recognition: "/dashboard/ess?tab=profile",
  birthday:       "/dashboard",
  security:       "/dashboard",
  // Employment changes open the employee workspace's Employment tab (status, confirmation, role), not the My Profile page.
  promotion:      "/dashboard/ess?tab=employment",
  confirmation:   "/dashboard/ess?tab=employment",
  payroll:        "/dashboard/ess?tab=payslips",
  system:         "/dashboard",
  // Fallback only: a timesheet notice opens its own place (see timesheetRoute below).
  timesheet:      "/dashboard/ess?tab=timesheet",
};

/** Where a notice that asks the person to ACT as an approver opens: the approvals screens (and the Attendance corrections tab for a
 *  regularization), never the person's own pages. A module not listed here has no approver screen and uses MODULE_ROUTES. */
export const APPROVER_ROUTES: Partial<Record<NotificationModule, string>> = {
  leave:          "/dashboard/approvals?section=approvals",
  permission:     "/dashboard/approvals?section=approvals",
  expense:        "/dashboard/approvals?section=approvals",
  attendance:     "/dashboard/attendance?tab=corrections",
  regularization: "/dashboard/attendance?tab=corrections",
  separation:     "/dashboard/separation",
  facial_recognition: "/dashboard/approvals?section=face_registration",
  payroll:        "/dashboard/payroll",
};

/** System notifications that concern one employee carry a `reference_id` saying where to go. */
const OWN_PROFILE_REFERENCE = "profile";
const HR_HELP_REFERENCE = "hr-help";
const PROFILE_CHANGE_REFERENCE = "profile-change";
const EMPLOYEE_REFERENCE_PREFIX = "employee:";

const TIMESHEET_WEEK = /(\d{4}-\d{2}-\d{2})/;

/** Timesheet notices: what an approver must act on opens Approvals > Timesheets; what happened to your own sheet opens that week
 *  in My Workspace. The week comes from the reference ("<week>:<sheet id>", or "employee-week:<week>" for the Friday reminder). */
function timesheetRoute({ notification_type: type, reference_id: reference }: Pick<Notification, "reference_id"> & Partial<Pick<Notification, "notification_type">>): string {
  const ref = reference ?? "";
  if (type === "timesheet_submitted" || ref.startsWith("approver-day:")) return "/dashboard/approvals?section=timesheets";
  const week = TIMESHEET_WEEK.exec(ref)?.[1];
  return week ? `/dashboard/ess?tab=timesheet&week=${week}` : MODULE_ROUTES.timesheet;
}

/** The page a notification should open. Joining-day notices link to the employee (or to your own profile when it is you);
    every other module keeps its fixed page, and an unknown module falls back to the dashboard. */
export function notificationRoute(notification: Pick<Notification, "module" | "reference_id"> & Partial<Pick<Notification, "notification_type" | "is_for_approver">>): string {
  if (notification.module === "timesheet") return timesheetRoute(notification);
  if (notification.module === "system") {
    const reference = notification.reference_id ?? "";
    if (reference === OWN_PROFILE_REFERENCE) return "/dashboard"; // the employee's own welcome notice opens the dashboard
    if (reference === PROFILE_CHANGE_REFERENCE) return "/dashboard/ess?tab=profile"; // the decision on your own profile correction
    if (reference === HR_HELP_REFERENCE) return "/dashboard/approvals?section=hr_requests"; // a new HR Help ticket opens the staff queue on the Approvals page
    if (reference.startsWith(EMPLOYEE_REFERENCE_PREFIX)) {
      const employeeId = reference.slice(EMPLOYEE_REFERENCE_PREFIX.length).trim();
      if (employeeId) return `/dashboard/employees/${encodeURIComponent(employeeId)}`;
    }
  }
  if (notification.module === "announcement" && /^\d+$/.test((notification.reference_id ?? "").trim())) {
    // reference_id is the announcement's id: open that one, not just the list.
    return `${MODULE_ROUTES.announcement}&announcement=${notification.reference_id.trim()}`;
  }
  if (notification.is_for_approver && APPROVER_ROUTES[notification.module]) return APPROVER_ROUTES[notification.module] as string; // a fixed table entry, checked on the line above
  return MODULE_ROUTES[notification.module] ?? "/dashboard";
}

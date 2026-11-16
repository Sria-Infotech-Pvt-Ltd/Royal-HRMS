import type { Notification, NotificationModule } from "@/types/notifications";

/** Where each notification module opens when its row is clicked in the bell. */
export const MODULE_ROUTES: Record<NotificationModule, string> = {
  leave:          "/dashboard/leave",
  attendance:     "/dashboard/my-attendance",
  regularization: "/dashboard/my-attendance",
  // The employee workspace's Announcements tab: readable by every employee, unlike the management page.
  announcement:   "/dashboard/ess?tab=announcements",
  holiday:        "/dashboard/attendance",
  permission:     "/dashboard/leave",
  // Employment changes open the employee workspace's Employment tab (status, confirmation, role), not the My Profile page.
  promotion:      "/dashboard/ess?tab=employment",
  confirmation:   "/dashboard/ess?tab=employment",
  payroll:        "/dashboard/payroll",
  system:         "/dashboard",
  // Fallback only: a timesheet notice opens its own place (see timesheetRoute below).
  timesheet:      "/dashboard/ess?tab=timesheet",
};

/** System notifications that concern one employee carry a `reference_id` saying where to go. */
const OWN_PROFILE_REFERENCE = "profile";
const HR_HELP_REFERENCE = "hr-help";
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
export function notificationRoute(notification: Pick<Notification, "module" | "reference_id"> & Partial<Pick<Notification, "notification_type">>): string {
  if (notification.module === "timesheet") return timesheetRoute(notification);
  if (notification.module === "system") {
    const reference = notification.reference_id ?? "";
    if (reference === OWN_PROFILE_REFERENCE) return "/dashboard"; // the employee's own welcome notice opens the dashboard
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
  return MODULE_ROUTES[notification.module] ?? "/dashboard";
}

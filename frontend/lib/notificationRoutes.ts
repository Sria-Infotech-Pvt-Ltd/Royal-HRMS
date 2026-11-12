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
  promotion:      "/dashboard/profile",
  confirmation:   "/dashboard/profile",
  payroll:        "/dashboard/payroll",
  system:         "/dashboard",
};

/** System notifications that concern one employee carry a `reference_id` saying where to go. */
const OWN_PROFILE_REFERENCE = "profile";
const EMPLOYEE_REFERENCE_PREFIX = "employee:";

/** The page a notification should open. Joining-day notices link to the employee (or to your own profile when it is you);
    every other module keeps its fixed page, and an unknown module falls back to the dashboard. */
export function notificationRoute(notification: Pick<Notification, "module" | "reference_id">): string {
  if (notification.module === "system") {
    const reference = notification.reference_id ?? "";
    if (reference === OWN_PROFILE_REFERENCE) return "/dashboard/profile";
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

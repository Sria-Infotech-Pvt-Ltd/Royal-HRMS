"use client";

import type { MonthName } from "@/types/company";

export const MONTH_NAMES: MonthName[] = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

// Leave balances/requests are keyed by plain calendar year on the backend —
// LeaveBalance.year is set from the joining/request date's .year directly,
// and the annual reset Celery task runs every Jan 1, not on the company's
// fiscal-year start month. Use this for anything under /leave/ — modules
// that need the company's actual fiscal year (Payroll, Reports) read it from
// the backend directly (e.g. GET /settings/company/financial-year/) rather
// than through a shared client-side hook.
export function getLeaveYear(): number {
  return new Date().getFullYear();
}

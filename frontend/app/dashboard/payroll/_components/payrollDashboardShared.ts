import type { PayrollCycle } from "@/types/payroll";

export const MONTHS_LONG = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
];
export const MONTHS_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

export interface PagedResponse<T> { results: T[]; count: number; }

export const STATUS_BADGE: Record<string, string> = {
  paid:                "badge badge-success",
  closed:              "badge badge-success",
  cancelled:           "badge badge-error",
  draft:               "badge badge-neutral",
  attendance_pending:  "badge badge-warn",
  attendance_approved: "badge badge-info",
  processing:          "badge badge-info",
  payslips_generated:  "badge badge-primary",
  query_window_open:   "badge badge-info",
};

export const STATUS_LABEL: Record<string, string> = {
  paid:                "Paid",
  closed:              "Closed",
  cancelled:           "Cancelled",
  draft:               "Draft",
  attendance_pending:  "Awaiting Approval",
  attendance_approved: "Approved",
  processing:          "Processing",
  payslips_generated:  "Payslips Ready",
  query_window_open:   "Query Window",
};

export const UNCANCELLABLE = ["paid", "closed", "cancelled"];
export const DAYS_LABEL    = ["S","M","T","W","T","F","S"];

export function getCalendarDates(year: number, month: number) {
  return {
    firstDay: new Date(year, month, 1).getDay(),
    days:     new Date(year, month + 1, 0).getDate(),
  };
}

// UAT-020 — every call site used to independently derive a cycle's "Month
// Year" label from cycle_start, which for a 25th-to-24th cycle (e.g.
// Nov-selected: 25-Oct → 24-Nov) displays the PREVIOUS calendar month —
// matching neither what the admin picked in the wizard nor the month it's
// actually paid in. pay_date's calendar month always equals the wizard's
// own selected Payroll Month (see PayrollPeriodStep.tsx's computeDates()),
// so it's the one field that already carries the intended label — this is
// the single naming rule every display of a cycle's period must use.
export function cyclePeriodLabel(
  cycle: Pick<PayrollCycle, "pay_date">,
  month: Intl.DateTimeFormatOptions["month"] = "long",
): string {
  return new Date(cycle.pay_date).toLocaleDateString("en-IN", { month, year: "numeric" });
}

/** Returns the cycle (non-cancelled) whose period covers the given month/year, or null. */
export function cycleForMonth(cycles: PayrollCycle[], calYear: number, calMonth: number): PayrollCycle | null {
  return cycles.find(c => {
    if (c.status === "cancelled") return false;
    const start = new Date(c.cycle_start);
    const end   = new Date(c.cycle_end);
    // Cycle covers calMonth if its date range overlaps with [first, last] of calMonth
    const first = new Date(calYear, calMonth, 1);
    const last  = new Date(calYear, calMonth + 1, 0);
    return start <= last && end >= first;
  }) ?? null;
}

export const DETAIL_STATUSES   = new Set(["paid", "closed"]);
export const TERMINAL_STATUSES = new Set(["paid", "closed", "cancelled"]);

export const PENDING_CYCLES_SECTION_ID = "payroll-pending-cycles";

"use client";

// Self-service-only "Leave" card for EmployeeDrawer.tsx — the balance
// endpoint always returns the CALLING user's own balances (no employee_id
// param exists), so this is only rendered when the drawer is opened in
// mode="self" (see EmployeeDrawer.tsx). Split into its own file purely to
// keep EmployeeDrawer.tsx under this codebase's ~300-line guideline.

import { useLeaveBalances } from "@/hooks/useEmployeeDashboard";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { financialYearRangeLabel } from "@/lib/formatDate";
import { currentFinancialYearStart } from "@/app/dashboard/my-payslip/_components/types";
import { SectionCard, Row } from "./EmployeeDrawerParts";

// Real LeaveBalance.leave_type codes (apps/hrms/models.py LEAVE_TYPE_CHOICES)
// → the labels/ordering this card shows — display-only, the balances
// themselves come from the same useLeaveBalances() hook the ESS dashboard's
// EmpLeaveBalances card already uses.
const LEAVE_LABEL: Record<string, string> = {
  earned:      "Earned / Privilege Leave",
  casual:      "Casual Leave",
  sick:        "Sick Leave",
  maternity:   "Maternity Leave",
  paternity:   "Paternity Leave",
  bereavement: "Bereavement Leave",
  comp_off:    "Compensatory Off",
  lwp:         "Leave Without Pay",
};
const LEAVE_ORDER = ["earned", "casual", "sick"];

interface AdminBalanceRow {
  leave_type: string;
  year: number;
  total_days: string;
  used_days: string;
  carried_forward: string;
  available_days: number;
}

/** Another employee's balances (admin/manager view) — the server scopes who
    may see whom; omit `employeeCode` for the signed-in user's own card. */
export default function EmployeeDrawerLeaveCard({ employeeCode }: { employeeCode?: string }) {
  const own = useLeaveBalances();
  const { data: fyConfig } = useFetch<{ financial_year_start_month: string }>(API.settings.financialYear);
  const other = useFetch<AdminBalanceRow[]>(employeeCode ? `${API.leave.balance}?employee_id=${encodeURIComponent(employeeCode)}` : null);

  const leaveData = employeeCode
    ? (other.data
        ? {
            year: other.data[0]?.year,
            lop_days: Number(other.data.find(b => b.leave_type === "lwp")?.used_days ?? 0),
            balances: other.data
              .filter(b => b.leave_type !== "lwp")
              .map(b => ({ leave_type: b.leave_type, remaining: b.available_days, total_days: Number(b.total_days) })),
          }
        : null)
    : own.data;

  const yearLabel = fyConfig ? financialYearRangeLabel(currentFinancialYearStart(fyConfig.financial_year_start_month)) : "";

  // The reference lists the three standing entitlements; show the rest (maternity, comp-off ...) only
  // when someone has none of them, so the card is never empty for a real balance.
  const allBalances = leaveData?.balances ?? [];
  const coreBalances = allBalances.filter(b => LEAVE_ORDER.includes(b.leave_type));
  const leaveBalances = (coreBalances.length > 0 ? coreBalances : allBalances)
    .slice()
    .sort((a, b) => {
      const ai = LEAVE_ORDER.indexOf(a.leave_type);
      const bi = LEAVE_ORDER.indexOf(b.leave_type);
      return (ai === -1 ? LEAVE_ORDER.length : ai) - (bi === -1 ? LEAVE_ORDER.length : bi);
    });

  return (
    <SectionCard title={`Leave${yearLabel ? ` · ${yearLabel}` : ""}`} list={leaveBalances.length > 0}>
      {leaveData === null && (employeeCode ? other.loading : own.loading) ? (
        <p className="hint">Loading…</p>
      ) : leaveBalances.length === 0 ? (
        <p className="hint">
          {employeeCode ? "No leave balances have been credited for this employee yet." : "No leave balances found. Contact HR to credit your leave."}
        </p>
      ) : (
        <>
          {leaveBalances.map(b => (
            <Row
              key={b.leave_type}
              label={`Balance — ${LEAVE_LABEL[b.leave_type] ?? b.leave_type}`}
              value={`${b.remaining} of ${b.total_days} days`}
            />
          ))}
          <Row label="Loss of pay" value={`${leaveData?.lop_days ?? 0} days`} />
        </>
      )}
    </SectionCard>
  );
}

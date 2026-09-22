"use client";

// Self-service-only "Leave" card for EmployeeDrawer.tsx — the balance
// endpoint always returns the CALLING user's own balances (no employee_id
// param exists), so this is only rendered when the drawer is opened in
// mode="self" (see EmployeeDrawer.tsx). Split into its own file purely to
// keep EmployeeDrawer.tsx under this codebase's ~300-line guideline.

import { useLeaveBalances } from "@/hooks/useEmployeeDashboard";
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

export default function EmployeeDrawerLeaveCard() {
  const { data: leaveData } = useLeaveBalances();

  const leaveBalances = (leaveData?.balances ?? [])
    .slice()
    .sort((a, b) => {
      const ai = LEAVE_ORDER.indexOf(a.leave_type);
      const bi = LEAVE_ORDER.indexOf(b.leave_type);
      return (ai === -1 ? LEAVE_ORDER.length : ai) - (bi === -1 ? LEAVE_ORDER.length : bi);
    });

  return (
    <SectionCard icon="ti-beach" title={`Leave${leaveData?.year ? ` · ${leaveData.year}` : ""}`}>
      {leaveBalances.length === 0 ? (
        <p style={{ fontSize: 12, color: "var(--on-variant)" }}>No leave balances found. Contact HR to credit your leave.</p>
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

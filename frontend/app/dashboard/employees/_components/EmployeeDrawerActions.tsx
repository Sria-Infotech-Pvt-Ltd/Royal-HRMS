"use client";

// The drawer's action row — "Perform an action" / "Basic pay" / "Leave" —
// each shown ONLY when the viewer's real permissions allow it:
//   Perform an action : employees.edit (applies directly) or
//                       employees.raise_action (raises for approval)
//   Basic pay         : payroll.view (read) — payroll.edit adds the form
//   Leave             : leave.view
// A Payroll Admin therefore sees Basic pay + Leave; a Reporting Manager sees
// Perform an action (raise) + Leave; HR sees all three.

import { useState } from "react";
import { usePermission } from "@/hooks/usePermission";
import type { Employee } from "../_data";
import PerformActionModal from "./PerformActionModal";
import EmployeeBasicPayModal from "./EmployeeBasicPayModal";
import EmployeeLeaveModal from "./EmployeeLeaveModal";

type Open = "action" | "pay" | "leave" | null;

interface Props {
  employee: Employee;
  /** Called after an action is applied/raised so the drawer can refresh its history. */
  onChanged: () => void;
  isExited?: boolean;
}

export default function EmployeeDrawerActions({ employee, onChanged, isExited = false }: Props) {
  const canEdit   = usePermission("employees.edit");
  const canRaise  = usePermission("employees.raise_action");
  const canPay    = usePermission("payroll.view");
  const canLeave  = usePermission("leave.view");
  const canEditPay = usePermission("payroll.edit");
  const canEditRecord = canEdit;
  const [open, setOpen] = useState<Open>(null);

  const canAct = (canEdit || canRaise) && !isExited;
  if (!canAct && !canPay && !canLeave) return null;

  return (
    <>
      <div className="emp-record-actions">
        {canAct   && <button className="rvbtn" type="button" onClick={() => setOpen("action")}>Perform an action</button>}
        {canPay   && <button className="rvbtn" type="button" onClick={() => setOpen("pay")}>Basic pay</button>}
        {canLeave && <button className="rvbtn" type="button" onClick={() => setOpen("leave")}>Leave</button>}
      </div>
      <div className="hint">
        {canEditRecord
          ? <>Press <b>Edit full record</b> to correct existing data. Use an <b>action</b> for effective-dated changes.</>
          : canRaise
            ? <>Use an <b>action</b> for effective-dated changes — it is sent to the approvers on its route, and nothing changes until they approve.</>
            : canEditPay
              ? <>Use <b>Basic pay</b> to revise this employee&apos;s pay with an effective date. Other changes to the record are made by HR.</>
              : <>This record is read-only for your role.</>}
      </div>

      {open === "action" && (
        <PerformActionModal employee={employee} onClose={() => setOpen(null)} onApplied={onChanged} />
      )}
      {open === "pay"   && <EmployeeBasicPayModal employee={employee} onClose={() => { setOpen(null); onChanged(); }} />}
      {open === "leave" && <EmployeeLeaveModal employee={employee} onClose={() => setOpen(null)} />}
    </>
  );
}

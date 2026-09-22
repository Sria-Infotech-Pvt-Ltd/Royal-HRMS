"use client";

// Unified "Perform an action" entry point for the Employee Detail page —
// opens the same PerformActionModal the Employee Directory row's "···" menu
// uses (see ../../_components/PerformActionModal.tsx), replacing this
// file's old dropdown (which deep-linked to the Promotion/Salary tabs and
// separation page) and its own small Confirmation modal.

import { usePermission } from "@/hooks/usePermission";
import PerformActionModal from "../../_components/PerformActionModal";
import { useState } from "react";
import type { Employee } from "../../_data";

interface Props {
  employee: Employee;
}

export default function ActionMenu({ employee }: Props) {
  const canEdit = usePermission("employees.edit");
  const canRevisePay = usePermission("payroll.edit");
  const canConfirm = usePermission("employees.confirm");
  const canPerformAny = canEdit || canRevisePay || canConfirm;
  const [open, setOpen] = useState(false);

  if (!canPerformAny) return null;

  return (
    <>
      <button onClick={() => setOpen(true)} suppressHydrationWarning className="btn">
        <i className="ti ti-bolt text-[14px]" />
        Perform an action
      </button>

      {open && (
        <PerformActionModal
          employee={employee}
          onClose={() => setOpen(false)}
          // The detail page's own state (position/salary/employment_status/
          // action-history, etc.) is spread across many separate hooks and
          // useState calls that this modal's real backend calls (PUT
          // employees/, POST employee-salary/, POST confirm/, POST
          // separation requests/) each update independently server-side —
          // a full reload is the simplest way to guarantee every one of
          // those pieces on this page reflects the applied action.
          onApplied={() => window.location.reload()}
        />
      )}
    </>
  );
}

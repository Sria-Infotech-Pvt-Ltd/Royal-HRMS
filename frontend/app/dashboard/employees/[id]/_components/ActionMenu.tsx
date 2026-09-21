"use client";

// Unified "Perform an action" entry point for the Employee Detail page —
// consolidates the mockup's 5-action list without duplicating what already
// exists: Promotion (PromotionTab) and Pay Change (SalaryTab) already have
// their own full modal flows, so those menu items just switch to that tab
// rather than re-implementing the modal here. Confirmation is genuinely new
// (see EmployeeConfirmView) and gets its own small modal, since there's
// nowhere else for it to live. Separation already has a complete separate
// module — this only deep-links to it.

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import Modal from "@/components/Modal";
import type { Employee } from "../../_data";

interface Props {
  employee: Employee;
  onSelectTab: (tab: string) => void;
  onConfirmed: (employmentStatus: string, confirmationDate: string | null) => void;
}

export default function ActionMenu({ employee, onSelectTab, onConfirmed }: Props) {
  const router = useRouter();
  const canPromote = usePermission("employees.edit");
  const canReviseSalary = usePermission("payroll.edit");
  const canConfirm = usePermission("employees.confirm");

  const [open, setOpen] = useState(false);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const alreadyConfirmed = employee.employmentStatus === "confirmed";
  const hasAnyAction = canPromote || canReviseSalary || (canConfirm && !alreadyConfirmed);

  if (!hasAnyAction) return null;

  return (
    <>
      <div className="relative" ref={menuRef}>
        <button onClick={() => setOpen(o => !o)} suppressHydrationWarning className="btn">
          <i className="ti ti-bolt text-[14px]" />
          Perform an action
          <i className={`ti ${open ? "ti-chevron-up" : "ti-chevron-down"} text-[12px]`} />
        </button>

        {open && (
          <div
            className="absolute right-0 mt-1.5 w-56 rounded-lg border shadow-lg z-20 py-1.5"
            style={{ background: "var(--surface)", borderColor: "var(--outline-v)" }}
          >
            {canPromote && (
              <MenuItem icon="ti-arrow-up-right" label="Promotion / Reassign Position" onClick={() => { onSelectTab("promotion"); setOpen(false); }} />
            )}
            {canReviseSalary && (
              <MenuItem icon="ti-currency-rupee" label="Pay Change" onClick={() => { onSelectTab("salary"); setOpen(false); }} />
            )}
            {canConfirm && !alreadyConfirmed && (
              <MenuItem icon="ti-circle-check" label="Confirmation" onClick={() => { setShowConfirmModal(true); setOpen(false); }} />
            )}
            <MenuItem icon="ti-door-exit" label="Separation" onClick={() => { router.push("/dashboard/separation"); setOpen(false); }} />
          </div>
        )}
      </div>

      {showConfirmModal && (
        <ConfirmModal
          employeeCode={employee.code}
          onClose={() => setShowConfirmModal(false)}
          onConfirmed={onConfirmed}
        />
      )}
    </>
  );
}

function MenuItem({ icon, label, onClick }: { icon: string; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-2.5 w-full px-3.5 py-2 text-left text-[13px] font-medium transition-colors hover:bg-[var(--bg-mid)]"
      style={{ color: "var(--on-bg)" }}
    >
      <i className={`ti ${icon} text-[14px]`} style={{ color: "var(--primary)" }} />
      {label}
    </button>
  );
}

function ConfirmModal({
  employeeCode,
  onClose,
  onConfirmed,
}: {
  employeeCode: string;
  onClose: () => void;
  onConfirmed: (employmentStatus: string, confirmationDate: string | null) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [effectiveDate, setEffectiveDate] = useState(today);
  const [remarks, setRemarks] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleConfirm() {
    setSaving(true);
    setErr(null);
    try {
      const res = await clientApi.post(API.employees.confirm(employeeCode), {
        effective_date: effectiveDate,
        remarks,
      });
      const data = res.data?.data;
      onConfirmed(data?.employment_status ?? "confirmed", data?.confirmation_date ?? effectiveDate);
      onClose();
    } catch (error: unknown) {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setErr(msg ?? "Failed to confirm employee. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title={<h2 className="modal-title">Confirm Employment</h2>}
      onClose={onClose}
      footer={
        <>
          <button onClick={onClose} disabled={saving} className="btn btn-ghost">Cancel</button>
          <button onClick={handleConfirm} disabled={saving} className="btn btn-filled">
            {saving ? "Confirming…" : "Confirm Employee"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="hint">
          This moves the employee from probation to confirmed. This cannot be undone from here.
        </p>

        {err && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg text-[13px] font-medium" style={{ background: "var(--crit-bg)", color: "var(--crit)" }}>
            <i className="ti ti-alert-circle text-[15px]" />
            {err}
          </div>
        )}

        <div className="f">
          <label>Effective Date</label>
          <input type="date" value={effectiveDate} onChange={e => setEffectiveDate(e.target.value)} className="finput" />
        </div>

        <div className="f">
          <label>Remarks <span className="tag">OPTIONAL</span></label>
          <textarea value={remarks} onChange={e => setRemarks(e.target.value)} rows={3} className="finput" style={{ height: "auto" }} />
        </div>
      </div>
    </Modal>
  );
}

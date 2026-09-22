"use client";

// Unified "Perform an action" modal for the Employee Directory — replaces
// both EmployeeRowActionsMenu's old inline "Deactivate" toggle and the
// Employee Detail page's ActionMenu dropdown (which deep-linked to the
// Promotion/Salary tabs and had its own small Confirmation modal). Every
// action funnels through this one flow instead: Promotion, Org assignment,
// Pay change, Confirmation and Separation, each against the same real
// backend endpoint that action already had (no parallel endpoints added —
// see each action's submit() below for exactly which one).

import { useEffect, useMemo, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import { useFetch } from "@/hooks/useFetch";
import { useOrgUnitsAndPositions } from "@/hooks/useOrgUnitsAndPositions";
import { getStoredUser } from "@/lib/auth";
import { fullName, type Employee, type FieldOption } from "../_data";
import {
  ACTION_LABELS, approvalRouteFor, reversibilityNote,
  CONFIRMATION_REASONS, ORG_ASSIGNMENT_REASONS, PAY_CHANGE_REASONS, PROMOTION_REASONS,
  type ActionType, type ActionHistoryRow, type EmployeeDetailSnapshot, type FieldDiffRow,
} from "./PerformActionFields/types";
import {
  ReasonSelect, PromotionFields, OrgAssignmentFields, PayChangeFields,
  ConfirmationFields, SeparationFields,
} from "./PerformActionFields/ActionFieldSections";
import ActionSummarySections from "./PerformActionFields/ActionSummarySections";

interface SeparationTypeOption {
  value: string; label: string; reason_applicable: boolean; notice_period_applicable: boolean;
}
interface ManagerOption {
  id: string; employee_id: string; full_name: string;
}

const today = () => new Date().toISOString().slice(0, 10);
const dayBefore = (iso: string) => {
  if (!iso) return "—";
  const d = new Date(iso);
  d.setDate(d.getDate() - 1);
  return d.toISOString().slice(0, 10);
};
const slash = (iso: string) => {
  if (!iso || iso === "9999-12-31") return "31/12/9999";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
};

export default function PerformActionModal({ employee, onClose, onApplied }: {
  employee: Employee;
  onClose: () => void;
  /** Called after a successful apply so the caller can refetch/refresh. */
  onApplied: () => void;
}) {
  const [actionType, setActionType] = useState<ActionType | "">("");
  const [reason, setReason] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(today());
  const [positionId, setPositionId] = useState("");
  const [annualCtc, setAnnualCtc] = useState("");
  const [managerId, setManagerId] = useState("");
  const [workLocation, setWorkLocation] = useState("");
  const [separationType, setSeparationType] = useState("");
  const [lastWorkingDay, setLastWorkingDay] = useState("");
  const [separationConfirmed, setSeparationConfirmed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  const { data: detail } = useFetch<EmployeeDetailSnapshot>(API.employees.detail(employee.code));
  const { data: history } = useFetch<ActionHistoryRow[]>(API.employees.actionHistory(employee.code));
  const { units, positionsForUnit } = useOrgUnitsAndPositions();
  const { data: managers } = useFetch<ManagerOption[]>(
    employee.location ? `${API.employees.managerList}?branch=${encodeURIComponent(employee.location)}` : null
  );
  const { data: separationTypes } = useFetch<SeparationTypeOption[]>(
    actionType === "separation" ? API.separation.types : null
  );

  const currentUser = getStoredUser();
  const currentRecord = history?.find(h => h.is_current) ?? null;

  const detailOrgUnitId = detail?.org_unit_id ?? "";
  const positionOptions: FieldOption[] = useMemo(() => {
    if (!detailOrgUnitId) return [];
    return positionsForUnit(detailOrgUnitId, false).map(p => ({ value: p.id, label: p.title }));
  }, [detailOrgUnitId, positionsForUnit]);

  const managerOptions: FieldOption[] = useMemo(
    () => (managers ?? [])
      .filter(m => m.id !== detail?.uuid)
      .map(m => ({ value: m.id, label: m.full_name })),
    [managers, detail?.uuid],
  );

  const separationTypeOptions: FieldOption[] = useMemo(
    () => (separationTypes ?? []).map(t => ({ value: t.value, label: t.label })),
    [separationTypes],
  );

  const reasonOptions = actionType === "promotion" ? PROMOTION_REASONS
    : actionType === "org_assignment" ? ORG_ASSIGNMENT_REASONS
    : actionType === "pay_change" ? PAY_CHANGE_REASONS
    : actionType === "confirmation" ? CONFIRMATION_REASONS
    : [];

  // Reset the fields that only apply to the previously selected action type
  // whenever the action type itself changes.
  useEffect(() => {
    setReason(""); setPositionId(""); setAnnualCtc(""); setManagerId("");
    setWorkLocation(""); setSeparationType(""); setLastWorkingDay("");
    setSeparationConfirmed(false); setErr("");
  }, [actionType]);

  const currentStatusLabel = detail?.employment_status === "confirmed" ? "Confirmed" : "Probation";
  const currentManagerName = detail?.reporting_manager?.name ?? employee.reportingManagerName ?? null;

  // ── BEFORE → AFTER + "not changed" field list, built per action type ──
  const changedFieldKeys: string[] = actionType === "promotion" ? ["position"]
    : actionType === "org_assignment" ? ["reporting_manager", "work_location"]
    : actionType === "pay_change" ? ["annual_ctc"]
    : actionType === "confirmation" ? ["employment_status"]
    : actionType === "separation" ? ["employment_status", "last_working_day"]
    : [];

  const diffRows: FieldDiffRow[] = useMemo(() => {
    const rows: FieldDiffRow[] = [];
    if (actionType === "promotion") {
      const selected = positionOptions.find(p => p.value === positionId);
      rows.push({ key: "position", label: "Position", before: employee.designation || "—", after: selected ? selected.label : null });
      if (annualCtc) rows.push({ key: "annual_ctc", label: "Annual CTC", before: "—", after: `₹${Number(annualCtc).toLocaleString("en-IN")}` });
    }
    if (actionType === "org_assignment") {
      const selectedMgr = managerOptions.find(m => m.value === managerId);
      rows.push({ key: "reporting_manager", label: "Reporting manager", before: currentManagerName || "CEO Office", after: selectedMgr ? selectedMgr.label : null });
      rows.push({ key: "work_location", label: "Work location", before: detail?.work_location || "—", after: workLocation ? workLocation : null });
    }
    if (actionType === "pay_change") {
      rows.push({ key: "annual_ctc", label: "Annual CTC", before: "—", after: annualCtc ? `₹${Number(annualCtc).toLocaleString("en-IN")}` : null });
    }
    if (actionType === "confirmation") {
      rows.push({ key: "employment_status", label: "Employee status", before: currentStatusLabel, after: "Confirmed" });
    }
    if (actionType === "separation") {
      rows.push({ key: "employment_status", label: "Employee status", before: "Active", after: "Notice Period" });
      rows.push({ key: "last_working_day", label: "Last working day", before: "—", after: lastWorkingDay ? slash(lastWorkingDay) : null });
    }
    return rows;
  }, [actionType, positionId, positionOptions, annualCtc, managerId, managerOptions, workLocation, detail, employee, currentStatusLabel, lastWorkingDay, currentManagerName]);

  const notChangedRows: { label: string; value: string }[] = [
    { key: "position", label: "Position", value: employee.designation || "—" },
    { key: "org_unit", label: "Org unit", value: employee.orgUnitName || employee.department || "—" },
    { key: "work_location", label: "Work location", value: detail?.work_location || "—" },
    { key: "reporting_manager", label: "Reporting manager", value: currentManagerName || "CEO Office" },
    { key: "employment_status", label: "Status", value: currentStatusLabel },
    { key: "record_range", label: "Current record date range", value: currentRecord ? `${slash(currentRecord.effective_from)} – ${slash(currentRecord.effective_to)}` : "—" },
  ].filter(r => r.key === "record_range" || !changedFieldKeys.includes(r.key === "position" ? "position" : r.key)).map(r => ({ label: r.label, value: r.value }));

  const route = actionType ? approvalRouteFor(actionType, currentManagerName, false) : "";
  const reversibility = actionType ? reversibilityNote(actionType) : null;

  function validate(): string {
    if (!actionType) return "Select an action type.";
    if (!reason && actionType !== "separation") return "Select a reason.";
    if (!effectiveFrom) return "Effective from is required.";
    if (actionType === "promotion" && !positionId) return "Select a position.";
    if (actionType === "pay_change" && !annualCtc) return "Annual CTC is required.";
    if (actionType === "confirmation" && currentStatusLabel === "Confirmed") return "This employee is already confirmed.";
    if (actionType === "separation") {
      if (!separationType) return "Select a separation type.";
      if (!lastWorkingDay) return "Last working day is required.";
      if (!separationConfirmed) return "Confirm the authorisation checkbox before applying.";
    }
    return "";
  }

  async function submit() {
    const validation = validate();
    if (validation) { setErr(validation); return; }
    setSaving(true);
    setErr("");
    try {
      if (actionType === "promotion") {
        await clientApi.put(API.employees.detail(employee.code), {
          position: positionId, effective_date: effectiveFrom, reason,
        });
        if (annualCtc && detail) {
          await clientApi.post(API.payroll.employeeSalary, {
            employee: detail.uuid, annual_ctc: annualCtc, effective_from: effectiveFrom, reason: "promotion",
          });
        }
      } else if (actionType === "org_assignment") {
        const payload: Record<string, string> = { effective_date: effectiveFrom, reason };
        if (managerId) payload.reporting_manager_id = managerId;
        if (workLocation) payload.work_location = workLocation;
        await clientApi.put(API.employees.detail(employee.code), payload);
      } else if (actionType === "pay_change" && detail) {
        await clientApi.post(API.payroll.employeeSalary, {
          employee: detail.uuid, annual_ctc: annualCtc, effective_from: effectiveFrom, reason,
        });
      } else if (actionType === "confirmation") {
        await clientApi.post(API.employees.confirm(employee.code), {
          effective_date: effectiveFrom, reason,
        });
      } else if (actionType === "separation") {
        await clientApi.post(API.separation.list, {
          employee_id: employee.code,
          separation_type: separationType,
          request_date: effectiveFrom,
          proposed_last_working_day: lastWorkingDay,
        });
      }
      onApplied();
      onClose();
    } catch (error: unknown) {
      const msg = (error as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setErr(msg ?? "Failed to apply this action. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const applyDisabled = saving || (actionType === "separation" && !separationConfirmed);

  return (
    <Modal
      title={<h2 className="modal-title">Perform an <em style={{ color: "var(--brand-ink)" }}>action</em></h2>}
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button onClick={onClose} disabled={saving} className="btn btn-ghost">Cancel</button>
          <button onClick={submit} disabled={applyDisabled} className="btn btn-filled">
            {saving ? "Applying…" : "Apply action"}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="hint">
          {fullName(employee)} · {employee.code} — current record runs {currentRecord ? `${slash(currentRecord.effective_from)} to ${slash(currentRecord.effective_to)}` : "— to 31/12/9999"}
        </p>

        {err && (
          <div className="flex items-start gap-2 px-3.5 py-2.5 rounded-lg" style={{ background: "var(--crit-bg)", color: "var(--crit)" }}>
            <i className="ti ti-alert-circle text-[14px] mt-0.5 flex-shrink-0" />
            <span className="text-[13px]">{err}</span>
          </div>
        )}

        <div className="section-label">Action</div>
        <div className="g3">
          <div className="f">
            <label>Action type <span className="req">*</span></label>
            <select value={actionType} onChange={e => setActionType(e.target.value as ActionType)} className="finput" style={{ cursor: "pointer" }}>
              <option value="">Select an action type</option>
              <option value="promotion">Promotion</option>
              <option value="org_assignment">Org assignment</option>
              <option value="pay_change">Pay change</option>
              <option value="confirmation">Confirmation</option>
              <option value="separation">Separation</option>
            </select>
          </div>
          {actionType !== "separation" && (
            <ReasonSelect reason={reason} setReason={setReason} options={reasonOptions} actionChosen={!!actionType} />
          )}
          <div className="f">
            <label>Effective from <span className="req">*</span></label>
            <input type="date" value={effectiveFrom} onChange={e => setEffectiveFrom(e.target.value)} className="finput" />
          </div>
        </div>

        {actionType && (
          <>
            <div className="section-label">Fields this {ACTION_LABELS[actionType].toUpperCase()} may change</div>
            {actionType === "promotion" && (
              <PromotionFields positionId={positionId} setPositionId={setPositionId} positionOptions={positionOptions} annualCtc={annualCtc} setAnnualCtc={setAnnualCtc} />
            )}
            {actionType === "org_assignment" && (
              <OrgAssignmentFields managerId={managerId} setManagerId={setManagerId} managerOptions={managerOptions} workLocation={workLocation} setWorkLocation={setWorkLocation} />
            )}
            {actionType === "pay_change" && (
              <PayChangeFields annualCtc={annualCtc} setAnnualCtc={setAnnualCtc} />
            )}
            {actionType === "confirmation" && (
              <ConfirmationFields currentStatusLabel={currentStatusLabel} />
            )}
            {actionType === "separation" && (
              <>
                <SeparationFields
                  separationType={separationType} setSeparationType={setSeparationType} typeOptions={separationTypeOptions}
                  lastWorkingDay={lastWorkingDay} setLastWorkingDay={setLastWorkingDay} resultingStatusLabel="Notice Period"
                />
                <p className="hint">Reason for this separation is captured in the full Separation module after this record is filed (real reason list already used there).</p>
              </>
            )}

            <ActionSummarySections
              employee={employee}
              actionType={actionType}
              diffRows={diffRows}
              notChangedRows={notChangedRows}
              route={route}
              effectiveFromLabel={slash(effectiveFrom)}
              raisedByName={currentUser?.name ?? "—"}
              raisedByRole={currentUser?.role ?? "—"}
              // Safe: this whole block only renders inside `{actionType && (...)}`,
              // and `reversibility` is only ever null when actionType is falsy.
              reversibility={reversibility as { text: string; tone: "purple" | "amber" }}
              separationConfirmed={separationConfirmed}
              setSeparationConfirmed={setSeparationConfirmed}
              delimitedToLabel={dayBefore(effectiveFrom) === "—" ? "—" : slash(dayBefore(effectiveFrom))}
              newRecordFromLabel={slash(effectiveFrom)}
            />
          </>
        )}

        {units.length === 0 && actionType === "promotion" && (
          <p className="hint">Loading org structure…</p>
        )}
      </div>
    </Modal>
  );
}

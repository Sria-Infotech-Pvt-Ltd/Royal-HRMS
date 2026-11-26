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
import { useT } from "@/hooks/useI18n";
import { tr } from "@/lib/i18n/tr";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDateSlash } from "@/lib/formatDate";
import RefModal from "@/components/employees/RefModal";
import { useFetch } from "@/hooks/useFetch";
import { useOrgUnitsAndPositions } from "@/hooks/useOrgUnitsAndPositions";
import { getStoredUser } from "@/lib/auth";
import { usePermission } from "@/hooks/usePermission";
import { useToast } from "@/components/ToastProvider";
import { directoryStatusLabel, fullName, reportingManagerDisplay, type Employee, type FieldOption } from "../_data";
import {
  ACTION_LABELS, approvalRouteFor, reversibilityNote,
  CONFIRMATION_REASONS, ORG_ASSIGNMENT_REASONS, PAY_CHANGE_REASONS, PROMOTION_REASONS,
  type ActionType, type ActionHistoryRow, type EmployeeDetailSnapshot, type FieldDiffRow,
} from "./PerformActionFields/types";
import {
  ReasonSelect, PromotionFields, OrgAssignmentFields, PayChangeFields,
  ConfirmationFields, SeparationFields,
} from "./PerformActionFields/ActionFieldSections";
import ActionSummarySections, { EmployeeDetailsCard } from "./PerformActionFields/ActionSummarySections";
import DateInput from "@/components/shared/DateInput";
import { unitMoveOptions } from "@/lib/orgMove";

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
const DATE_FMT = (iso: string) => {
  if (!iso || iso === "9999-12-31") return "31/12/9999";
  return formatDateSlash(iso);
};

export default function PerformActionModal({ employee, onClose, onApplied, initialActionType }: {
  employee: Employee;
  onClose: () => void;
  /** Called after a successful apply so the caller can refetch/refresh. */
  onApplied: () => void;
  initialActionType?: ActionType;
}) {
  const t = useT();
  const [actionType, setActionType] = useState<ActionType | "">(initialActionType ?? "");
  const [reason, setReason] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(today());
  const [positionId, setPositionId] = useState("");
  const [annualCtc, setAnnualCtc] = useState("");
  const [managerId, setManagerId] = useState("");
  const [workLocation, setWorkLocation] = useState("");
  const [moveUnitId, setMoveUnitId] = useState("");
  const [separationType, setSeparationType] = useState("");
  const [lastWorkingDay, setLastWorkingDay] = useState("");
  const [separationConfirmed, setSeparationConfirmed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState("");

  // Anyone holding employees.edit (HR / Branch Admin / System Admin) applies
  // these actions directly, exactly as before. A Reporting Manager only holds
  // employees.raise_action: their submission becomes a pending request that
  // the approvers on its route must approve (apps.accounts personnel-action
  // requests). Separation is excluded — it has its own approval workflow.
  const canEdit  = usePermission("employees.edit");
  const canRaise = usePermission("employees.raise_action");
  const { showToast } = useToast();
  const raisesRequest = !canEdit && canRaise && actionType !== "separation";

  const { data: detail } = useFetch<EmployeeDetailSnapshot>(API.employees.detail(employee.code));
  const { data: history } = useFetch<ActionHistoryRow[]>(API.employees.actionHistory(employee.code));
  const { units, positions, positionsForUnit } = useOrgUnitsAndPositions();
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

  // Org assignment: another unit and one of its VACANT positions (the server refuses a seat someone else holds).
  const moveUnitOptions = useMemo(() => unitMoveOptions(units, positions, detailOrgUnitId), [units, positions, detailOrgUnitId]);
  const movePositionOptions: FieldOption[] = useMemo(
    () => (moveUnitId ? positions.filter(p => p.org_unit === moveUnitId && p.is_active && !p.holder).map(p => ({ value: p.id, label: p.grade ? `${p.title} · ${p.grade}` : p.title })) : []),
    [moveUnitId, positions],
  );

  const managerOptions: FieldOption[] = useMemo(
    () => (managers ?? [])
      .filter(m => m.id !== detail?.uuid)
      .map(m => ({ value: m.id, label: m.full_name })),
    [managers, detail?.uuid],
  );

  const separationTypeOptions: FieldOption[] = useMemo(
    () => (separationTypes ?? []).map(option => ({ value: option.value, label: option.label })),
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
    setReason(""); setPositionId(""); setAnnualCtc(""); setManagerId(""); setMoveUnitId("");
    setWorkLocation(""); setSeparationType(""); setLastWorkingDay("");
    setSeparationConfirmed(false); setErr("");
  }, [actionType]);

  const currentStatusLabel = detail?.employment_status === "confirmed" ? "Confirmed" : "Probation";
  const currentManagerName = detail?.reporting_manager?.name ?? employee.reportingManagerName ?? null;

  // ── BEFORE → AFTER + "not changed" field list, built per action type ──
  const changedFieldKeys: string[] = actionType === "promotion" ? ["position"]
    : actionType === "org_assignment" ? ["reporting_manager", "work_location", ...(moveUnitId ? ["org_unit", "position"] : [])]
    : actionType === "pay_change" ? ["annual_ctc"]
    : actionType === "confirmation" ? ["employment_status"]
    : actionType === "separation" ? ["employment_status", "last_working_day"]
    : [];

  const diffRows: FieldDiffRow[] = useMemo(() => {
    const rows: FieldDiffRow[] = [];
    if (actionType === "promotion") {
      const selected = positionOptions.find(p => p.value === positionId);
      rows.push({ key: "position", label: tr("Position"), before: employee.designation || "—", after: selected ? selected.label : null });
      if (annualCtc) rows.push({ key: "annual_ctc", label: tr("Annual CTC"), before: "—", after: `₹${Number(annualCtc).toLocaleString("en-IN")}` });
    }
    if (actionType === "org_assignment") {
      if (moveUnitId) {
        const unit = moveUnitOptions.find(option => option.value === moveUnitId);
        const seat = movePositionOptions.find(option => option.value === positionId);
        rows.push({ key: "org_unit", label: tr("Org unit"), before: employee.orgUnitName || employee.department || "—", after: unit ? unit.label : null });
        rows.push({ key: "position", label: tr("Position"), before: employee.designation || "—", after: seat ? seat.label : null });
      }
      const selectedMgr = managerOptions.find(m => m.value === managerId);
      rows.push({ key: "reporting_manager", label: tr("Reporting manager"), before: reportingManagerDisplay(currentManagerName, employee.noManagerByDesign), after: selectedMgr ? selectedMgr.label : null });
      rows.push({ key: "work_location", label: tr("Work location"), before: detail?.work_location || "—", after: workLocation ? workLocation : null });
    }
    if (actionType === "pay_change") {
      rows.push({ key: "annual_ctc", label: tr("Annual CTC"), before: "—", after: annualCtc ? `₹${Number(annualCtc).toLocaleString("en-IN")}` : null });
    }
    if (actionType === "confirmation") {
      rows.push({ key: "employment_status", label: tr("Employee status"), before: tr(currentStatusLabel), after: tr("Confirmed") });
    }
    if (actionType === "separation") {
      rows.push({ key: "employment_status", label: tr("Employee status"), before: tr("Active"), after: tr("Notice Period") });
      rows.push({ key: "notice_period_start", label: tr("Notice period starts"), before: tr("Not set"), after: effectiveFrom ? DATE_FMT(effectiveFrom) : null });
      rows.push({ key: "last_working_day", label: tr("Last working day"), before: tr("Not set"), after: lastWorkingDay ? DATE_FMT(lastWorkingDay) : null });
    }
    return rows;
  }, [actionType, positionId, positionOptions, annualCtc, managerId, managerOptions, workLocation, detail, employee, currentStatusLabel, lastWorkingDay, effectiveFrom, currentManagerName, moveUnitId, moveUnitOptions, movePositionOptions]);

  const orgUnitLabel = employee.orgUnitName
    ? (employee.orgUnitParentName ? `${employee.orgUnitName} › ${employee.orgUnitParentName}` : employee.orgUnitName)
    : (employee.department || "—");
  const directoryStatus = directoryStatusLabel(employee);

  const notChangedRows: { label: string; value: string }[] = [
    { key: "position", label: t("Position"), value: employee.designation || "—" },
    { key: "org_unit", label: t("Org unit"), value: orgUnitLabel },
    { key: "work_location", label: t("Work location"), value: detail?.work_location || employee.location || "—" },
    { key: "reporting_manager", label: t("Reporting manager"), value: reportingManagerDisplay(currentManagerName, employee.noManagerByDesign) },
    { key: "employment_status", label: t("Status"), value: t(directoryStatus) },
    { key: "record_range", label: t("Current record"), value: currentRecord ? `${DATE_FMT(currentRecord.effective_from)} → ${DATE_FMT(currentRecord.effective_to)}` : "—" },
  ].filter(r => r.key === "record_range" || (r.key === "position" && actionType !== "org_assignment") || !changedFieldKeys.includes(r.key)).map(r => ({ label: r.label, value: r.value }));

  const route = actionType ? approvalRouteFor(actionType, currentManagerName, false, raisesRequest) : "";
  const reversibility = actionType ? reversibilityNote(actionType) : null;

  function validate(): string {
    if (!actionType) return t("Select an action type.");
    if (!reason && actionType !== "separation") return t("Select a reason.");
    if (!effectiveFrom) return t("Effective from is required.");
    if (actionType === "promotion" && !positionId) return t("Select a position.");
    if (actionType === "org_assignment" && moveUnitId && !positionId) return t("Select a vacant position in the new org unit.");
    if (actionType === "org_assignment" && !positionId && !managerId && !workLocation) return t("Choose a new position, reporting manager or work location.");
    if (actionType === "pay_change" && !annualCtc) return t("Annual CTC is required.");
    if (actionType === "confirmation" && currentStatusLabel === "Confirmed") return t("This employee is already confirmed.");
    if (actionType === "separation") {
      if (!separationType) return t("Select a separation type.");
      if (!lastWorkingDay) return t("Last working day is required.");
      if (!separationConfirmed) return t("Confirm the authorisation checkbox before applying.");
    }
    return "";
  }

  async function submit() {
    const validation = validate();
    if (validation) { setErr(validation); return; }
    setSaving(true);
    setErr("");
    try {
      if (raisesRequest) {
        await clientApi.post(API.employees.actionRequests(employee.code), {
          action_type: actionType,
          reason,
          effective_from: effectiveFrom,
          position: positionId || undefined,
          annual_ctc: annualCtc || undefined,
          reporting_manager_id: managerId || undefined,
          work_location: workLocation || undefined,
        });
        showToast(t("{action} sent for approval.", { action: t(ACTION_LABELS[actionType as ActionType]) }), "success");
      } else if (actionType === "promotion") {
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
        if (positionId) { payload.position = positionId; payload.position_must_be_vacant = "true"; }
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
      setErr(msg ?? t("Failed to apply this action. Please try again."));
    } finally {
      setSaving(false);
    }
  }

  const applyDisabled = saving || (actionType === "separation" && !separationConfirmed);

  const footParams = { end: dayBefore(effectiveFrom) === "—" ? "—" : DATE_FMT(dayBefore(effectiveFrom)), start: DATE_FMT(effectiveFrom) };
  const footNote = effectiveFrom
    ? (raisesRequest
      ? t("If approved, the current record will be delimited to {end}; the new record runs {start} → 31/12/9999.", footParams)
      : t("Current record will be delimited to {end}; the new record runs {start} → 31/12/9999.", footParams))
    : "";
  const subtitleParams = { name: fullName(employee), code: employee.code, from: currentRecord ? DATE_FMT(currentRecord.effective_from) : "", to: currentRecord ? DATE_FMT(currentRecord.effective_to) : "" };

  return (
    <RefModal
      title={t("Perform an")} accent={t("action")}
      subtitle={currentRecord ? t("{name} · {code} — current record runs {from} to {to}.", subtitleParams) : t("{name} · {code} — current record runs — to 31/12/9999.", subtitleParams)}
      onClose={onClose}
      closeDisabled={saving}
      note={footNote}
      actions={
        <>
          <button onClick={onClose} disabled={saving} className="rvbtn ghost" type="button">{t("Cancel")}</button>
          <button onClick={submit} disabled={applyDisabled} className="rvbtn pri" type="button">
            {saving ? (raisesRequest ? t("Sending…") : t("Applying…")) : (raisesRequest ? t("Raise for approval") : t("Apply action"))}
          </button>
        </>
      }
    >
        {err && (
          <div className="flex items-start gap-2 px-3.5 py-2.5 rounded-lg" style={{ background: "var(--crit-bg)", color: "var(--crit)" }}>
            <i className="ti ti-alert-circle text-[14px] mt-0.5 flex-shrink-0" />
            <span className="text-[13px]">{err}</span>
          </div>
        )}

        <div className="sechead">{t("ACTION")}</div>
        <div className="g3">
          <div className="f">
            <label>{t("Action type")} <span className="req">*</span></label>
            <select value={actionType} onChange={e => setActionType(e.target.value as ActionType)} className="finput" style={{ cursor: "pointer" }}>
              <option value="">{t("Select an action type")}</option>
              <option value="promotion">{t("Promotion")}</option>
              <option value="org_assignment">{t("Org assignment")}</option>
              <option value="pay_change">{t("Pay change")}</option>
              <option value="confirmation">{t("Confirmation")}</option>
              <option value="separation">{t("Separation")}</option>
            </select>
          </div>
          {actionType !== "separation" && (
            <ReasonSelect reason={reason} setReason={setReason} options={reasonOptions} actionChosen={!!actionType} />
          )}
          <div className="f">
            <label>{t("Effective from")} <span className="req">*</span></label>
            <DateInput value={effectiveFrom} onChange={isoDate => setEffectiveFrom(isoDate)} className="finput" />
          </div>
        </div>

        <div className="divider" />
        <div className="sechead">{actionType ? t("FIELDS THIS {action} MAY CHANGE", { action: t(ACTION_LABELS[actionType]).toUpperCase() }) : t("FIELDS THIS ACTION MAY CHANGE")}</div>
        {!actionType && <div className="hint">{t("Choose an action above and the fields it may change will appear here.")}</div>}

        {actionType && (
          <>
            {actionType === "promotion" && (
              <PromotionFields positionId={positionId} setPositionId={setPositionId} positionOptions={positionOptions} annualCtc={annualCtc} setAnnualCtc={setAnnualCtc} />
            )}
            {actionType === "org_assignment" && (
              <OrgAssignmentFields
                managerId={managerId} setManagerId={setManagerId} managerOptions={managerOptions} workLocation={workLocation} setWorkLocation={setWorkLocation}
                move={{ unitId: moveUnitId, setUnitId: setMoveUnitId, unitOptions: moveUnitOptions, positionId, setPositionId, positionOptions: movePositionOptions }}
              />
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
                  lastWorkingDay={lastWorkingDay} setLastWorkingDay={setLastWorkingDay} resultingStatusLabel={t("Notice Period")}
                />
                <p className="hint">{t("Reason for this separation is captured in the full Separation module after this record is filed (real reason list already used there).")}</p>
              </>
            )}

            <ActionSummarySections
              employee={employee}
              actionType={actionType}
              diffRows={diffRows}
              rows={notChangedRows}
              route={t(route)}
              effectiveFromLabel={DATE_FMT(effectiveFrom)}
              raisedByName={currentUser?.name ?? "—"}
              raisedByRole={currentUser?.designation || "—"}
              // Safe: this whole block only renders inside `{actionType && (...)}`,
              // and `reversibility` is only ever null when actionType is falsy.
              reversibility={reversibility as { text: string; tone: "purple" | "amber" }}
              separationConfirmed={separationConfirmed}
              setSeparationConfirmed={setSeparationConfirmed}
              requiresApproval={raisesRequest}
            />
          </>
        )}

        {!actionType && <EmployeeDetailsCard employee={employee} rows={notChangedRows} />}

        {units.length === 0 && actionType === "promotion" && (
          <p className="hint">{t("Loading org structure…")}</p>
        )}
    </RefModal>
  );
}

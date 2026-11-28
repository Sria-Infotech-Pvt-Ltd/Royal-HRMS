"use client";

// Unified "Perform an action" modal for the Employee Directory — replaces
// both EmployeeRowActionsMenu's old inline "Deactivate" toggle and the
// Employee Detail page's ActionMenu dropdown (which deep-linked to the
// Promotion/Salary tabs and had its own small Confirmation modal). Every
// action funnels through this one flow instead: Promotion, Org assignment,
// Pay change, Confirmation and Separation, each against the same real
// backend endpoint that action already had (no parallel endpoints added —
// see submitPerformAction() in lib/performAction.ts for exactly which one).
// The form values live in usePerformActionForm, the data in usePerformActionData,
// and the BEFORE → AFTER rows are built in lib/performActionRows.ts.

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import RefModal from "@/components/employees/RefModal";
import DateInput from "@/components/shared/DateInput";
import { getStoredUser } from "@/lib/auth";
import { usePermission } from "@/hooks/usePermission";
import { useToast } from "@/components/ToastProvider";
import { usePerformActionForm } from "@/hooks/usePerformActionForm";
import { usePerformActionData } from "@/hooks/usePerformActionData";
import { dayBefore, formatRecordDate, submitPerformAction, validatePerformAction } from "@/lib/performAction";
import { buildDiffRows, buildNotChangedRows } from "@/lib/performActionRows";
import { fullName, type Employee } from "../_data";
import {
  ACTION_LABELS, approvalRouteFor, reversibilityNote,
  CONFIRMATION_REASONS, ORG_ASSIGNMENT_REASONS, PAY_CHANGE_REASONS, PROMOTION_REASONS,
  type ActionType, type ReasonOption,
} from "./PerformActionFields/types";
import { ReasonSelect } from "./PerformActionFields/ActionFieldSections";
import ActionFieldsPanel from "./PerformActionFields/ActionFieldsPanel";
import ActionSummarySections, { EmployeeDetailsCard } from "./PerformActionFields/ActionSummarySections";

const REASONS_FOR: Partial<Record<ActionType, ReasonOption[]>> = {
  promotion: PROMOTION_REASONS, org_assignment: ORG_ASSIGNMENT_REASONS, pay_change: PAY_CHANGE_REASONS, confirmation: CONFIRMATION_REASONS,
};

interface PerformActionModalProps {
  employee: Employee;
  onClose: () => void;
  /** Called after a successful apply so the caller can refetch/refresh. */
  onApplied: () => void;
  initialActionType?: ActionType;
}

export default function PerformActionModal({ employee, onClose, onApplied, initialActionType }: PerformActionModalProps) {
  const t = useT();
  const form = usePerformActionForm(initialActionType);
  const { values } = form;
  const { actionType, effectiveFrom, separationConfirmed } = values;
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

  const data = usePerformActionData(employee, actionType, values.moveUnitId);
  const { detail, currentRecord } = data;
  const currentUser = getStoredUser();
  const currentStatusLabel = detail?.employment_status === "confirmed" ? "Confirmed" : "Probation";
  const currentManagerName = detail?.reporting_manager?.name ?? employee.reportingManagerName ?? null;
  const rowContext = { employee, detail, currentRecord, currentStatusLabel, currentManagerName };
  const diffRows = buildDiffRows(values, data, rowContext);
  const notChangedRows = buildNotChangedRows(values, rowContext);

  const route = actionType ? approvalRouteFor(actionType, currentManagerName, false, raisesRequest) : "";
  const reversibility = actionType ? reversibilityNote(actionType) : null;

  function chooseActionType(next: ActionType | "") {
    form.setActionType(next);
    setErr("");
  }

  async function submit() {
    const validation = validatePerformAction(values, currentStatusLabel, t);
    if (validation) { setErr(validation); return; }
    setSaving(true);
    setErr("");
    try {
      await submitPerformAction({ employeeCode: employee.code, employeeUuid: detail?.uuid ?? null, values, raisesRequest });
      if (raisesRequest) showToast(t("{action} sent for approval.", { action: t(ACTION_LABELS[actionType as ActionType]) }), "success");
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

  const footParams = { end: dayBefore(effectiveFrom) === "—" ? "—" : formatRecordDate(dayBefore(effectiveFrom)), start: formatRecordDate(effectiveFrom) };
  const footNote = effectiveFrom
    ? (raisesRequest
      ? t("If approved, the current record will be delimited to {end}; the new record runs {start} → 31/12/9999.", footParams)
      : t("Current record will be delimited to {end}; the new record runs {start} → 31/12/9999.", footParams))
    : "";
  const subtitleParams = { name: fullName(employee), code: employee.code, from: currentRecord ? formatRecordDate(currentRecord.effective_from) : "", to: currentRecord ? formatRecordDate(currentRecord.effective_to) : "" };

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
            <select value={actionType} onChange={e => chooseActionType(e.target.value as ActionType)} className="finput" style={{ cursor: "pointer" }}>
              <option value="">{t("Select an action type")}</option>
              <option value="promotion">{t("Promotion")}</option>
              <option value="org_assignment">{t("Org assignment")}</option>
              <option value="pay_change">{t("Pay change")}</option>
              <option value="confirmation">{t("Confirmation")}</option>
              <option value="separation">{t("Separation")}</option>
            </select>
          </div>
          {actionType !== "separation" && (
            <ReasonSelect reason={values.reason} setReason={form.setReason} options={actionType ? REASONS_FOR[actionType] ?? [] : []} actionChosen={!!actionType} />
          )}
          <div className="f">
            <label>{t("Effective from")} <span className="req">*</span></label>
            <DateInput value={effectiveFrom} onChange={isoDate => form.setEffectiveFrom(isoDate)} className="finput" />
          </div>
        </div>

        <div className="divider" />
        <div className="sechead">{actionType ? t("FIELDS THIS {action} MAY CHANGE", { action: t(ACTION_LABELS[actionType]).toUpperCase() }) : t("FIELDS THIS ACTION MAY CHANGE")}</div>
        {!actionType && <div className="hint">{t("Choose an action above and the fields it may change will appear here.")}</div>}

        {actionType && (
          <>
            <ActionFieldsPanel form={form} data={data} currentStatusLabel={currentStatusLabel} />

            <ActionSummarySections
              employee={employee}
              actionType={actionType}
              diffRows={diffRows}
              rows={notChangedRows}
              route={t(route)}
              effectiveFromLabel={formatRecordDate(effectiveFrom)}
              raisedByName={currentUser?.name ?? "—"}
              raisedByRole={currentUser?.designation || "—"}
              // Safe: this whole block only renders inside `{actionType && (...)}`,
              // and `reversibility` is only ever null when actionType is falsy.
              reversibility={reversibility as { text: string; tone: "purple" | "amber" }}
              separationConfirmed={separationConfirmed}
              setSeparationConfirmed={form.setSeparationConfirmed}
              requiresApproval={raisesRequest}
            />
          </>
        )}

        {!actionType && <EmployeeDetailsCard employee={employee} rows={notChangedRows} />}

        {!data.hasUnits && actionType === "promotion" && (
          <p className="hint">{t("Loading org structure…")}</p>
        )}
    </RefModal>
  );
}

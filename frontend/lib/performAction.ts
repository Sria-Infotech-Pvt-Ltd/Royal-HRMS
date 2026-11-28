// The "Perform an action" modal's checks and its one save. Each action goes to the endpoint it already had (no parallel
// endpoints): Promotion and Org assignment edit the employee record, Pay change adds a salary revision, Confirmation and
// Separation use their own endpoints, and a Reporting Manager's submission becomes a pending action request instead.

import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDateSlash } from "@/lib/formatDate";
import type { TranslateParams } from "@/lib/i18n/translate";
import type { PerformActionValues } from "@/hooks/usePerformActionForm";

type Translate = (text: string, params?: TranslateParams) => string;

/** Today as YYYY-MM-DD, the modal's default "Effective from". */
export function performActionToday(): string {
  return new Date().toISOString().slice(0, 10);
}

export function dayBefore(iso: string): string {
  if (!iso) return "—";
  const date = new Date(iso);
  date.setDate(date.getDate() - 1);
  return date.toISOString().slice(0, 10);
}

/** A record date as DD/MM/YYYY; the open-ended end date shows as 31/12/9999. */
export function formatRecordDate(iso: string): string {
  if (!iso || iso === "9999-12-31") return "31/12/9999";
  return formatDateSlash(iso);
}

/** What is missing or wrong before the action can be applied, or "" when it is ready. */
export function validatePerformAction(values: PerformActionValues, currentStatusLabel: string, t: Translate): string {
  const { actionType, reason, effectiveFrom, positionId, moveUnitId, managerId, workLocation, annualCtc } = values;
  if (!actionType) return t("Select an action type.");
  if (!reason && actionType !== "separation") return t("Select a reason.");
  if (!effectiveFrom) return t("Effective from is required.");
  if (actionType === "promotion" && !positionId) return t("Select a position.");
  if (actionType === "org_assignment" && moveUnitId && !positionId) return t("Select a vacant position in the new org unit.");
  if (actionType === "org_assignment" && !positionId && !managerId && !workLocation) return t("Choose a new position, reporting manager or work location.");
  if (actionType === "pay_change" && !annualCtc) return t("Annual CTC is required.");
  if (actionType === "confirmation" && currentStatusLabel === "Confirmed") return t("This employee is already confirmed.");
  if (actionType === "separation") {
    if (!values.separationType) return t("Select a separation type.");
    if (!values.lastWorkingDay) return t("Last working day is required.");
    if (!values.separationConfirmed) return t("Confirm the authorisation checkbox before applying.");
  }
  return "";
}

interface SubmitArgs {
  employeeCode: string;
  /** The employee's database id, needed for salary revisions; null until their detail has loaded. */
  employeeUuid: string | null;
  values: PerformActionValues;
  raisesRequest: boolean;
}

/** Sends the action. Throws the API error so the modal can show its message. */
export async function submitPerformAction({ employeeCode, employeeUuid, values, raisesRequest }: SubmitArgs): Promise<void> {
  const { actionType, reason, effectiveFrom, positionId, annualCtc, managerId, workLocation } = values;
  if (raisesRequest) {
    await clientApi.post(API.employees.actionRequests(employeeCode), {
      action_type: actionType, reason, effective_from: effectiveFrom, position: positionId || undefined,
      annual_ctc: annualCtc || undefined, reporting_manager_id: managerId || undefined, work_location: workLocation || undefined,
    });
  } else if (actionType === "promotion") {
    await clientApi.put(API.employees.detail(employeeCode), { position: positionId, effective_date: effectiveFrom, reason });
    if (annualCtc && employeeUuid) {
      await clientApi.post(API.payroll.employeeSalary, { employee: employeeUuid, annual_ctc: annualCtc, effective_from: effectiveFrom, reason: "promotion" });
    }
  } else if (actionType === "org_assignment") {
    const payload: Record<string, string> = { effective_date: effectiveFrom, reason };
    if (managerId) payload.reporting_manager_id = managerId;
    if (workLocation) payload.work_location = workLocation;
    if (positionId) { payload.position = positionId; payload.position_must_be_vacant = "true"; }
    await clientApi.put(API.employees.detail(employeeCode), payload);
  } else if (actionType === "pay_change" && employeeUuid) {
    await clientApi.post(API.payroll.employeeSalary, { employee: employeeUuid, annual_ctc: annualCtc, effective_from: effectiveFrom, reason });
  } else if (actionType === "confirmation") {
    await clientApi.post(API.employees.confirm(employeeCode), { effective_date: effectiveFrom, reason });
  } else if (actionType === "separation") {
    await clientApi.post(API.separation.list, {
      employee_id: employeeCode, separation_type: values.separationType, request_date: effectiveFrom,
      proposed_last_working_day: values.lastWorkingDay,
    });
  }
}

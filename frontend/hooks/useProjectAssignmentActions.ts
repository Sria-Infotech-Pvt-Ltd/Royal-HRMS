"use client";

// Admin actions on an employee's project assignments from the Work Status panel: assign a project, edit it, extend
// it (also re-opens a finished one) or end it early. The server validates everything and needs employees.edit.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { VIEW_AS_HEADER } from "@/lib/viewAs";
import { useToast } from "@/components/ToastProvider";
import type { AssignmentAction, AssignmentForm, WorkStatusAssignment } from "@/types/workStatus";

export const EMPTY_FORM: AssignmentForm = {
  project_name: "", start_date: "", end_date: "", role: "", work_mode: "office", work_location: "", notes: "", reason: "",
};

const SUCCESS: Record<AssignmentAction, string> = {
  assign: "Project assigned.",
  edit:   "Project assignment updated.",
  extend: "Project extended.",
  end:    "Project ended.",
};

/** The form the dialog opens with: blank to assign, the assignment's values otherwise (extend starts with no new date). */
export function initialForm(action: AssignmentAction, assignment: WorkStatusAssignment | null): AssignmentForm {
  if (!assignment || action === "assign") return EMPTY_FORM;
  return {
    project_name: assignment.project_name,
    start_date:   assignment.start_date,
    end_date:     action === "extend" || action === "end" ? "" : assignment.end_date,
    role:         assignment.role,
    work_mode:    assignment.work_mode,
    work_location: assignment.work_location,
    notes:        assignment.notes,
    reason:       "",
  };
}

/** A message for what the admin must fix before sending, or "" when the form can go to the server. */
export function validateForm(action: AssignmentAction, form: AssignmentForm, assignment: WorkStatusAssignment | null): string {
  if (action === "assign" || action === "edit") {
    if (!form.project_name.trim()) return "Enter the project name.";
    if (!form.start_date) return "Start date is required.";
    if (!form.end_date) return "End date is required.";
    if (form.end_date < form.start_date) return "End date cannot be before the start date.";
    if (form.work_mode === "client_site" && !form.work_location.trim()) return "Enter the client location (address or site name).";
  }
  if (action === "extend") {
    if (!form.end_date) return "Choose the new end date.";
    if (assignment && form.end_date <= assignment.end_date) return "The new end date must be after the current end date.";
  }
  if (action === "end" && assignment && form.end_date && form.end_date > assignment.end_date) {
    return "To move the end date later, use Extend.";
  }
  return "";
}

// Always sent as the signed-in admin: inside an employee's workspace ("view as") every request would otherwise carry
// the view-as header, and the server refuses any change made "as" someone else.
const AS_SIGNED_IN_USER = { headers: { [VIEW_AS_HEADER]: "" } };

function requestFor(employeeId: string, action: AssignmentAction, form: AssignmentForm, assignment: WorkStatusAssignment | null) {
  const details = {
    project_name: form.project_name.trim(), start_date: form.start_date, end_date: form.end_date, role: form.role.trim(),
    work_mode: form.work_mode, work_location: form.work_location.trim(), notes: form.notes.trim(),
  };
  if (action === "assign" || !assignment) return clientApi.post(API.workStatus.assign(employeeId), details, AS_SIGNED_IN_USER);
  const id = assignment.assignment_id;
  if (action === "edit") return clientApi.patch(API.workStatus.edit(employeeId, id), details, AS_SIGNED_IN_USER);
  if (action === "extend") return clientApi.post(API.workStatus.extend(employeeId, id), { end_date: form.end_date, reason: form.reason.trim() }, AS_SIGNED_IN_USER);
  return clientApi.post(API.workStatus.end(employeeId, id), { ...(form.end_date ? { end_date: form.end_date } : {}), reason: form.reason.trim() }, AS_SIGNED_IN_USER);
}

export function useProjectAssignmentActions(employeeId: string, onSaved: () => void) {
  const { showToast } = useToast();
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  async function submit(action: AssignmentAction, form: AssignmentForm, assignment: WorkStatusAssignment | null): Promise<boolean> {
    const problem = validateForm(action, form, assignment);
    if (problem) { setError(problem); return false; }
    setIsSaving(true);
    setError("");
    try {
      await requestFor(employeeId, action, form, assignment);
      showToast(SUCCESS[action], "success");
      onSaved();
      return true;
    } catch (err: unknown) {
      // The API's error envelope carries a message written for the admin; fall back when it is missing.
      setError((err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Could not save this change.");
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  return { error, setError, isSaving, submit };
}

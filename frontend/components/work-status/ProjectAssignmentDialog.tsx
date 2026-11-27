"use client";

// One dialog for every admin action on a project assignment: Assign project, Edit, Extend (a new, later end date —
// also re-opens a finished project) and End (finish early; the end date defaults to today).

import { useState } from "react";
import Modal from "@/components/Modal";
import DateInput from "@/components/shared/DateInput";
import { initialForm, useProjectAssignmentActions } from "@/hooks/useProjectAssignmentActions";
import type { AssignmentAction, AssignmentForm, WorkMode, WorkStatusAssignment } from "@/types/workStatus";
import { WORK_MODE_OPTIONS, fmtDate } from "./workStatusFormat";

interface Props {
  employeeId:   string;
  employeeName: string;
  action:       AssignmentAction;
  /** The assignment being changed; null when assigning a new project. */
  assignment:   WorkStatusAssignment | null;
  onClose:      () => void;
  onSaved:      () => void;
}

const TITLE: Record<AssignmentAction, string> = {
  assign: "Assign project",
  edit:   "Edit project assignment",
  extend: "Extend project",
  end:    "End project",
};

const BUTTON: Record<AssignmentAction, [string, string]> = {
  assign: ["Assign", "Assigning…"],
  edit:   ["Save changes", "Saving…"],
  extend: ["Extend", "Extending…"],
  end:    ["End project", "Ending…"],
};

const GRID = { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12 };

export default function ProjectAssignmentDialog({ employeeId, employeeName, action, assignment, onClose, onSaved }: Props) {
  const [form, setForm] = useState<AssignmentForm>(() => initialForm(action, assignment));
  const { error, isSaving, submit } = useProjectAssignmentActions(employeeId, onSaved);
  const set = (field: keyof AssignmentForm) => (value: string) => setForm(previous => ({ ...previous, [field]: value }));
  const isDetails = action === "assign" || action === "edit";

  async function save() {
    if (await submit(action, form, assignment)) onClose();
  }

  const footer = (
    <>
      <button className="btn btn-outline" type="button" onClick={onClose} disabled={isSaving}>Cancel</button>
      <button className="btn btn-filled" type="button" onClick={save} disabled={isSaving}>
        {isSaving ? BUTTON[action][1] : BUTTON[action][0]}
      </button>
    </>
  );

  return (
    <Modal title={TITLE[action]} onClose={onClose} footer={footer} closeDisabled={isSaving} maxWidth={560}>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
          {employeeName}
          {assignment && ` · ${assignment.project_name} · ${fmtDate(assignment.start_date)} – ${fmtDate(assignment.end_date)}`}
        </div>
        {error && <div className="alert alert-error" style={{ fontSize: 12 }}>{error}</div>}

        {isDetails ? (
          <div style={GRID}>
            <div className="f" style={{ gridColumn: "1 / -1" }}>
              <label htmlFor="pa-project">Project name *</label>
              <input id="pa-project" className="finput" value={form.project_name} maxLength={255}
                placeholder="e.g. Website Revamp" onChange={event => set("project_name")(event.target.value)} />
            </div>
            <div className="f"><label htmlFor="pa-start">Start date *</label>
              <DateInput id="pa-start" className="finput" value={form.start_date} onChange={set("start_date")} /></div>
            <div className="f"><label htmlFor="pa-end">End date *</label>
              <DateInput id="pa-end" className="finput" value={form.end_date} min={form.start_date || undefined} onChange={set("end_date")} /></div>
            <div className="f"><label htmlFor="pa-mode">Work mode *</label>
              <select id="pa-mode" className="finput" value={form.work_mode}
                onChange={event => set("work_mode")(event.target.value as WorkMode) /* options come from WORK_MODE_OPTIONS, so the value is a WorkMode */}>
                {WORK_MODE_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
              </select></div>
            <div className="f"><label htmlFor="pa-location">{form.work_mode === "client_site" ? "Client location *" : "Location"}</label>
              <input id="pa-location" className="finput" value={form.work_location} maxLength={255}
                placeholder={form.work_mode === "client_site" ? "Client name, address or site" : "Optional, e.g. office or branch"}
                onChange={event => set("work_location")(event.target.value)} /></div>
            <div className="f"><label htmlFor="pa-role">Role</label>
              <input id="pa-role" className="finput" value={form.role} maxLength={100} placeholder="Optional"
                onChange={event => set("role")(event.target.value)} /></div>
            <div className="f"><label htmlFor="pa-notes">Notes</label>
              <input id="pa-notes" className="finput" value={form.notes} maxLength={2000} placeholder="Optional"
                onChange={event => set("notes")(event.target.value)} /></div>
          </div>
        ) : (
          <div style={GRID}>
            <div className="f">
              <label htmlFor="pa-new-end">{action === "extend" ? "New end date *" : "End date"}</label>
              <DateInput id="pa-new-end" className="finput" value={form.end_date} onChange={set("end_date")}
                min={assignment?.start_date} />
              {action === "end" && <div className="hint">Leave blank to end it today.</div>}
            </div>
            <div className="f">
              <label htmlFor="pa-reason">Reason</label>
              <input id="pa-reason" className="finput" value={form.reason} maxLength={1000} placeholder="Optional"
                onChange={event => set("reason")(event.target.value)} />
            </div>
          </div>
        )}
      </div>
    </Modal>
  );
}

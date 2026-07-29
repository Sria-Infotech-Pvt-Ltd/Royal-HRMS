"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { fullName, type Employee } from "../_data";

interface Props {
  employee:      Employee;
  branchOptions: string[];
  deptOptions:   string[];
  onClose:       () => void;
  onSaved:       () => void;
}

type StatusChoice = "active" | "inactive";

// Onboarding is a derived state (is_active && must_change_password on the
// backend), not something PATCH can set directly — an onboarding employee
// is, underneath, still active, so that's what this dropdown reflects.
function toStatusChoice(status: Employee["status"]): StatusChoice {
  return status === "inactive" ? "inactive" : "active";
}

export default function EditEmployeeModal({
  employee, branchOptions, deptOptions, onClose, onSaved,
}: Props) {
  const [name,        setName]        = useState(fullName(employee));
  const [phone,       setPhone]       = useState(employee.phone);
  const [branch,      setBranch]      = useState(employee.location);
  const [department,  setDepartment]  = useState(employee.department);
  const [designation, setDesignation] = useState(employee.designation);
  const [doj,         setDoj]         = useState(employee.dateOfJoining);
  const [statusChoice, setStatusChoice] = useState<StatusChoice>(toStatusChoice(employee.status));

  const [saving, setSaving] = useState(false);
  const [apiErr, setApiErr] = useState("");

  // The dropdowns are populated from the already-loaded employee list
  // (GET /api/employees/) rather than a separate branches/departments
  // fetch — the current employee's own values are folded in too, so
  // editing someone whose branch/department isn't already in that list
  // (e.g. the only person in a given department) doesn't leave the
  // select showing a blank, unselected option.
  const branchChoices = [...new Set([employee.location, ...branchOptions].filter(Boolean))];
  const deptChoices    = [...new Set([employee.department, ...deptOptions].filter(Boolean))];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setApiErr("");
    try {
      await clientApi.put(API.employees.detail(employee.id), {
        full_name:       name.trim(),
        phone:           phone.trim(),
        branch,
        department,
        designation:     designation.trim(),
        date_of_joining: doj,
      });

      const originalStatus = toStatusChoice(employee.status);
      if (statusChoice !== originalStatus) {
        await clientApi.patch(API.employees.detail(employee.id), {
          is_active: statusChoice === "active",
        });
      }

      onSaved();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })
          ?.response?.data?.message ?? "Failed to update employee. Please try again.";
      setApiErr(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={ev => { if (ev.target === ev.currentTarget) onClose(); }}>
      <div className="modal" style={{ width: "min(560px, 95vw)" }}>
        <div className="modal-header">
          <div className="modal-title">
            <i className="ti ti-edit" style={{ marginRight: 8 }} />
            Edit {fullName(employee)}
          </div>
          <button className="modal-close" onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="modal-body">
            {apiErr && (
              <div className="alert alert-error" style={{ marginBottom: 16 }}>
                <i className="ti ti-alert-circle" /><div>{apiErr}</div>
              </div>
            )}

            <div className="field-group mb-16">
              <label className="field-label">Full Name</label>
              <input
                className="field-input"
                value={name}
                onChange={ev => setName(ev.target.value)}
                required
              />
            </div>

            <div className="form-row cols-2 mb-16">
              <div className="field-group">
                <label className="field-label">Phone</label>
                <input
                  className="field-input"
                  value={phone}
                  onChange={ev => setPhone(ev.target.value)}
                />
              </div>
              <div className="field-group">
                <label className="field-label">Date of Joining</label>
                <input
                  type="date"
                  className="field-input"
                  value={doj}
                  onChange={ev => setDoj(ev.target.value)}
                />
              </div>
            </div>

            <div className="form-row cols-2 mb-16">
              <div className="field-group">
                <label className="field-label">Branch</label>
                <select
                  className="field-input field-select"
                  value={branch}
                  onChange={ev => setBranch(ev.target.value)}
                >
                  {branchChoices.map(b => <option key={b} value={b}>{b}</option>)}
                </select>
              </div>
              <div className="field-group">
                <label className="field-label">Department</label>
                <select
                  className="field-input field-select"
                  value={department}
                  onChange={ev => setDepartment(ev.target.value)}
                >
                  {deptChoices.map(d => <option key={d} value={d}>{d}</option>)}
                </select>
              </div>
            </div>

            <div className="form-row cols-2 mb-16">
              <div className="field-group">
                <label className="field-label">Designation</label>
                <input
                  className="field-input"
                  value={designation}
                  onChange={ev => setDesignation(ev.target.value)}
                />
              </div>
              <div className="field-group">
                <label className="field-label">Status</label>
                <select
                  className="field-input field-select"
                  value={statusChoice}
                  onChange={ev => setStatusChoice(ev.target.value as StatusChoice)}
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
                {employee.status === "onboarding" && (
                  <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
                    Currently onboarding — still active until they complete it.
                  </p>
                )}
              </div>
            </div>
          </div>

          <div className="modal-footer">
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={saving}>
              Cancel
            </button>
            <button type="submit" className="btn btn-filled" disabled={saving}>
              {saving
                ? <><i className="ti ti-loader-2 spin" /> Saving…</>
                : <><i className="ti ti-check" /> Save Changes</>
              }
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

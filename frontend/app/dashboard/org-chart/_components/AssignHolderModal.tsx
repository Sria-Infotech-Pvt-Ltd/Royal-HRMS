"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { Position } from "@/types/orgStructure";
import type { EmployeeOption } from "./OrgStructureClient";

interface Props {
  position: Position | null;
  employees: EmployeeOption[];
  onClose: () => void;
  onAssigned: () => void;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function AssignHolderModal({ position, employees, onClose, onAssigned }: Props) {
  const [employeeId, setEmployeeId] = useState(position?.holder ?? "");
  const [effectiveFrom, setEffectiveFrom] = useState(today());
  const [effectiveTo, setEffectiveTo] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [dateError, setDateError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit() {
    if (!position) return;
    if (!employeeId) { setFieldError("Pick an employee."); return; }
    if (!effectiveFrom) { setDateError("Effective from is required."); return; }
    if (effectiveTo && effectiveTo < effectiveFrom) { setDateError("Effective to can't be before effective from."); return; }
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await clientApi.post(API.orgStructure.positions.placements(position.id), {
        employee: employeeId, effective_from: effectiveFrom, effective_to: effectiveTo || null,
      });
      onAssigned();
    } catch (err: unknown) {
      setSubmitError((err as { message?: string })?.message ?? "Failed to assign holder.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!position) return null;

  return (
    <Modal
      title={<><i className="ti ti-user-question" style={{ marginRight: 8 }} />{position.holder ? "Reassign holder" : "Assign holder"}</>}
      onClose={onClose}
      maxWidth={440}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <><Spin />&nbsp;Saving…</> : position.holder ? "Reassign" : "Assign"}
          </button>
        </>
      }
    >
      {submitError && (
        <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
          {submitError}
        </div>
      )}
      <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 14 }}>{position.title} · {position.org_unit_name}</div>

      <div className="field-group mb-16">
        <label className="field-label">Employee <span style={{ color: "var(--error)" }}>*</span></label>
        <select
          className={`field-input field-select${fieldError ? " field-error" : ""}`}
          value={employeeId}
          onChange={e => { setEmployeeId(e.target.value); setFieldError(null); }}
        >
          <option value="">Select an employee…</option>
          {employees.map(e => <option key={e.id} value={e.id}>{e.full_name} ({e.employee_id})</option>)}
        </select>
        {fieldError && <p className="field-error-msg">{fieldError}</p>}
      </div>

      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Effective from <span style={{ color: "var(--error)" }}>*</span></label>
          <input
            className={`field-input${dateError ? " field-error" : ""}`}
            type="date"
            value={effectiveFrom}
            onChange={e => { setEffectiveFrom(e.target.value); setDateError(null); }}
          />
        </div>
        <div className="field-group">
          <label className="field-label">Effective to <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
          <input
            className="field-input"
            type="date"
            min={effectiveFrom}
            value={effectiveTo}
            onChange={e => { setEffectiveTo(e.target.value); setDateError(null); }}
          />
        </div>
      </div>
      {dateError && <p className="field-error-msg" style={{ marginTop: -10, marginBottom: 14 }}>{dateError}</p>}

      {position.holder_name && (
        <div style={{ marginBottom: 14, padding: "10px 14px", background: "var(--bg-low)", border: "1px solid var(--outline-v)", borderRadius: 8, fontSize: 12, color: "var(--on-variant)" }}>
          <i className="ti ti-info-circle" style={{ marginRight: 6 }} />
          {position.holder_name}&apos;s placement will be closed the day before the new start date and kept in history.
        </div>
      )}

      <div style={{ fontSize: 11.5, color: "var(--outline)" }}>
        Placing a person on a chief position makes them the unit&apos;s head automatically, as of the effective date above.
        A future-dated start schedules the change without affecting today&apos;s holder.
      </div>
    </Modal>
  );
}

"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { Director, DirectorPayload } from "@/types/company";

interface Props {
  existing: Director | null;
  onClose: () => void;
  onSaved: () => void;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

type ApiErrorShape = { message?: string; data?: Record<string, string[]> };

export default function DirectorModal({ existing, onClose, onSaved }: Props) {
  const [din, setDin] = useState(existing?.din ?? "");
  const [name, setName] = useState(existing?.name ?? "");
  const [designation, setDesignation] = useState(existing?.designation ?? "");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function validate(): boolean {
    const errs: Record<string, string> = {};
    if (!din.trim()) errs.din = "DIN is required.";
    if (!name.trim()) errs.name = "Name is required.";
    if (!designation.trim()) errs.designation = "Designation is required.";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function submit() {
    if (!validate()) return;
    setIsSubmitting(true);
    setSubmitError(null);
    setFieldErrors({});
    const payload: DirectorPayload = { din: din.trim(), name: name.trim(), designation: designation.trim() };
    try {
      if (existing) {
        await clientApi.put(API.settings.directors.detail(existing.id), payload);
      } else {
        await clientApi.post(API.settings.directors.list, payload);
      }
      onSaved();
    } catch (err: unknown) {
      const e = err as ApiErrorShape;
      const errs: Record<string, string> = {};
      Object.entries(e.data ?? {}).forEach(([k, v]) => { errs[k] = Array.isArray(v) ? v[0] : String(v); });
      setFieldErrors(errs);
      setSubmitError(e.message ?? "Failed to save director.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      title={<><i className="ti ti-user-star" style={{ marginRight: 8 }} />{existing ? "Edit" : "Add"} Director</>}
      onClose={onClose}
      maxWidth={420}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <><Spin />&nbsp;Saving…</> : "Save"}
          </button>
        </>
      }
    >
      {submitError && (
        <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
          {submitError}
        </div>
      )}

      <div className="field-group mb-16">
        <label className="field-label">DIN *</label>
        <input
          className={`field-input${fieldErrors.din ? " field-error" : ""}`}
          value={din}
          onChange={e => { setDin(e.target.value.replace(/\D/g, "").slice(0, 8)); setFieldErrors(p => ({ ...p, din: "" })); }}
          placeholder="8-digit Director Identification Number"
          maxLength={8}
        />
        {fieldErrors.din && <p className="field-error-msg">{fieldErrors.din}</p>}
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Name *</label>
        <input
          className={`field-input${fieldErrors.name ? " field-error" : ""}`}
          value={name}
          onChange={e => { setName(e.target.value); setFieldErrors(p => ({ ...p, name: "" })); }}
        />
        {fieldErrors.name && <p className="field-error-msg">{fieldErrors.name}</p>}
      </div>

      <div className="field-group">
        <label className="field-label">Designation *</label>
        <input
          className={`field-input${fieldErrors.designation ? " field-error" : ""}`}
          value={designation}
          onChange={e => { setDesignation(e.target.value); setFieldErrors(p => ({ ...p, designation: "" })); }}
          placeholder="e.g. Managing Director"
        />
        {fieldErrors.designation && <p className="field-error-msg">{fieldErrors.designation}</p>}
      </div>
    </Modal>
  );
}

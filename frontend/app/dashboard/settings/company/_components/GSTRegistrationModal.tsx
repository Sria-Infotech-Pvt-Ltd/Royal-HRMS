"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { GSTRegistration, GSTRegistrationPayload } from "@/types/company";
import { GST_REGISTRATION_TYPE_OPTIONS, STATES } from "../_data";

interface Props {
  existing: GSTRegistration | null;
  onClose: () => void;
  onSaved: () => void;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

type ApiErrorShape = { message?: string; data?: Record<string, string[]> };

export default function GSTRegistrationModal({ existing, onClose, onSaved }: Props) {
  const [gstin, setGstin] = useState(existing?.gstin ?? "");
  const [state, setState] = useState(existing?.state ?? "");
  const [registrationType, setRegistrationType] = useState(existing?.registration_type ?? "regular");
  const [placeOfBusiness, setPlaceOfBusiness] = useState(existing?.place_of_business ?? "");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function validate(): boolean {
    const errs: Record<string, string> = {};
    if (!gstin.trim()) errs.gstin = "GSTIN is required.";
    if (!state) errs.state = "State is required.";
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function submit() {
    if (!validate()) return;
    setIsSubmitting(true);
    setSubmitError(null);
    setFieldErrors({});
    const payload: GSTRegistrationPayload = {
      gstin: gstin.trim().toUpperCase(),
      state,
      registration_type: registrationType,
      place_of_business: placeOfBusiness.trim(),
    };
    try {
      if (existing) {
        await clientApi.put(API.settings.gstRegistrations.detail(existing.id), payload);
      } else {
        await clientApi.post(API.settings.gstRegistrations.list, payload);
      }
      onSaved();
    } catch (err: unknown) {
      const e = err as ApiErrorShape;
      const errs: Record<string, string> = {};
      Object.entries(e.data ?? {}).forEach(([k, v]) => { errs[k] = Array.isArray(v) ? v[0] : String(v); });
      setFieldErrors(errs);
      setSubmitError(e.message ?? "Failed to save GST registration.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      title={<><i className="ti ti-receipt-tax" style={{ marginRight: 8 }} />{existing ? "Edit" : "Add"} GST Registration</>}
      onClose={onClose}
      maxWidth={460}
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
        <label className="field-label">GSTIN *</label>
        <input
          className={`field-input${fieldErrors.gstin ? " field-error" : ""}`}
          value={gstin}
          onChange={e => { setGstin(e.target.value.toUpperCase()); setFieldErrors(p => ({ ...p, gstin: "" })); }}
          placeholder="22AAAAA0000A1Z5"
          maxLength={15}
        />
        {fieldErrors.gstin && <p className="field-error-msg">{fieldErrors.gstin}</p>}
      </div>

      <div className="field-group mb-16">
        <label className="field-label">State *</label>
        <select
          className={`field-input${fieldErrors.state ? " field-error" : ""}`}
          value={state}
          onChange={e => { setState(e.target.value); setFieldErrors(p => ({ ...p, state: "" })); }}
        >
          <option value="">Select…</option>
          {STATES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        {fieldErrors.state && <p className="field-error-msg">{fieldErrors.state}</p>}
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Registration Type</label>
        <select className="field-input" value={registrationType} onChange={e => setRegistrationType(e.target.value)}>
          {GST_REGISTRATION_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      <div className="field-group">
        <label className="field-label">Place of Business</label>
        <input
          className="field-input"
          value={placeOfBusiness}
          onChange={e => setPlaceOfBusiness(e.target.value)}
          placeholder="Branch / office address (optional)"
        />
      </div>
    </Modal>
  );
}

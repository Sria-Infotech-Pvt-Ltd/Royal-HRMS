"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { OrgUnit, OrgUnitPayload } from "@/types/orgStructure";

interface Props {
  units: OrgUnit[];
  parentId: string | null;
  onClose: () => void;
  onCreated: (unit: OrgUnit) => void;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function AddUnitModal({ units, parentId, onClose, onCreated }: Props) {
  const [name, setName]           = useState("");
  const [code, setCode]           = useState("");
  const [parent, setParent]       = useState(parentId ?? "");
  const [costCenter, setCostCenter] = useState("");
  const [nameError, setNameError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const parentUnit = units.find(u => u.id === parentId);

  async function submit() {
    if (!name.trim()) { setNameError("Unit name is required."); return; }
    setIsSubmitting(true);
    setSubmitError(null);
    const payload: OrgUnitPayload = {
      name: name.trim(), code: code.trim().toUpperCase(),
      parent: parent || null, cost_center: costCenter.trim().toUpperCase(),
    };
    try {
      const res = await clientApi.post(API.orgStructure.units.list, payload);
      onCreated(res.data.data);
    } catch (err: unknown) {
      setSubmitError((err as { message?: string })?.message ?? "Failed to create org unit.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <Modal
      title={<><i className="ti ti-sitemap" style={{ marginRight: 8 }} />Add org unit</>}
      onClose={onClose}
      maxWidth={460}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <><Spin />&nbsp;Creating…</> : "Create unit"}
          </button>
        </>
      }
    >
      {submitError && (
        <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
          {submitError}
        </div>
      )}
      {parentUnit && (
        <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 14 }}>Under {parentUnit.name}</div>
      )}

      <div className="field-group mb-16">
        <label className="field-label">Unit Name <span style={{ color: "var(--error)" }}>*</span></label>
        <input
          className={`field-input${nameError ? " field-error" : ""}`}
          value={name}
          onChange={e => { setName(e.target.value); setNameError(null); }}
          placeholder="e.g. Basis & Infrastructure"
        />
        {nameError && <p className="field-error-msg">{nameError}</p>}
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Code <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
        <input className="field-input" style={{ fontFamily: "monospace" }} value={code} onChange={e => setCode(e.target.value)} placeholder="BASIS" />
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Parent Unit</label>
        <select className="field-input" value={parent} onChange={e => setParent(e.target.value)}>
          <option value="">None — top level</option>
          {units.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
        </select>
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Cost Center <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
        <input className="field-input" style={{ fontFamily: "monospace" }} value={costCenter} onChange={e => setCostCenter(e.target.value)} placeholder="CC-…" />
      </div>

      <div style={{ fontSize: 11.5, color: "var(--outline)" }}>
        You don&apos;t assign a head here. Add a position next, then mark it chief.
      </div>
    </Modal>
  );
}

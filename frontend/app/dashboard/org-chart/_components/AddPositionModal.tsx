"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import ToggleSwitch from "@/components/ToggleSwitch";
import type { JobTemplate, OrgUnit, Position, PositionPayload } from "@/types/orgStructure";
import type { BranchOption, RoleOption } from "./OrgStructureClient";

interface Props {
  unit: OrgUnit | null;
  jobs: JobTemplate[];
  branches: BranchOption[];
  roles: RoleOption[];
  hasChief: boolean;
  onClose: () => void;
  onCreated: (position: Position) => void;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function AddPositionModal({ unit, jobs, branches, roles, hasChief, onClose, onCreated }: Props) {
  const [title, setTitle]       = useState("");
  const [jobTemplate, setJobTemplate] = useState("");
  const [grade, setGrade]       = useState("");
  const [branch, setBranch]     = useState("");
  const [defaultRole, setDefaultRole] = useState("");
  const [isChief, setIsChief]   = useState(!hasChief);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit() {
    if (!unit) return;
    if (!title.trim()) { setTitleError("Position title is required."); return; }
    setIsSubmitting(true);
    setSubmitError(null);
    const payload: PositionPayload = {
      org_unit: unit.id, job_template: jobTemplate || null,
      title: title.trim(), grade: grade.trim().toUpperCase(), is_chief: isChief,
      branch: branch ? Number(branch) : null,
      default_role: defaultRole ? Number(defaultRole) : null,
    };
    try {
      const res = await clientApi.post(API.orgStructure.positions.list, payload);
      onCreated(res.data.data);
    } catch (err: unknown) {
      setSubmitError((err as { message?: string })?.message ?? "Failed to create position.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!unit) return null;

  return (
    <Modal
      title={<><i className="ti ti-id-badge-2" style={{ marginRight: 8 }} />Add position</>}
      onClose={onClose}
      maxWidth={460}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <><Spin />&nbsp;Creating…</> : "Create position"}
          </button>
        </>
      }
    >
      {submitError && (
        <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
          {submitError}
        </div>
      )}
      <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 14 }}>In {unit.name}</div>

      <div className="field-group mb-16">
        <label className="field-label">Position Title <span style={{ color: "var(--error)" }}>*</span></label>
        <input
          className={`field-input${titleError ? " field-error" : ""}`}
          value={title}
          onChange={e => { setTitle(e.target.value); setTitleError(null); }}
          placeholder="e.g. Senior ABAP Consultant"
        />
        {titleError && <p className="field-error-msg">{titleError}</p>}
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Job Template</label>
        <select className="field-input field-select" value={jobTemplate} onChange={e => setJobTemplate(e.target.value)}>
          <option value="">None</option>
          {jobs.filter(j => j.is_active).map(j => <option key={j.id} value={j.id}>{j.name}{j.band ? ` · ${j.band}` : ""}</option>)}
        </select>
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Grade / Band <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
        <input className="field-input" style={{ fontFamily: "monospace" }} value={grade} onChange={e => setGrade(e.target.value)} placeholder="L4" />
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Company Code <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional — leave unset for a company-wide seat)</span></label>
        <select className="field-input field-select" value={branch} onChange={e => setBranch(e.target.value)}>
          <option value="">Company-wide</option>
          {branches.map(b => <option key={b.id} value={b.id}>{b.branch_name}</option>)}
        </select>
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Default Role <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional — suggested to HR when hiring into this seat)</span></label>
        <select className="field-input field-select" value={defaultRole} onChange={e => setDefaultRole(e.target.value)}>
          <option value="">None</option>
          {roles.map(r => <option key={r.id} value={r.id}>{r.display_name}</option>)}
        </select>
      </div>

      <div className="mb-8">
        <ToggleSwitch
          checked={isChief}
          onChange={checked => setIsChief(checked)}
          label={<>Make this the <b>head</b> of the unit.</>}
        />
      </div>
      <div style={{ fontSize: 11.5, color: "var(--outline)", marginBottom: 16 }}>
        {hasChief ? "This unit already has a chief; turning this on will replace it." : "This unit has no head yet."}
      </div>

      <div style={{ fontSize: 11.5, color: "var(--outline)" }}>
        The position is created <b>vacant</b>. Assign a holder once someone is hired.
      </div>
    </Modal>
  );
}

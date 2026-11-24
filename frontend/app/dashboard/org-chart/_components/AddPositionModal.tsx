"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import { useT } from "@/hooks/useI18n";
import ToggleSwitch from "@/components/ToggleSwitch";
import SearchableSelect from "@/components/SearchableSelect";
import type { JobTemplate, OrgUnit, Position, PositionPayload } from "@/types/orgStructure";
import type { BranchOption } from "./OrgStructureClient";

interface Props {
  unit: OrgUnit | null;
  jobs: JobTemplate[];
  branches: BranchOption[];
  hasChief: boolean;
  onClose: () => void;
  onCreated: (position: Position) => void;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

export default function AddPositionModal({ unit, jobs, branches, hasChief, onClose, onCreated }: Props) {
  const t = useT();
  const [title, setTitle]       = useState("");
  const [jobTemplate, setJobTemplate] = useState("");
  const [grade, setGrade]       = useState("");
  const [branch, setBranch]     = useState("");
  const [isChief, setIsChief]   = useState(!hasChief);
  const [titleError, setTitleError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit() {
    if (!unit) return;
    if (!title.trim()) { setTitleError(t("Position title is required.")); return; }
    setIsSubmitting(true);
    setSubmitError(null);
    const payload: PositionPayload = {
      org_unit: unit.id, job_template: jobTemplate || null,
      title: title.trim(), grade: grade.trim().toUpperCase(), is_chief: isChief,
      branch: branch ? Number(branch) : null,
    };
    try {
      const res = await clientApi.post(API.orgStructure.positions.list, payload);
      onCreated(res.data.data);
    } catch (err: unknown) {
      setSubmitError((err as { message?: string })?.message ?? t("Failed to create position."));
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!unit) return null;

  return (
    <Modal
      title={<><i className="ti ti-id-badge-2" style={{ marginRight: 8 }} />{t("Add position")}</>}
      onClose={onClose}
      maxWidth={460}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>{t("Cancel")}</button>
          <button className="btn btn-filled" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <><Spin />&nbsp;{t("Creating…")}</> : t("Create position")}
          </button>
        </>
      }
    >
      {submitError && (
        <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
          {submitError}
        </div>
      )}
      <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 14 }}>{t("In {name}", { name: unit.name })}</div>

      <div className="field-group mb-16">
        <label className="field-label">{t("Position Title")} <span style={{ color: "var(--error)" }}>*</span></label>
        <input
          className={`field-input${titleError ? " field-error" : ""}`}
          value={title}
          onChange={e => { setTitle(e.target.value); setTitleError(null); }}
          placeholder={t("e.g. Senior ABAP Consultant")}
        />
        {titleError && <p className="field-error-msg">{titleError}</p>}
      </div>

      <div className="field-group mb-16">
        <label className="field-label">{t("Job Template")}</label>
        <SearchableSelect
          value={jobTemplate} onChange={setJobTemplate} placeholder={t("None")}
          options={jobs.filter(j => j.is_active).map(j => ({ value: String(j.id), label: `${j.name}${j.band ? ` · ${j.band}` : ""}` }))}
          inputClassName="field-input"
        />
      </div>

      <div className="field-group mb-16">
        <label className="field-label">{t("Grade / Band")} <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>{t("(optional)")}</span></label>
        <input className="field-input" style={{ fontFamily: "monospace" }} value={grade} onChange={e => setGrade(e.target.value)} placeholder="L4" />
      </div>

      <div className="field-group mb-16">
        <label className="field-label">{t("Company Code")} <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>{t("(optional — leave unset for a company-wide seat)")}</span></label>
        <SearchableSelect
          value={branch} onChange={setBranch} placeholder={t("Company-wide")}
          options={branches.map(b => ({ value: String(b.id), label: b.branch_name }))}
          inputClassName="field-input"
        />
      </div>

      <div className="mb-8">
        <ToggleSwitch
          checked={isChief}
          onChange={checked => setIsChief(checked)}
          label={<>{t("Make this the")} <b>{t("head")}</b> {t("of the unit.")}</>}
        />
      </div>
      <div style={{ fontSize: 11.5, color: "var(--outline)", marginBottom: 16 }}>
        {hasChief ? t("This unit already has a chief; turning this on will replace it.") : t("This unit has no head yet.")}
      </div>

      <div style={{ fontSize: 11.5, color: "var(--outline)" }}>
        {t("The position is created")} <b>{t("vacant")}</b>{t(". Assign a holder once someone is hired.")}
      </div>
    </Modal>
  );
}

"use client";

import type { EducationExperienceFieldConfig } from "@/types/onboardingFieldConfig";
import DocUploadButton, { type HireDocument } from "@/components/DocUploadButton";

// ── Step: Experience ──────────────────────────────────────────────────────────
// A genuinely repeatable, unbounded list of previous employers (unlike
// EducationChecklist's fixed 6-row checklist) — add/remove any number of
// entries. Total Experience (Years) is derived from these entries' date
// ranges (see services_education_experience._compute_total_experience_years)
// and shown read-only — never entered directly. Pure/prop-driven, same
// convention as TabDocuments.tsx.
//
// One overall Save & Continue for the whole step (not a per-entry Save
// button) — add/edit/remove entries here purely updates local state;
// nothing reaches the server until the wizard's own Save & Continue is
// clicked, which then reconciles the whole list in one go (create/update/
// delete as needed). A `temp-` id prefix marks a not-yet-created row (the
// wizard page's own convention); onRemove(id) here is always just a local
// removal.
//
// `is_current` ("I currently work here") is the explicit UI control for
// what the backend still stores as end_date=null — checking it disables
// and clears End Date instead of relying on the employee to just leave it
// blank.

const EMPLOYMENT_TYPES: { value: string; label: string }[] = [
  { value: "full_time",  label: "Full-time" },
  { value: "part_time",  label: "Part-time" },
  { value: "internship", label: "Internship" },
  { value: "contract",   label: "Contract" },
  { value: "freelance",  label: "Freelance" },
];

export interface ExperienceEntry {
  id: string;
  employer_name: string;
  designation: string;
  employment_type: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
  responsibilities: string;
  reason_for_leaving: string;
}

type FieldValue = string | boolean;

interface Props {
  totalExperienceYears: string | null;
  entries: ExperienceEntry[];
  // HR-configured show/require toggles (Settings > Onboarding Fields >
  // Education & Experience) for employment_type/start_date/end_date/
  // responsibilities/reason_for_leaving — Employer and Designation aren't
  // included, they're always shown/optional. Empty array (still loading,
  // or config unavailable) means every field defaults to shown/optional.
  fieldConfig: EducationExperienceFieldConfig[];
  onAdd: () => void;
  onFieldChange: (id: string, field: keyof ExperienceEntry, value: FieldValue) => void;
  onRemove: (id: string) => void;
  error: string | null;
  // Optional — only the Hire wizard passes these today; every other caller
  // of this shared component keeps working exactly as before.
  documents?: HireDocument[];
  uploading?: string | null;
  onUploadDoc?: (documentType: string, file: File, entryRef?: string) => void;
  onDeleteDoc?: (doc: HireDocument) => void;
}

const Req = () => <span style={{ color: "var(--error)", marginLeft: 2 }}>*</span>;

export default function ExperienceList({
  totalExperienceYears, entries, fieldConfig, onAdd, onFieldChange, onRemove, error,
  documents, uploading, onUploadDoc, onDeleteDoc,
}: Props) {
  function isVisible(key: string): boolean {
    return fieldConfig.find(c => c.field_key === key)?.visible ?? true;
  }
  function isRequired(key: string): boolean {
    return fieldConfig.find(c => c.field_key === key)?.required ?? false;
  }

  return (
    <div>
      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      <div className="field-group" style={{ maxWidth: 260, marginBottom: 8 }}>
        <label className="field-label">Total Experience (Years)</label>
        <div className="field-input" style={{ background: "var(--bg-low)", color: "var(--on-variant)" }}>
          {totalExperienceYears ?? "—"}
        </div>
      </div>
      <p style={{ color: "var(--on-variant)", fontSize: ".85rem", marginBottom: 20 }}>
        Calculated automatically from the employment dates below. Fresher with no prior work experience? Leave this whole step blank and click Save &amp; Continue.
      </p>

      {entries.length === 0 && (
        <p style={{ color: "var(--on-variant)", fontSize: ".9rem", marginBottom: 16 }}>
          No previous employers added yet — optional, but add any you have.
        </p>
      )}

      {entries.map(entry => {
        const key = entry.id;
        return (
          <div key={key} style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: "14px 16px", marginBottom: 14 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
              <span className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--on-variant)" }}>Experience</span>
              <button className="btn btn-ghost btn-sm" type="button" onClick={() => onRemove(entry.id)} style={{ color: "var(--error)" }}>
                Remove
              </button>
            </div>
            <div className="form-row cols-2">
              <div className="field-group">
                <label className="field-label">Employer</label>
                <input className="field-input" value={entry.employer_name} onChange={e => onFieldChange(entry.id, "employer_name", e.target.value)} />
              </div>
              <div className="field-group">
                <label className="field-label">Designation</label>
                <input className="field-input" value={entry.designation} onChange={e => onFieldChange(entry.id, "designation", e.target.value)} />
              </div>
              {isVisible("employment_type") && (
                <div className="field-group">
                  <label className="field-label">Employment Type{isRequired("employment_type") && <Req />}</label>
                  <select
                    className="field-input field-select"
                    value={entry.employment_type}
                    onChange={e => onFieldChange(entry.id, "employment_type", e.target.value)}
                  >
                    <option value="">— Select —</option>
                    {EMPLOYMENT_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                  </select>
                </div>
              )}
              {isVisible("start_date") && (
                <div className="field-group">
                  <label className="field-label">Start Date{isRequired("start_date") && <Req />}</label>
                  <input className="field-input" type="date" value={entry.start_date} onChange={e => onFieldChange(entry.id, "start_date", e.target.value)} />
                </div>
              )}
              {isVisible("end_date") && (
                <div className="field-group">
                  <label className="field-label">Last working day{isRequired("end_date") && !entry.is_current && <Req />}</label>
                  <input
                    className="field-input" type="date"
                    value={entry.end_date}
                    disabled={entry.is_current}
                    onChange={e => onFieldChange(entry.id, "end_date", e.target.value)}
                    style={entry.is_current ? { background: "var(--bg-low)", color: "var(--on-variant)" } : undefined}
                  />
                  <div className="hint">Actual, or expected if serving notice.</div>
                </div>
              )}
            </div>

            <label className="module-check" style={{ marginTop: 4, marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="checkbox"
                checked={entry.is_current}
                onChange={e => onFieldChange(entry.id, "is_current", e.target.checked)}
              />
              <span>I currently work here</span>
            </label>

            {isVisible("responsibilities") && (
              <div className="field-group" style={{ marginBottom: 12 }}>
                <label className="field-label">Key Responsibilities{isRequired("responsibilities") && <Req />}</label>
                <textarea className="field-input" rows={2} value={entry.responsibilities} onChange={e => onFieldChange(entry.id, "responsibilities", e.target.value)} />
              </div>
            )}
            {isVisible("reason_for_leaving") && (
              <div className="field-group" style={{ marginBottom: 12 }}>
                <label className="field-label">Reason for Leaving{isRequired("reason_for_leaving") && <Req />}</label>
                <textarea className="field-input" rows={2} value={entry.reason_for_leaving} onChange={e => onFieldChange(entry.id, "reason_for_leaving", e.target.value)} />
              </div>
            )}

            {onUploadDoc && (
              <div>
                <DocUploadButton
                  documentType="experience_letter"
                  label="experience letter"
                  entryRef={entry.id}
                  existing={documents?.find(d => d.document_type === "experience_letter" && d.entry_ref === entry.id)}
                  uploading={uploading === `experience_letter:${entry.id}`}
                  onUpload={onUploadDoc}
                  onDelete={onDeleteDoc}
                />
              </div>
            )}
          </div>
        );
      })}

      <button className="btn btn-ghost" type="button" onClick={onAdd}>
        <i className="ti ti-plus" /> Add Previous Employer
      </button>
    </div>
  );
}

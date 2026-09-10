"use client";

import { useState } from "react";
import type { EducationExperienceFieldConfig } from "@/types/onboardingFieldConfig";

// ── Step: Education ──────────────────────────────────────────────────────────
// A genuinely repeatable, unbounded list of qualifications (two Bachelor's
// degrees, two "Other" certifications — all valid), same structure as
// ExperienceList.tsx: "+ Add Education" always adds a blank card; Type is
// just the first field inside it, not a gate you pick before the card
// appears. Picking "Other" reveals a free-text label for anything not in
// the standard list (a professional certification, etc.). Institution/
// Percentage/date-range mirrors what real HRMS tools (Keka) show on an
// employee's Education card. Pure/prop-driven, same convention as
// TabDocuments.tsx.
//
// One overall Save & Continue for the whole step (not a per-entry Save
// button) — add/edit/remove entries here purely updates local state;
// nothing reaches the server until the wizard's own Save & Continue is
// clicked, which then reconciles the whole list in one go (create/update/
// delete as needed). A `temp-` id prefix marks a not-yet-created row (the
// wizard page's own convention); onRemove(id) here is always just a local
// removal — the wizard page decides whether that also means "delete this
// on the server" when it reconciles. Mirrors ExperienceList.tsx exactly.

const EDUCATION_LEVELS: { value: string; label: string }[] = [
  { value: "ssc",          label: "SSC / 10th" },
  { value: "intermediate", label: "Intermediate / 12th" },
  { value: "diploma",      label: "Diploma" },
  { value: "bachelors",    label: "Bachelor's" },
  { value: "masters",      label: "Master's" },
  { value: "doctorate",    label: "Doctorate" },
  { value: "other",        label: "Other" },
];

// Common streams/majors for each level, so Specialization is a dropdown
// instead of free text where a sensible standard list exists — "Other"
// always included so nothing gets forced into a wrong bucket. Levels with
// no common standard list (SSC has no stream; Doctorate/Other are too
// varied) keep a plain free-text Specialization input instead.
const SPECIALIZATIONS_BY_LEVEL: Record<string, string[]> = {
  intermediate: [
    "MPC (Maths, Physics, Chemistry)", "BiPC (Biology, Physics, Chemistry)",
    "MEC (Maths, Economics, Commerce)", "CEC (Commerce, Economics, Civics)",
    "Arts / Humanities", "Other",
  ],
  diploma: [
    "Mechanical Engineering", "Civil Engineering", "Electrical Engineering",
    "Electronics & Communication", "Computer Science", "Information Technology",
    "Automobile Engineering", "Other",
  ],
  bachelors: [
    "Computer Science", "Information Technology", "Electronics & Communication",
    "Electrical Engineering", "Mechanical Engineering", "Civil Engineering",
    "Commerce", "Economics", "Business Administration", "Arts / Humanities",
    "Science", "Law", "Other",
  ],
  masters: [
    "Computer Science", "Information Technology", "Business Administration (MBA)",
    "Commerce", "Economics", "Engineering (M.Tech)", "Science (M.Sc)",
    "Arts (M.A.)", "Law (LLM)", "Other",
  ],
};

export interface EducationEntry {
  id: string;
  level: string;
  custom_level_label: string;
  institution: string;
  specialization: string;
  percentage: string;
  start_date: string;
  end_date: string;
}

interface Props {
  entries: EducationEntry[];
  // HR-configured show/require toggles (Settings > Onboarding Fields >
  // Education & Experience) for specialization/percentage/start_date/
  // end_date — Level and Institution aren't included, they're always
  // shown/required. Empty array (still loading, or config unavailable)
  // means every field defaults to shown/optional — never hides a field
  // due to a slow/failed fetch.
  fieldConfig: EducationExperienceFieldConfig[];
  onAdd: () => void;
  onFieldChange: (id: string, field: keyof EducationEntry, value: string) => void;
  onRemove: (id: string) => void;
  error: string | null;
}

const Req = () => <span style={{ color: "var(--error)", marginLeft: 2 }}>*</span>;

export default function EducationChecklist({ entries, fieldConfig, onAdd, onFieldChange, onRemove, error }: Props) {
  // Local-only UI state: which entries currently have "Other" picked in
  // the Specialization dropdown (so the free-text box under it stays open
  // even while that text box is empty) — not part of EducationEntry itself
  // since it's just a display toggle, not data.
  const [customSpecIds, setCustomSpecIds] = useState<Set<string>>(new Set());

  function isVisible(key: string): boolean {
    return fieldConfig.find(c => c.field_key === key)?.visible ?? true;
  }
  function isRequired(key: string): boolean {
    return fieldConfig.find(c => c.field_key === key)?.required ?? false;
  }

  function handleSpecializationChange(id: string, value: string) {
    if (value === "Other") {
      setCustomSpecIds(prev => new Set(prev).add(id));
      onFieldChange(id, "specialization", "");
    } else {
      setCustomSpecIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
      onFieldChange(id, "specialization", value);
    }
  }

  return (
    <div>
      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      <p style={{ color: "var(--on-variant)", marginBottom: "1.25rem", fontSize: ".9rem", lineHeight: 1.6 }}>
        Add each qualification you&apos;ve completed — at least one is required before you can submit.
      </p>

      {entries.length === 0 && (
        <p style={{ color: "var(--on-variant)", fontSize: ".9rem", marginBottom: 16 }}>
          No education added yet — click below to add your first one.
        </p>
      )}

      {entries.map(entry => {
        const key = entry.id;
        return (
          <div key={key} style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: "14px 16px", marginBottom: 14 }}>
            <div className="form-row cols-2">
              <div className="field-group">
                <label className="field-label">Education Level</label>
                <select className="field-input field-select" value={entry.level} onChange={e => onFieldChange(entry.id, "level", e.target.value)}>
                  <option value="" disabled>Select…</option>
                  {EDUCATION_LEVELS.map(l => <option key={l.value} value={l.value}>{l.label}</option>)}
                </select>
              </div>
              {entry.level === "other" && (
                <div className="field-group">
                  <label className="field-label">Name it</label>
                  <input
                    className="field-input" placeholder="e.g. PMP Certification"
                    value={entry.custom_level_label}
                    onChange={e => onFieldChange(entry.id, "custom_level_label", e.target.value)}
                  />
                </div>
              )}
              <div className="field-group">
                <label className="field-label">Institution</label>
                <input className="field-input" value={entry.institution} onChange={e => onFieldChange(entry.id, "institution", e.target.value)} />
              </div>
              {isVisible("specialization") && (() => {
                const list = SPECIALIZATIONS_BY_LEVEL[entry.level];
                if (!list) {
                  return (
                    <div className="field-group">
                      <label className="field-label">Specialization{isRequired("specialization") && <Req />}</label>
                      <input className="field-input" value={entry.specialization} onChange={e => onFieldChange(entry.id, "specialization", e.target.value)} />
                    </div>
                  );
                }
                const matchesList = list.includes(entry.specialization);
                const showCustom = customSpecIds.has(entry.id) || (entry.specialization !== "" && !matchesList);
                const selectValue = matchesList ? entry.specialization : (showCustom ? "Other" : "");
                return (
                  <>
                    <div className="field-group">
                      <label className="field-label">Specialization{isRequired("specialization") && <Req />}</label>
                      <select className="field-input field-select" value={selectValue} onChange={e => handleSpecializationChange(entry.id, e.target.value)}>
                        <option value="">Select…</option>
                        {list.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
                    {showCustom && (
                      <div className="field-group">
                        <label className="field-label">Specify Specialization</label>
                        <input
                          className="field-input" placeholder="e.g. Robotics"
                          value={entry.specialization}
                          onChange={e => onFieldChange(entry.id, "specialization", e.target.value)}
                        />
                      </div>
                    )}
                  </>
                );
              })()}
              {isVisible("percentage") && (
                <div className="field-group">
                  <label className="field-label">Percentage / Grade{isRequired("percentage") && <Req />}</label>
                  <input className="field-input" placeholder="e.g. 85% or 8.5 CGPA" value={entry.percentage} onChange={e => onFieldChange(entry.id, "percentage", e.target.value)} />
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
                  <label className="field-label">End Date{isRequired("end_date") && <Req />}</label>
                  <input className="field-input" type="date" value={entry.end_date} onChange={e => onFieldChange(entry.id, "end_date", e.target.value)} />
                </div>
              )}
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              <button className="btn btn-ghost btn-sm" type="button" onClick={() => onRemove(entry.id)}>
                <i className="ti ti-trash" style={{ fontSize: 13 }} /> Remove
              </button>
            </div>
          </div>
        );
      })}

      <button className="btn btn-ghost" type="button" onClick={onAdd}>
        <i className="ti ti-plus" /> Add Education
      </button>
    </div>
  );
}

"use client";

// ── Step: Family & Nomination ────────────────────────────────────────────────
// Two related repeatable lists in one step, matching the mockup's own
// combined "Family & nomination" screen: Family Members (dependants) and
// EPF/Gratuity Nominees. A nominee is picked from the family list rather
// than re-typed — same "richer source, not re-entered" idea used elsewhere
// in this app — so the nominee dropdown is built from `familyEntries`, not
// a separate free-text field.
//
// One overall Save & Continue for the whole step (same convention as
// EducationChecklist/ExperienceList) — everything here is local state until
// the wizard's own Save & Continue reconciles both lists at once. Family is
// always reconciled BEFORE nominees (see saveFamilyNominationEntries() in
// both wizard pages) so a nominee referencing a not-yet-created (`temp-`)
// family member gets translated to the real id the family save just
// returned, before the nominee list is sent.
//
// No server-side block on a nomination scheme's shares not summing to
// 100% (matches the mockup, which only ever displays that total) — the
// running total below is informational, not a gate.

export interface FamilyEntry {
  id: string;
  name: string;
  relationship: string;
  date_of_birth: string;
  gender: string;
  blood_group: string;
  is_dependent: boolean;
}

export interface NomineeEntry {
  id: string;
  family_member: string; // FamilyEntry.id — may be a temp- id until saved
  scheme: string;
  share_percentage: string;
}

const RELATIONSHIPS = ["father", "mother", "spouse", "child", "sibling"];
const RELATIONSHIP_LABELS: Record<string, string> = {
  father: "Father", mother: "Mother", spouse: "Spouse", child: "Child", sibling: "Sibling",
};
const SCHEMES: { value: string; label: string }[] = [
  { value: "epf_eps",  label: "EPF + EPS" },
  { value: "gratuity", label: "Gratuity" },
  { value: "both",     label: "Both" },
];

type FamilyFieldValue = string | boolean;

interface Props {
  familyEntries: FamilyEntry[];
  nomineeEntries: NomineeEntry[];
  onAddFamily: () => void;
  onFamilyFieldChange: (id: string, field: keyof FamilyEntry, value: FamilyFieldValue) => void;
  onRemoveFamily: (id: string) => void;
  onAddNominee: () => void;
  onNomineeFieldChange: (id: string, field: keyof NomineeEntry, value: string) => void;
  onRemoveNominee: (id: string) => void;
  error: string | null;
}

export default function FamilyNominationStep({
  familyEntries, nomineeEntries, onAddFamily, onFamilyFieldChange, onRemoveFamily,
  onAddNominee, onNomineeFieldChange, onRemoveNominee, error,
}: Props) {
  const totalsByScheme = SCHEMES.reduce<Record<string, number>>((acc, s) => {
    acc[s.value] = nomineeEntries
      .filter(n => n.scheme === s.value)
      .reduce((sum, n) => sum + (Number(n.share_percentage) || 0), 0);
    return acc;
  }, {});

  return (
    <div>
      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      <h4 style={{ fontSize: "0.95rem", marginBottom: 4 }}>Family Members</h4>
      <p style={{ color: "var(--on-variant)", fontSize: ".85rem", marginBottom: 16 }}>
        Add family before setting nominations below — a nominee is picked from this list.
      </p>

      {familyEntries.length === 0 && (
        <p style={{ color: "var(--on-variant)", fontSize: ".9rem", marginBottom: 16 }}>
          No family members added yet — optional, but add any dependants or nominees-to-be.
        </p>
      )}

      {familyEntries.map(entry => (
        <div key={entry.id} style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: "14px 16px", marginBottom: 14 }}>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Name</label>
              <input className="field-input" value={entry.name} onChange={e => onFamilyFieldChange(entry.id, "name", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Relationship</label>
              <select className="field-input field-select" value={entry.relationship} onChange={e => onFamilyFieldChange(entry.id, "relationship", e.target.value)}>
                <option value="">— Select —</option>
                {RELATIONSHIPS.map(r => <option key={r} value={r}>{RELATIONSHIP_LABELS[r]}</option>)}
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Date of Birth</label>
              <input className="field-input" type="date" value={entry.date_of_birth} onChange={e => onFamilyFieldChange(entry.id, "date_of_birth", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Gender</label>
              <select className="field-input field-select" value={entry.gender} onChange={e => onFamilyFieldChange(entry.id, "gender", e.target.value)}>
                <option value="">— Select —</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Blood Group</label>
              <input className="field-input" value={entry.blood_group} onChange={e => onFamilyFieldChange(entry.id, "blood_group", e.target.value)} placeholder="e.g. O+" />
            </div>
          </div>
          <label className="module-check" style={{ marginTop: 4, marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
            <input type="checkbox" checked={entry.is_dependent} onChange={e => onFamilyFieldChange(entry.id, "is_dependent", e.target.checked)} />
            <span>Dependent</span>
          </label>
          <button className="btn btn-ghost btn-sm" type="button" onClick={() => onRemoveFamily(entry.id)}>
            <i className="ti ti-trash" style={{ fontSize: 13 }} /> Remove
          </button>
        </div>
      ))}

      <button className="btn btn-ghost" type="button" onClick={onAddFamily} style={{ marginBottom: 24 }}>
        <i className="ti ti-plus" /> Add Family Member
      </button>

      <div style={{ borderTop: "1px solid var(--outline-v)", paddingTop: 20 }}>
        <h4 style={{ fontSize: "0.95rem", marginBottom: 4 }}>EPF / Gratuity Nomination</h4>
        <p style={{ color: "var(--on-variant)", fontSize: ".85rem", marginBottom: 16 }}>
          Each scheme&apos;s shares should add up to 100% across all nominees.
        </p>

        {familyEntries.length === 0 && (
          <p style={{ color: "var(--warn)", fontSize: ".85rem", marginBottom: 16 }}>
            Add a family member above before adding a nominee.
          </p>
        )}

        {nomineeEntries.map(entry => (
          <div key={entry.id} style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: "14px 16px", marginBottom: 14 }}>
            <div className="form-row cols-2">
              <div className="field-group">
                <label className="field-label">Nominee</label>
                <select className="field-input field-select" value={entry.family_member} onChange={e => onNomineeFieldChange(entry.id, "family_member", e.target.value)}>
                  <option value="">— Select from family —</option>
                  {familyEntries.map(f => (
                    <option key={f.id} value={f.id}>{f.name}{f.relationship ? ` (${RELATIONSHIP_LABELS[f.relationship] ?? f.relationship})` : ""}</option>
                  ))}
                </select>
              </div>
              <div className="field-group">
                <label className="field-label">Scheme</label>
                <select className="field-input field-select" value={entry.scheme} onChange={e => onNomineeFieldChange(entry.id, "scheme", e.target.value)}>
                  {SCHEMES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
              <div className="field-group">
                <label className="field-label">Share %</label>
                <input
                  className="field-input" type="number" min={0} max={100}
                  value={entry.share_percentage}
                  onChange={e => onNomineeFieldChange(entry.id, "share_percentage", e.target.value.replace(/[^0-9]/g, ""))}
                />
              </div>
            </div>
            <button className="btn btn-ghost btn-sm" type="button" onClick={() => onRemoveNominee(entry.id)}>
              <i className="ti ti-trash" style={{ fontSize: 13 }} /> Remove
            </button>
          </div>
        ))}

        <button className="btn btn-ghost" type="button" onClick={onAddNominee} disabled={familyEntries.length === 0}>
          <i className="ti ti-plus" /> Add Nominee
        </button>

        {nomineeEntries.length > 0 && (
          <p style={{ marginTop: 12, fontSize: ".85rem", color: "var(--on-variant)" }}>
            {SCHEMES.map(s => `${s.label}: ${totalsByScheme[s.value]}%`).join(" · ")}
          </p>
        )}
      </div>
    </div>
  );
}

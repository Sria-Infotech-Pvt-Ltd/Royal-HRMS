"use client";

// One family member as a card. Closed, it is a one-line summary (initials, name, relationship, age, Dependent / Nominee tags);
// open, it shows the editable fields. A card with no name yet always stays open so a new entry is ready to type into.

import { useId } from "react";
import DateInput from "@/components/shared/DateInput";
import { BLOOD_GROUPS, RELATIONSHIPS, RELATIONSHIP_LABELS, type FamilyEntry } from "./familyNominationTypes";
import { ageInYears, initialsOf } from "./nominationRules";

interface Props {
  entry: FamilyEntry;
  isOpen: boolean;
  /** This person is already picked as a nominee somewhere below. */
  isNominee: boolean;
  /** A short warning for the card, for example that another father is already listed. */
  roleNote: string | null;
  onToggle: () => void;
  onChange: (field: keyof FamilyEntry, value: string | boolean) => void;
  onRemove: () => void;
}

const TAG: React.CSSProperties = { fontSize: 11, fontWeight: 600, padding: "2px 8px", borderRadius: 999, background: "var(--surface-2, #f3f4f6)", color: "var(--ink-2, #374151)" };

export default function FamilyMemberCard({ entry, isOpen, isNominee, roleNote, onToggle, onChange, onRemove }: Props) {
  const uid = useId();
  const name = entry.name.trim();
  const age = ageInYears(entry.date_of_birth);
  const showForm = isOpen || name === "";
  const field = (key: string) => `${uid}-${key}`;
  return (
    <section aria-label={`Family member: ${name || "new"}`} style={{ border: "1px solid var(--line, #e5e7eb)", borderRadius: 12, background: "var(--surface, #fff)", padding: "12px 14px" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <div aria-hidden="true" style={{ width: 38, height: 38, borderRadius: "50%", display: "grid", placeItems: "center", fontWeight: 700, fontSize: 13, background: "var(--brand-soft, #ede9fe)", color: "var(--brand, #6d28d9)" }}>
          {initialsOf(name)}
        </div>
        <div style={{ flex: "1 1 180px", minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: name ? "var(--ink)" : "var(--muted)" }}>{name || "New family member"}</div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 4 }}>
            {entry.relationship && <span style={TAG}>{RELATIONSHIP_LABELS[entry.relationship] ?? entry.relationship}</span>}
            {age !== null && <span style={TAG}>{age} {age === 1 ? "yr" : "yrs"}</span>}
            {entry.is_dependent && <span style={TAG}>Dependent</span>}
            {isNominee && <span style={{ ...TAG, background: "var(--brand-soft, #ede9fe)", color: "var(--brand, #6d28d9)" }}>Nominee</span>}
          </div>
          {roleNote && <div role="note" style={{ fontSize: 11.5, color: "var(--warn, #b45309)", marginTop: 4 }}>{roleNote}</div>}
        </div>
        {name !== "" && (
          <button type="button" className="rvbtn" aria-expanded={isOpen} aria-label={`${isOpen ? "Close" : "Edit"} ${name}`} onClick={onToggle}>
            {isOpen ? "Done" : "Edit"}
          </button>
        )}
        <button type="button" className="rvbtn ghost" aria-label={`Remove ${name || "this family member"}`} onClick={onRemove}>
          <i className="ti ti-trash" aria-hidden="true" />
        </button>
      </div>

      {showForm && (
        <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 12 }}>
          <div className="field-group">
            <label className="field-label" htmlFor={field("name")}>Name</label>
            <input id={field("name")} className="field-input" value={entry.name} onChange={event => onChange("name", event.target.value)} />
          </div>
          <div className="field-group">
            <label className="field-label" htmlFor={field("relationship")}>Relationship</label>
            <select id={field("relationship")} className="field-input field-select" value={entry.relationship} onChange={event => onChange("relationship", event.target.value)}>
              <option value="">— Select —</option>
              {RELATIONSHIPS.map(relationship => <option key={relationship} value={relationship}>{RELATIONSHIP_LABELS[relationship]}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">Date of birth</label>
            <DateInput separator="-" className="field-input" value={entry.date_of_birth} onChange={isoDate => onChange("date_of_birth", isoDate)} />
          </div>
          <div className="field-group">
            <label className="field-label" htmlFor={field("gender")}>Gender</label>
            <select id={field("gender")} className="field-input field-select" value={entry.gender} onChange={event => onChange("gender", event.target.value)}>
              <option value="">— Select —</option>
              <option value="male">Male</option>
              <option value="female">Female</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div className="field-group">
            <label className="field-label" htmlFor={field("blood")}>Blood group</label>
            {/* The same fixed list as Personal identity: free text let typos and non-standard values through (QA report #56). */}
            <select id={field("blood")} className="field-input field-select" value={entry.blood_group} onChange={event => onChange("blood_group", event.target.value)}>
              <option value="">— Select —</option>
              {BLOOD_GROUPS.map(group => <option key={group} value={group}>{group}</option>)}
            </select>
          </div>
          <label style={{ display: "flex", alignItems: "center", gap: 8, alignSelf: "end", fontSize: 13.5, paddingBottom: 8 }}>
            <input type="checkbox" checked={entry.is_dependent} onChange={event => onChange("is_dependent", event.target.checked)} />
            Dependent on the employee
          </label>
        </div>
      )}
    </section>
  );
}

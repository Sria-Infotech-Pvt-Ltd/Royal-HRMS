"use client";

// One nomination scheme (EPF + EPS, Gratuity, Both): a bar showing how much of the 100% is assigned, one row per nominee picked from
// the family list, and quick actions (add, split equally, fill the rest). The bar is guidance only; a scheme over 100% is what the
// Review step refuses, and a scheme under 100% is allowed.

import { RELATIONSHIP_LABELS, type FamilyEntry, type NomineeEntry } from "./familyNominationTypes";
import { equalShares, isMinor, remainingFor, schemeState, type SchemeState } from "./nominationRules";

interface Props {
  scheme: { value: string; label: string; hint: string };
  /** The nominees of THIS scheme only. */
  nominees: NomineeEntry[];
  /** Every nominee, so "fill the rest" can see what the other nominees of the scheme already hold. */
  allNominees: NomineeEntry[];
  total: number;
  members: FamilyEntry[];
  canAdd: boolean;
  onAdd: () => void;
  onField: (id: string, field: keyof NomineeEntry, value: string) => void;
  onRemove: (id: string) => void;
}

const BAR_COLOUR: Record<SchemeState, string> = {
  empty: "var(--line, #e5e7eb)", short: "var(--warn, #d97706)", complete: "var(--success, #16a34a)", over: "var(--crit, #dc2626)",
};

function statusText(state: SchemeState, total: number): string {
  if (state === "empty") return "No nominee yet";
  if (state === "complete") return "Complete: 100%";
  if (state === "over") return `Over by ${total - 100}%: lower a share`;
  return `${100 - total}% still to assign`;
}

function memberLabel(member: FamilyEntry): string {
  const name = member.name.trim() || "Unnamed member";
  return member.relationship ? `${name} (${RELATIONSHIP_LABELS[member.relationship] ?? member.relationship})` : name;
}

export default function NominationLane({ scheme, nominees, allNominees, total, members, canAdd, onAdd, onField, onRemove }: Props) {
  const state = schemeState(total, nominees.length);
  const shares = equalShares(nominees.length);
  return (
    <section aria-label={`${scheme.label} nomination`} style={{ border: "1px solid var(--line, #e5e7eb)", borderRadius: 12, background: "var(--surface, #fff)", padding: "12px 14px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
        <div><b style={{ fontSize: 14 }}>{scheme.label}</b> <span style={{ fontSize: 12, color: "var(--muted)" }}>{scheme.hint}</span></div>
        <span role="status" style={{ fontSize: 12, fontWeight: 600, color: state === "empty" ? "var(--muted)" : BAR_COLOUR[state] }}>{statusText(state, total)}</span>
      </div>
      <div role="progressbar" aria-label={`${scheme.label} shares assigned`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.min(total, 100)}
        style={{ height: 8, borderRadius: 999, background: "var(--surface-2, #f3f4f6)", margin: "10px 0 12px", overflow: "hidden" }}>
        <div style={{ width: `${Math.min(total, 100)}%`, height: "100%", background: BAR_COLOUR[state], transition: "width .2s" }} />
      </div>

      {nominees.map(nominee => {
        const picked = members.find(member => member.id === nominee.family_member);
        const rest = remainingFor(allNominees, scheme.value, nominee.id);
        return (
          <div key={nominee.id} style={{ marginBottom: 10 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
              <select aria-label={`${scheme.label} nominee`} className="field-input field-select" style={{ flex: "1 1 220px" }} value={nominee.family_member}
                onChange={event => onField(nominee.id, "family_member", event.target.value)}>
                <option value="">— Select from family —</option>
                {members.map(member => (
                  <option key={member.id} value={member.id} disabled={nominees.some(other => other.id !== nominee.id && other.family_member === member.id)}>{memberLabel(member)}</option>
                ))}
              </select>
              <input aria-label={`${scheme.label} share for ${picked?.name.trim() || "this nominee"}`} className="field-input" type="number" min={0} max={100} style={{ width: 84 }}
                value={nominee.share_percentage} onChange={event => onField(nominee.id, "share_percentage", event.target.value.replace(/[^0-9]/g, ""))} />
              <span aria-hidden="true" style={{ fontSize: 13, color: "var(--muted)" }}>%</span>
              {rest > 0 && Number(nominee.share_percentage) !== rest && (
                <button type="button" className="rvbtn" onClick={() => onField(nominee.id, "share_percentage", String(rest))}>Fill the rest ({rest}%)</button>
              )}
              <button type="button" className="rvbtn ghost" aria-label={`Remove ${scheme.label} nominee ${picked?.name.trim() || ""}`.trim()} onClick={() => onRemove(nominee.id)}>
                <i className="ti ti-trash" aria-hidden="true" />
              </button>
            </div>
            {picked && isMinor(picked.date_of_birth) && (
              <div role="note" style={{ fontSize: 11.5, color: "var(--warn, #b45309)", marginTop: 4 }}>
                {picked.name.trim() || "This person"} is under 18. Check whether a guardian must be named for a minor nominee.
              </div>
            )}
          </div>
        );
      })}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="rvbtn" disabled={!canAdd} title={canAdd ? undefined : "Add a family member with a name first"} onClick={onAdd}>
          <i className="ti ti-plus" aria-hidden="true" /> Add nominee
        </button>
        {nominees.length > 1 && (
          <button type="button" className="rvbtn ghost" onClick={() => nominees.forEach((nominee, index) => onField(nominee.id, "share_percentage", String(shares[index])))}>
            Split equally
          </button>
        )}
      </div>
    </section>
  );
}

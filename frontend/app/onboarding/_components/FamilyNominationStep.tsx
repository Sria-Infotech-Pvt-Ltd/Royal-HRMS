"use client";

// ── Step: Family & Nomination ────────────────────────────────────────────────
// Two related lists in one step: family members (people cards) and EPF / Gratuity nominees (one lane per scheme). A nominee is
// picked from the family list, never re-typed, so a person is added once and used wherever needed.
//
// The props are unchanged from the earlier version (the Hire wizard, the HR-assisted onboarding page and Edit Record all use them):
// everything is local state until the wizard's own Save & Continue reconciles both lists at once, family always BEFORE nominees
// (see saveFamilyNominationEntries() in both wizard pages) so a nominee pointing at a not-yet-created (`temp-`) family member
// gets the real id first. No rule here blocks saving: the share totals are guidance; the Review step refuses only a scheme over 100%.
//
// The quick-add buttons call the same onAddFamily / onAddNominee as before (they take no arguments), then set the relationship or
// scheme on the entry that just appeared, so no caller had to change.

import { useEffect, useRef, useState } from "react";
import { useT } from "@/hooks/useI18n";
import FamilyMemberCard from "./FamilyMemberCard";
import NominationLane from "./NominationLane";
import { RELATIONSHIPS, RELATIONSHIP_LABELS, SCHEMES, type FamilyEntry, type NomineeEntry } from "./familyNominationTypes";
import { duplicateRoleIds, namedMembers, presetFor, schemeState, schemeTotal, sharesIn } from "./nominationRules";

export type { FamilyEntry, NomineeEntry } from "./familyNominationTypes";

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

const PILL: React.CSSProperties = { fontSize: 12, fontWeight: 600, padding: "4px 10px", borderRadius: 999, background: "var(--surface-2, #f3f4f6)", color: "var(--ink-2, #374151)" };
const DOT: Record<string, string> = { short: "var(--warn, #d97706)", complete: "var(--success, #16a34a)", over: "var(--crit, #dc2626)" };

export default function FamilyNominationStep({
  familyEntries, nomineeEntries, onAddFamily, onFamilyFieldChange, onRemoveFamily, onAddNominee, onNomineeFieldChange, onRemoveNominee, error,
}: Props) {
  const t = useT();
  // Cards the person has opened. A card with no name is always open, and one that already has a name starts closed.
  const [openIds, setOpenIds] = useState<ReadonlySet<string>>(new Set());

  // What a quick-add button wants the NEXT new entry to look like, applied once that entry shows up in the list.
  const pendingFamily = useRef<Partial<FamilyEntry> | null>(null);
  const pendingScheme = useRef<string | null>(null);
  const knownFamily = useRef<Set<string>>(new Set(familyEntries.map(entry => entry.id)));
  const knownNominees = useRef<Set<string>>(new Set(nomineeEntries.map(entry => entry.id)));
  useEffect(() => {
    const fresh = familyEntries.filter(entry => !knownFamily.current.has(entry.id));
    knownFamily.current = new Set(familyEntries.map(entry => entry.id));
    const preset = pendingFamily.current;
    if (preset && fresh.length === 1) {
      pendingFamily.current = null;
      for (const [field, value] of Object.entries(preset)) onFamilyFieldChange(fresh[0].id, field as keyof FamilyEntry, value as string); // a preset only holds strings
    }
  }, [familyEntries, onFamilyFieldChange]);
  useEffect(() => {
    const fresh = nomineeEntries.filter(entry => !knownNominees.current.has(entry.id));
    knownNominees.current = new Set(nomineeEntries.map(entry => entry.id));
    const scheme = pendingScheme.current;
    if (scheme && fresh.length === 1) {
      pendingScheme.current = null;
      onNomineeFieldChange(fresh[0].id, "scheme", scheme);
    }
  }, [nomineeEntries, onNomineeFieldChange]);

  const people = namedMembers(familyEntries);
  // Set when someone presses Add nominee with nobody to nominate yet: the note below turns into a clear instruction.
  const [wasBlocked, setWasBlocked] = useState(false);
  const familySection = useRef<HTMLDivElement | null>(null);
  const nominatedIds = new Set(nomineeEntries.map(nominee => nominee.family_member).filter(Boolean));
  const selectable = familyEntries.filter(entry => entry.name.trim() !== "" || nominatedIds.has(entry.id));
  const duplicates = duplicateRoleIds(familyEntries);
  const dependants = people.filter(entry => entry.is_dependent).length;

  function quickAdd(relationship?: string) {
    pendingFamily.current = relationship ? presetFor(relationship) : null;
    onAddFamily();
  }
  /** Add nominee pressed with no named family member: say why, make sure there is a card to type into, and go up to the family list. */
  function nomineeBlocked() {
    setWasBlocked(true);
    if (familyEntries.length === 0) quickAdd();
    familySection.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  function addNominee(scheme: string) {
    pendingScheme.current = scheme;
    onAddNominee();
  }
  function changeFamily(id: string, field: keyof FamilyEntry, value: FamilyFieldValue) {
    setOpenIds(previous => (previous.has(id) ? previous : new Set(previous).add(id)));   // typing in a card keeps it open
    onFamilyFieldChange(id, field, value);
  }
  function toggle(id: string, isOpen: boolean) {
    setOpenIds(previous => {
      const next = new Set(previous);
      if (isOpen) next.delete(id); else next.add(id);
      return next;
    });
  }

  return (
    <div style={{ display: "grid", gap: 18 }}>
      {error && <div className="alert alert-error">{error}</div>}

      <div role="status" aria-label={t("Summary")} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <span style={PILL}>{people.length === 1 ? t("{count} family member", { count: people.length }) : t("{count} family members", { count: people.length })}</span>
        <span style={PILL}>{dependants === 1 ? t("{count} dependant", { count: dependants }) : t("{count} dependants", { count: dependants })}</span>
        {SCHEMES.map(scheme => {
          const list = sharesIn(nomineeEntries, scheme.value);
          const total = schemeTotal(nomineeEntries, scheme.value);
          const state = schemeState(total, list.length);
          return list.length === 0 ? null : (
            <span key={scheme.value} style={PILL}><span aria-hidden="true" style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: DOT[state], marginRight: 6 }} />{t(scheme.label)} {total}%</span>
          );
        })}
      </div>

      <div ref={familySection}>
        <h4 style={{ fontSize: "0.95rem", margin: "0 0 4px" }}>{t("Family members")}</h4>
        <p style={{ color: "var(--on-variant)", fontSize: ".85rem", margin: "0 0 12px" }}>
          {t("Add the people who depend on the employee or who may be nominated below. A person is added once and can be picked as a nominee.")}
        </p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 12 }}>
          <span style={{ fontSize: 12, color: "var(--muted)" }}>{t("Quick add")}</span>
          {RELATIONSHIPS.filter(relationship => relationship !== "sibling").map(relationship => (
            <button key={relationship} type="button" className="rvbtn" onClick={() => quickAdd(relationship)}>
              <i className="ti ti-plus" aria-hidden="true" /> {t(RELATIONSHIP_LABELS[relationship])}
            </button>
          ))}
          <button type="button" className="rvbtn ghost" onClick={() => quickAdd()}>{t("Someone else")}</button>
        </div>
        {familyEntries.length === 0 && (
          <p style={{ color: "var(--on-variant)", fontSize: ".9rem", margin: 0 }}>{t("No family members yet. This is optional; use the buttons above to add someone.")}</p>
        )}
        <div style={{ display: "grid", gap: 10 }}>
          {familyEntries.map(entry => (
            <FamilyMemberCard
              key={entry.id} entry={entry} isOpen={openIds.has(entry.id)} isNominee={nominatedIds.has(entry.id)}
              roleNote={duplicates.has(entry.id) ? t("Another {relationship} is already listed.", { relationship: t(RELATIONSHIP_LABELS[entry.relationship]).toLowerCase() }) : null}
              onToggle={() => toggle(entry.id, openIds.has(entry.id))} onChange={(field, value) => changeFamily(entry.id, field, value)} onRemove={() => onRemoveFamily(entry.id)}
            />
          ))}
        </div>
      </div>

      <div style={{ borderTop: "1px solid var(--line, #e5e7eb)", paddingTop: 16 }}>
        <h4 style={{ fontSize: "0.95rem", margin: "0 0 4px" }}>{t("EPF / Gratuity nomination")}</h4>
        <p style={{ color: "var(--on-variant)", fontSize: ".85rem", margin: "0 0 12px" }}>
          {t("Each scheme's shares should add up to 100% across its nominees. Pick nominees from the family list above.")}
        </p>
        {people.length === 0 && (
          wasBlocked
            ? <div role="alert" className="alert alert-error" style={{ margin: "0 0 12px" }}><i className="ti ti-alert-circle" /><div>{t("A nominee is picked from the family list, and there is nobody in it yet. Add a family member with a name above, then add the nominee.")}</div></div>
            : <p style={{ color: "var(--warn)", fontSize: ".85rem", margin: "0 0 12px" }}>{t("Add a family member with a name above before adding a nominee.")}</p>
        )}
        <div style={{ display: "grid", gap: 10 }}>
          {SCHEMES.map(scheme => (
            <NominationLane
              key={scheme.value} scheme={scheme} nominees={sharesIn(nomineeEntries, scheme.value)} allNominees={nomineeEntries}
              total={schemeTotal(nomineeEntries, scheme.value)} members={selectable} canAdd={people.length > 0}
              onAdd={() => addNominee(scheme.value)} onBlocked={nomineeBlocked} onField={onNomineeFieldChange} onRemove={onRemoveNominee}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

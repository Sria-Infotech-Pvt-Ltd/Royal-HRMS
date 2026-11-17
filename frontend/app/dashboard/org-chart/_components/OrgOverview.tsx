"use client";

import type { ReactNode } from "react";
import type { OrgAttention } from "@/lib/orgStructureStats";
import type { OrgUnit } from "@/types/orgStructure";

interface Props {
  attention: OrgAttention;
  onSelectUnit: (unitId: string) => void;
}

/** Shown on the right while nothing is selected: where the gaps in the structure are, each one a shortcut. */
export default function OrgOverview({ attention, onSelectUnit }: Props) {
  const { withoutChief, chiefVacant, empty, mostVacant } = attention;
  const isAllGood = withoutChief.length + chiefVacant.length + empty.length + mostVacant.length === 0;

  return (
    <div>
      <div style={{ fontSize: 15, fontWeight: 700 }}>Overview</div>
      <div style={{ fontSize: 12.5, color: "var(--on-variant)", margin: "2px 0 16px" }}>
        Select a unit, position or person to see its details, or start with one of these.
      </div>
      {isAllGood ? (
        <div className="alert alert-success"><i className="ti ti-circle-check" /> <div>Every unit has a head and no seats are open.</div></div>
      ) : (
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))" }}>
          <Group icon="ti-user-question" title="Most open seats" hint="Units with the most vacant positions of their own">
            {mostVacant.map(({ unit, vacant }) => <Row key={unit.id} unit={unit} note={`${vacant} open`} onSelectUnit={onSelectUnit} />)}
          </Group>
          <Group icon="ti-crown" title="Head seat vacant" hint="The unit's chief position has nobody in it">
            {chiefVacant.map(unit => <Row key={unit.id} unit={unit} onSelectUnit={onSelectUnit} />)}
          </Group>
          <Group icon="ti-alert-triangle" title="No head set" hint="Has positions, but none is marked as chief">
            {withoutChief.map(unit => <Row key={unit.id} unit={unit} onSelectUnit={onSelectUnit} />)}
          </Group>
          <Group icon="ti-folder-off" title="Empty units" hint="No positions and no sub-units">
            {empty.map(unit => <Row key={unit.id} unit={unit} onSelectUnit={onSelectUnit} />)}
          </Group>
        </div>
      )}
    </div>
  );
}

const VISIBLE_ROWS = 6;

function Group({ icon, title, hint, children }: { icon: string; title: string; hint: string; children: ReactNode[] }) {
  if (children.length === 0) return null;
  return (
    <div style={{ border: "1px solid var(--outline-v)", borderRadius: 10, overflow: "hidden" }}>
      <div style={{ padding: "10px 12px", background: "var(--bg-low)" }}>
        <div style={{ fontSize: 13, fontWeight: 700, display: "flex", alignItems: "center", gap: 6 }}>
          <i className={`ti ${icon}`} style={{ color: "var(--warn)" }} /> {title}
          <span className="badge badge-warn" style={{ marginLeft: "auto" }}>{children.length}</span>
        </div>
        <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 2 }}>{hint}</div>
      </div>
      <div>{children.slice(0, VISIBLE_ROWS)}</div>
      {children.length > VISIBLE_ROWS && (
        <div style={{ padding: "6px 12px", fontSize: 11.5, color: "var(--on-variant)" }}>and {children.length - VISIBLE_ROWS} more — use the search to find them</div>
      )}
    </div>
  );
}

function Row({ unit, note, onSelectUnit }: { unit: OrgUnit; note?: string; onSelectUnit: (unitId: string) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelectUnit(unit.id)}
      style={{ display: "flex", width: "100%", alignItems: "center", gap: 8, padding: "8px 12px", border: "none", borderTop: "1px solid var(--outline-v)", background: "none", cursor: "pointer", textAlign: "left", fontSize: 12.5, color: "inherit" }}
    >
      <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{unit.name}</span>
      {note && <span style={{ color: "var(--warn)", fontWeight: 600, flexShrink: 0 }}>{note}</span>}
      <i className="ti ti-chevron-right" style={{ color: "var(--outline)" }} />
    </button>
  );
}

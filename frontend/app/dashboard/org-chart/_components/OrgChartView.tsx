"use client";

import { useMemo, useState, type ReactNode } from "react";
import type { OrgUnit, Position } from "@/types/orgStructure";
import { initialsOf, type UnitRollup } from "@/lib/orgStructureStats";
import { useChartBranches } from "@/hooks/useChartBranches";
import { useT } from "@/hooks/useI18n";
import OrgChartFrame from "./OrgChartFrame";

interface Props {
  units: OrgUnit[];
  positions: Position[];
  rollups: Map<string, UnitRollup>;
  selectedUnitId: string | null;
  onSelectUnit: (unitId: string) => void;
}

const OPEN_DEPTH = 2;       // how many levels start expanded
const MAX_AVATARS = 3;
const MAX_SEATS_SHOWN = 5;

/** The organisation drawn as boxes joined by lines: one box per org unit, top of the company first. */
export default function OrgChartView({ units, positions, rollups, selectedUnitId, onSelectUnit }: Props) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [showSeats, setShowSeats] = useState(false);
  const branches = useChartBranches(OPEN_DEPTH);

  const liveUnits = useMemo(() => units.filter(unit => unit.is_active), [units]);
  const childrenOf = useMemo(() => {
    const map = new Map<string | null, OrgUnit[]>();
    for (const unit of liveUnits) map.set(unit.parent, [...(map.get(unit.parent) ?? []), unit]);
    return map;
  }, [liveUnits]);
  const seatsOf = useMemo(() => {
    const map = new Map<string, Position[]>();
    for (const position of positions) {
      if (position.is_active) map.set(position.org_unit, [...(map.get(position.org_unit) ?? []), position]);
    }
    return map;
  }, [positions]);

  // Search: the units that match, and every unit above a match (kept open and not dimmed so the path to it is visible).
  const { matches, pathToMatches } = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matched = new Set<string>();
    const path = new Set<string>();
    if (!needle) return { matches: matched, pathToMatches: path };
    const parentOf = new Map(liveUnits.map(unit => [unit.id, unit.parent]));
    for (const unit of liveUnits) {
      const seats = seatsOf.get(unit.id) ?? [];
      const isMatch = unit.name.toLowerCase().includes(needle) || unit.code.toLowerCase().includes(needle)
        || seats.some(seat => seat.title.toLowerCase().includes(needle) || (seat.holder_name ?? "").toLowerCase().includes(needle));
      if (!isMatch) continue;
      matched.add(unit.id);
      for (let above = parentOf.get(unit.id); above && !path.has(above); above = parentOf.get(above)) path.add(above);
    }
    return { matches: matched, pathToMatches: path };
  }, [query, liveUnits, seatsOf]);
  const isSearching = query.trim() !== "";

  function renderBranch(unit: OrgUnit, depth: number): ReactNode {
    const kids = childrenOf.get(unit.id) ?? [];
    const isOpen = branches.isOpen(unit.id, depth, pathToMatches.has(unit.id));
    const state = !isSearching ? "normal" : matches.has(unit.id) ? "hit" : pathToMatches.has(unit.id) ? "normal" : "dim";
    return (
      <li key={unit.id}>
        <UnitBox
          unit={unit} rollup={rollups.get(unit.id)} seats={seatsOf.get(unit.id) ?? []} showSeats={showSeats}
          selected={selectedUnitId === unit.id} state={state} childCount={kids.length} isOpen={isOpen}
          onSelect={() => onSelectUnit(unit.id)} onToggle={() => branches.flip(unit.id)}
        />
        {kids.length > 0 && isOpen && <ul>{kids.map(child => renderBranch(child, depth + 1))}</ul>}
      </li>
    );
  }

  const roots = childrenOf.get(null) ?? [];
  const seatsToggle = (
    <button type="button" className={showSeats ? "btn btn-filled btn-sm" : "btn btn-ghost btn-sm"} aria-pressed={showSeats} onClick={() => setShowSeats(!showSeats)}>
      <i className="ti ti-id-badge-2" /> {t("Show seats")}
    </button>
  );
  return (
    <OrgChartFrame
      query={query} onQueryChange={setQuery} searchPlaceholder={t("Find unit, position or person")}
      onExpandAll={() => branches.setAll(true)} onCollapseAll={() => branches.setAll(false)}
      isEmpty={roots.length === 0} emptyText={t("No org units yet — add one to get started.")} tools={seatsToggle}
    >
      <ul>{roots.map(root => renderBranch(root, 0))}</ul>
    </OrgChartFrame>
  );
}

interface BoxProps {
  unit: OrgUnit; rollup: UnitRollup | undefined; seats: Position[]; showSeats: boolean; selected: boolean;
  state: "normal" | "hit" | "dim"; childCount: number; isOpen: boolean; onSelect: () => void; onToggle: () => void;
}

function UnitBox({ unit, rollup, seats, showSeats, selected, state, childCount, isOpen, onSelect, onToggle }: BoxProps) {
  const t = useT();
  const total = rollup?.total ?? 0;
  const filled = rollup?.filled ?? 0;
  const openSeats = total - filled;
  const percent = total === 0 ? 0 : Math.round((filled / total) * 100);
  const chief = rollup?.chief ?? null;
  const holders = seats.filter(seat => seat.holder_name).map(seat => seat.holder_name ?? "");
  const health = total === 0 ? "" : percent >= 80 ? "oc-ok" : percent >= 40 ? "oc-mid" : "oc-low";
  const classes = ["oc-box", health, selected ? "oc-box-sel" : "", state === "hit" ? "oc-box-hit" : "", state === "dim" ? "oc-dim" : ""].filter(Boolean).join(" ");
  return (
    <div className="oc-box-wrap">
      <div className={classes} role="button" tabIndex={0} onClick={onSelect}
        onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelect(); } }}>
        <div className="oc-name" title={unit.name}>{unit.name}</div>
        <div className="oc-head">
          {chief?.holder_name ? <><i className="ti ti-crown" /> {chief.holder_name}</>
            : chief ? <span className="oc-warn">{t("Head seat vacant")}</span>
            : <span className="oc-muted">{t("No head set")}</span>}
        </div>
        <div className="oc-bar" title={t("{filled} of {total} seats filled", { filled, total })}><span style={{ width: `${percent}%` }} /></div>
        <div className="oc-foot">
          <span>{t("{filled}/{total} filled", { filled, total })}{openSeats > 0 && <span className="oc-warn"> · {t("{count} open", { count: openSeats })}</span>}</span>
          {!showSeats && (
            <span className="oc-avatars">
              {holders.slice(0, MAX_AVATARS).map(name => <span key={name} className="oc-avatar" title={name}>{initialsOf(name)}</span>)}
              {holders.length > MAX_AVATARS && <span className="oc-avatar oc-more">+{holders.length - MAX_AVATARS}</span>}
            </span>
          )}
        </div>
        {showSeats && seats.length > 0 && (
          <div className="oc-seats">
            {seats.slice(0, MAX_SEATS_SHOWN).map(seat => (
              <div key={seat.id} className="oc-seat" title={seat.holder_name ? `${seat.title} — ${seat.holder_name}` : `${seat.title} — ${t("vacant")}`}>
                <span className={`oc-avatar${seat.holder_name ? "" : " oc-avatar-vacant"}`}>{seat.holder_name ? initialsOf(seat.holder_name) : "?"}</span>
                <span className="oc-seat-title">{seat.title}</span>
                {seat.is_chief && <i className="ti ti-crown" />}
              </div>
            ))}
            {seats.length > MAX_SEATS_SHOWN && <div className="oc-muted" style={{ fontSize: 11 }}>{t("+{count} more seats", { count: seats.length - MAX_SEATS_SHOWN })}</div>}
          </div>
        )}
      </div>
      {childCount > 0 && (
        <button type="button" className="oc-toggle" onClick={onToggle} aria-label={isOpen ? t("Collapse sub-units") : t("Expand sub-units")} title={isOpen ? t("Collapse") : childCount === 1 ? t("Show {count} sub-unit", { count: childCount }) : t("Show {count} sub-units", { count: childCount })}>
          {isOpen ? <i className="ti ti-minus" /> : childCount}
        </button>
      )}
    </div>
  );
}

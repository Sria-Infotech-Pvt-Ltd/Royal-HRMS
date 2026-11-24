"use client";

import { useState, type ReactNode } from "react";
import type { OrgUnit, Position } from "@/types/orgStructure";
import type { Selected } from "./OrgStructureClient";
import type { UnitRollup } from "@/lib/orgStructureStats";
import { useT } from "@/hooks/useI18n";

export type SeatFilter = "all" | "vacant" | "filled";
/** "Expand all" / "Collapse all": a new id is a new command, so pressing the same button twice still works. */
export interface TreeCommand { id: number; action: "expand" | "collapse" }

interface Props {
  units: OrgUnit[];
  positions: Position[];
  search: string;
  branchFilter: number | null;
  selected: Selected;
  onSelect: (s: Selected) => void;
  rollups: Map<string, UnitRollup>;
  seatFilter: SeatFilter;
  command: TreeCommand | null;
}

function initials(name: string): string {
  return name.split(/\s+/).slice(0, 2).map(w => w[0]).join("").toUpperCase();
}

/** The name with the searched text picked out. */
function highlight(text: string, query: string): ReactNode {
  const at = query ? text.toLowerCase().indexOf(query) : -1;
  if (at < 0) return text;
  return <>{text.slice(0, at)}<mark className="orgnode-hit">{text.slice(at, at + query.length)}</mark>{text.slice(at + query.length)}</>;
}

export default function OrgTree({ units, positions, search, branchFilter, selected, onSelect, rollups, seatFilter, command }: Props) {
  const t = useT();
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  // Apply a new Expand all / Collapse all while rendering (React's pattern for state that follows a prop), not in an effect.
  const [seenCommandId, setSeenCommandId] = useState<number | null>(null);
  if (command && command.id !== seenCommandId) {
    setSeenCommandId(command.id);
    setCollapsed(command.action === "expand" ? new Set() : new Set([
      ...units.filter(u => positions.some(p => p.org_unit === u.id) || units.some(c => c.parent === u.id)).map(u => `u${u.id}`),
      ...positions.filter(p => p.holder).map(p => `p${p.id}`),
    ]));
  }
  const q = search.trim().toLowerCase();

  // A branch-scoped position must match; a position with no branch set is
  // company-wide and always shows, in every branch view. Filtering to one
  // specific branch is meant for "what's open here" (hiring into that
  // branch), so once a branch is actually selected, only vacant positions
  // show — a filled seat isn't something you'd be assigning into anyway.
  const matchesBranch = (p: Position) => {
    if (branchFilter === null) return true;
    if (p.branch !== null && p.branch !== branchFilter) return false;
    return !p.holder;
  };

  const childUnits = (parentId: string | null) => units.filter(u => u.parent === parentId);
  const matchesSeatFilter = (p: Position) =>
    seatFilter === "all" || (seatFilter === "vacant" ? p.is_active && !p.holder : !!p.holder);
  const posInUnit = (unitId: string) => positions.filter(p => p.org_unit === unitId && matchesBranch(p) && matchesSeatFilter(p));

  function toggle(key: string) {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function matchesSearch(u: OrgUnit): boolean {
    if (!q) return true;
    if (u.name.toLowerCase().includes(q) || u.code.toLowerCase().includes(q)) return true;
    if (posInUnit(u.id).some(p => p.title.toLowerCase().includes(q) || (p.holder_name ?? "").toLowerCase().includes(q))) return true;
    return childUnits(u.id).some(matchesSearch);
  }

  // posInUnit already applies the branch filter — a unit only "has a branch
  // match" once it (or a descendant) has at least one visible position left.
  function hasBranchMatch(u: OrgUnit): boolean {
    if (branchFilter === null && seatFilter === "all") return true;
    if (posInUnit(u.id).length > 0) return true;
    return childUnits(u.id).some(hasBranchMatch);
  }

  function matchUnit(u: OrgUnit): boolean {
    return matchesSearch(u) && hasBranchMatch(u);
  }

  function renderUnit(u: OrgUnit, depth: number): ReactNode {
    if (!matchUnit(u)) return null;
    const kids = childUnits(u.id);
    const poss = posInUnit(u.id);
    const hasChildren = kids.length + poss.length > 0;
    const isCollapsed = collapsed.has(`u${u.id}`) && !q;
    const isSel = selected?.type === "unit" && selected.id === u.id;
    const rollup = rollups.get(u.id);

    return (
      <div key={`u${u.id}`}>
        <div
          className={`orgnode${isSel ? " orgnode-sel" : ""}`}
          style={{ paddingLeft: 9 + depth * 18 }}
          onClick={() => onSelect({ type: "unit", id: u.id })}
        >
          {hasChildren ? (
            <i
              className={`ti ${isCollapsed ? "ti-chevron-right" : "ti-chevron-down"} orgnode-caret`}
              onClick={e => { e.stopPropagation(); toggle(`u${u.id}`); }}
            />
          ) : <span className="orgnode-caret" />}
          <span className="orgnode-glyph" style={{ background: "var(--primary-container, color-mix(in srgb, var(--brand) 12%, transparent))", color: "var(--primary)" }}>O</span>
          <span className="orgnode-name">{highlight(u.name, q)}</span>
          {rollup && rollup.total > 0 && (
            <span className="orgnode-count" title={t("{filled} of {total} seats filled, including sub-units", { filled: rollup.filled, total: rollup.total })}>
              {rollup.filled}/{rollup.total}
            </span>
          )}
        </div>
        {!isCollapsed && (
          <>
            {poss.map(p => renderPosition(p, depth + 1))}
            {kids.map(c => renderUnit(c, depth + 1))}
          </>
        )}
      </div>
    );
  }

  function renderPosition(p: Position, depth: number): ReactNode {
    if (q) {
      const selfMatches = p.title.toLowerCase().includes(q) || (p.holder_name ?? "").toLowerCase().includes(q);
      const unit = units.find(u => u.id === p.org_unit);
      const unitMatches = unit && (unit.name.toLowerCase().includes(q) || unit.code.toLowerCase().includes(q));
      if (!selfMatches && !unitMatches) return null;
    }
    const isSel = selected?.type === "position" && selected.id === p.id;
    const hasHolder = !!p.holder_name;
    const isCollapsed = collapsed.has(`p${p.id}`) && !q;

    return (
      <div key={`p${p.id}`}>
        <div
          className={`orgnode${isSel ? " orgnode-sel" : ""}`}
          style={{ paddingLeft: 9 + depth * 18, opacity: p.is_active ? 1 : 0.55 }}
          onClick={() => onSelect({ type: "position", id: p.id })}
        >
          {hasHolder ? (
            <i
              className={`ti ${isCollapsed ? "ti-chevron-right" : "ti-chevron-down"} orgnode-caret`}
              onClick={e => { e.stopPropagation(); toggle(`p${p.id}`); }}
            />
          ) : <span className="orgnode-caret" />}
          <span className="orgnode-glyph" style={{ background: "var(--info-c)", color: "var(--info)" }}>S</span>
          <span className="orgnode-name">{highlight(p.title, q)}</span>
          {p.is_chief && <i className="ti ti-crown" style={{ color: "var(--warn)", fontSize: 13, flexShrink: 0 }} title={t("Chief position")} />}
          {!p.is_active && <span className="badge" style={{ marginLeft: "auto", fontSize: 9.5, background: "var(--bg-low)", color: "var(--on-variant)", flexShrink: 0 }}>{t("Inactive")}</span>}
          {p.is_active && !hasHolder && <span className="badge badge-warn" style={{ marginLeft: "auto", fontSize: 9.5 }}>{t("Vacant")}</span>}
        </div>
        {hasHolder && !isCollapsed && (
          <div
            className={`orgnode${selected?.type === "person" && selected.id === p.holder ? " orgnode-sel" : ""}`}
            style={{ paddingLeft: 9 + (depth + 1) * 18 }}
            onClick={() => p.holder && onSelect({ type: "person", id: p.holder })}
          >
            <span className="orgnode-caret" />
            <span className="orgnode-glyph" style={{ background: "var(--success-c)", color: "var(--success)" }}>{initials(p.holder_name ?? "?")}</span>
            <span className="orgnode-name">{highlight(p.holder_name ?? "", q)}</span>
          </div>
        )}
      </div>
    );
  }

  const roots = childUnits(null);
  const rendered = roots.map(r => renderUnit(r, 0)).filter(Boolean);

  return (
    <>
      <style>{`
        .orgnode { display:flex; align-items:center; gap:8px; padding:7px 9px; border-radius:8px; cursor:pointer; }
        .orgnode:hover { background: var(--bg-low); }
        .orgnode-sel { background: color-mix(in srgb, var(--brand) 10%, transparent); }
        .orgnode-sel .orgnode-name { color: var(--primary); font-weight: 600; }
        .orgnode-caret { width:15px; height:15px; flex-shrink:0; font-size:13px; color: var(--outline); }
        .orgnode-glyph { width:21px; height:21px; border-radius:6px; flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:10px; font-weight:750; }
        .orgnode-count { flex-shrink:0; font-size:10.5px; font-weight:650; padding:1px 7px; border-radius:10px; background:var(--bg-low); color:var(--on-variant); border:1px solid var(--outline-v); }
        .orgnode-hit { background: rgba(250,204,21,0.45); color: inherit; border-radius: 3px; padding: 0 1px; }
        .orgnode-name { flex: 1 1 auto; min-width: 0; font-size:13px; font-weight:520; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      `}</style>
      {rendered.length > 0
        ? rendered
        : <div style={{ padding: 24, textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
            {q || branchFilter !== null || seatFilter !== "all" ? t("Nothing matches.") : t("No org units yet — add one to get started.")}
          </div>
      }
    </>
  );
}

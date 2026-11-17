"use client";

import { useMemo, useState, type ReactNode } from "react";
import type { Position } from "@/types/orgStructure";
import { initialsOf } from "@/lib/orgStructureStats";
import { useChartBranches } from "@/hooks/useChartBranches";
import OrgChartFrame from "./OrgChartFrame";

interface Props {
  positions: Position[];
  selectedPositionId: string | null;
  onSelectPosition: (positionId: string) => void;
}

const OPEN_DEPTH = 3;

/** Who reports to whom: one box per active position, joined by each position's "reports to". Seats with no line sit at the top. */
export default function OrgReportingChart({ positions, selectedPositionId, onSelectPosition }: Props) {
  const [query, setQuery] = useState("");
  const branches = useChartBranches(OPEN_DEPTH);
  const live = useMemo(() => positions.filter(position => position.is_active), [positions]);

  const { roots, childrenOf, parentOf } = useMemo(() => {
    const ids = new Set(live.map(position => position.id));
    const children = new Map<string, Position[]>();
    const parents = new Map<string, string>();
    const top: Position[] = [];
    for (const position of live) {
      const parentId = position.reports_to?.position_id ?? null;
      // A line pointing at a missing seat, or at itself, is treated as no line rather than hiding the seat.
      if (!parentId || parentId === position.id || !ids.has(parentId)) { top.push(position); continue; }
      parents.set(position.id, parentId);
      children.set(parentId, [...(children.get(parentId) ?? []), position]);
    }
    // A loop (A reports to B, B to A) has no top, so it would vanish: start the chart from one seat of each loop.
    const reachable = new Set<string>();
    const walk = (position: Position) => {
      if (reachable.has(position.id)) return;
      reachable.add(position.id);
      (children.get(position.id) ?? []).forEach(walk);
    };
    top.forEach(walk);
    for (const position of live) {
      if (reachable.has(position.id)) continue;
      // Cut the loop here: this seat stops reporting to the one that (indirectly) reports to it.
      const formerParent = parents.get(position.id);
      if (formerParent) children.set(formerParent, (children.get(formerParent) ?? []).filter(child => child.id !== position.id));
      parents.delete(position.id);
      top.push(position);
      walk(position);
    }
    return { roots: top, childrenOf: children, parentOf: parents };
  }, [live]);

  const { matches, pathToMatches } = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const matched = new Set<string>();
    const path = new Set<string>();
    if (!needle) return { matches: matched, pathToMatches: path };
    for (const position of live) {
      const text = `${position.title} ${position.holder_name ?? ""} ${position.org_unit_name}`.toLowerCase();
      if (!text.includes(needle)) continue;
      matched.add(position.id);
      for (let above = parentOf.get(position.id); above && !path.has(above); above = parentOf.get(above)) path.add(above);
    }
    return { matches: matched, pathToMatches: path };
  }, [query, live, parentOf]);
  const isSearching = query.trim() !== "";
  const unlinkedCount = roots.filter(position => (childrenOf.get(position.id) ?? []).length === 0).length;

  function renderBranch(position: Position, depth: number): ReactNode {
    const kids = childrenOf.get(position.id) ?? [];
    const isOpen = branches.isOpen(position.id, depth, pathToMatches.has(position.id));
    const stateClass = !isSearching ? "" : matches.has(position.id) ? " oc-box-hit" : pathToMatches.has(position.id) ? "" : " oc-dim";
    return (
      <li key={position.id}>
        <div className="oc-box-wrap">
          <div className={`oc-box ${position.holder_name ? "oc-filled" : "oc-vacant"}${selectedPositionId === position.id ? " oc-box-sel" : ""}${stateClass}`} role="button" tabIndex={0}
            onClick={() => onSelectPosition(position.id)}
            onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onSelectPosition(position.id); } }}>
            <div className="oc-name" title={position.title}>{position.title}{position.is_chief && <i className="ti ti-crown" style={{ color: "var(--warn)", marginLeft: 5 }} title="Head of unit" />}</div>
            <div className="oc-head">
              <span className={`oc-avatar${position.holder_name ? "" : " oc-avatar-vacant"}`}>{position.holder_name ? initialsOf(position.holder_name) : "?"}</span>
              {position.holder_name ?? <span className="oc-warn">Vacant</span>}
            </div>
            <div className="oc-sub" style={{ marginTop: 4 }} title={position.org_unit_name}>{position.org_unit_name}</div>
          </div>
          {kids.length > 0 && (
            <button type="button" className="oc-toggle" onClick={() => branches.flip(position.id)} aria-label={isOpen ? "Hide reports" : "Show reports"}
              title={isOpen ? "Collapse" : `Show ${kids.length} direct report${kids.length === 1 ? "" : "s"}`}>
              {isOpen ? <i className="ti ti-minus" /> : kids.length}
            </button>
          )}
        </div>
        {kids.length > 0 && isOpen && <ul>{kids.map(child => renderBranch(child, depth + 1))}</ul>}
      </li>
    );
  }

  return (
    <OrgChartFrame
      query={query} onQueryChange={setQuery} searchPlaceholder="Find position, person or unit"
      onExpandAll={() => branches.setAll(true)} onCollapseAll={() => branches.setAll(false)}
      isEmpty={live.length === 0} emptyText="No positions yet."
      tools={unlinkedCount > 0 ? <span className="badge badge-warn" title="Positions with nobody reporting to them and no one they report to. Set 'Reports to' on a position to place it in the chain.">{unlinkedCount} without a reporting line</span> : null}
    >
      <ul>{roots.map(root => renderBranch(root, 0))}</ul>
    </OrgChartFrame>
  );
}

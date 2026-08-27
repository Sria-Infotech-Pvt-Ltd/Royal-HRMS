"use client";

import { useState, type ReactNode } from "react";
import type { OrgUnit, Position } from "@/types/orgStructure";
import type { Selected } from "./OrgStructureClient";

interface Props {
  units: OrgUnit[];
  positions: Position[];
  search: string;
  selected: Selected;
  onSelect: (s: Selected) => void;
}

function initials(name: string): string {
  return name.split(/\s+/).slice(0, 2).map(w => w[0]).join("").toUpperCase();
}

export default function OrgTree({ units, positions, search, selected, onSelect }: Props) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const q = search.trim().toLowerCase();

  const childUnits = (parentId: string | null) => units.filter(u => u.parent === parentId);
  const posInUnit = (unitId: string) => positions.filter(p => p.org_unit === unitId);

  function toggle(key: string) {
    setCollapsed(prev => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  function matchUnit(u: OrgUnit): boolean {
    if (!q) return true;
    if (u.name.toLowerCase().includes(q) || u.code.toLowerCase().includes(q)) return true;
    if (posInUnit(u.id).some(p => p.title.toLowerCase().includes(q) || (p.holder_name ?? "").toLowerCase().includes(q))) return true;
    return childUnits(u.id).some(matchUnit);
  }

  function renderUnit(u: OrgUnit, depth: number): ReactNode {
    if (!matchUnit(u)) return null;
    const kids = childUnits(u.id);
    const poss = posInUnit(u.id);
    const hasChildren = kids.length + poss.length > 0;
    const isCollapsed = collapsed.has(`u${u.id}`) && !q;
    const isSel = selected?.type === "unit" && selected.id === u.id;

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
          <span className="orgnode-glyph" style={{ background: "var(--primary-container, rgba(30,78,140,0.12))", color: "var(--primary)" }}>O</span>
          <span className="orgnode-name">{u.name}</span>
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
          style={{ paddingLeft: 9 + depth * 18 }}
          onClick={() => onSelect({ type: "position", id: p.id })}
        >
          {hasHolder ? (
            <i
              className={`ti ${isCollapsed ? "ti-chevron-right" : "ti-chevron-down"} orgnode-caret`}
              onClick={e => { e.stopPropagation(); toggle(`p${p.id}`); }}
            />
          ) : <span className="orgnode-caret" />}
          <span className="orgnode-glyph" style={{ background: "var(--info-c)", color: "var(--info)" }}>S</span>
          <span className="orgnode-name">{p.title}</span>
          {p.is_chief && <i className="ti ti-crown" style={{ color: "var(--warn)", fontSize: 13, flexShrink: 0 }} title="Chief position" />}
          {!hasHolder && <span className="badge badge-warn" style={{ marginLeft: "auto", fontSize: 9.5 }}>Vacant</span>}
        </div>
        {hasHolder && !isCollapsed && (
          <div
            className={`orgnode${selected?.type === "person" && selected.id === p.holder ? " orgnode-sel" : ""}`}
            style={{ paddingLeft: 9 + (depth + 1) * 18 }}
            onClick={() => p.holder && onSelect({ type: "person", id: p.holder })}
          >
            <span className="orgnode-caret" />
            <span className="orgnode-glyph" style={{ background: "var(--success-c)", color: "var(--success)" }}>{initials(p.holder_name ?? "?")}</span>
            <span className="orgnode-name">{p.holder_name}</span>
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
        .orgnode-sel { background: rgba(30,78,140,0.1); }
        .orgnode-sel .orgnode-name { color: var(--primary); font-weight: 600; }
        .orgnode-caret { width:15px; height:15px; flex-shrink:0; font-size:13px; color: var(--outline); }
        .orgnode-glyph { width:21px; height:21px; border-radius:6px; flex-shrink:0; display:flex; align-items:center; justify-content:center; font-size:10px; font-weight:750; }
        .orgnode-name { font-size:13px; font-weight:520; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
      `}</style>
      {rendered.length > 0
        ? rendered
        : <div style={{ padding: 24, textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
            {q ? "Nothing matches." : "No org units yet — add one to get started."}
          </div>
      }
    </>
  );
}

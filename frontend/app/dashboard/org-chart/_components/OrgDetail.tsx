"use client";

import type { ReactNode } from "react";
import type { JobTemplate, OrgUnit, Placement, Position } from "@/types/orgStructure";
import type { BranchOption, RoleOption, Selected } from "./OrgStructureClient";
import ToggleSwitch from "@/components/ToggleSwitch";

interface Props {
  selected: Selected;
  units: OrgUnit[];
  positions: Position[];
  jobs: JobTemplate[];
  branches: BranchOption[];
  roles: RoleOption[];
  canEdit: boolean;
  placementHistory: Placement[];
  placementHistoryLoading: boolean;
  onSelect: (s: Selected) => void;
  onAddSubUnit: (parentUnitId: string) => void;
  onDeleteUnit: (unitId: string) => void;
  onAddPosition: (unitId: string) => void;
  onAssign: (positionId: string) => void;
  onVacate: (positionId: string) => void;
  onDeactivate: (positionId: string) => void;
  onReactivate: (positionId: string) => void;
  canDelete: boolean;
  onDelete: (positionId: string) => void;
  onCancelScheduled: (placementId: string) => void;
  onUnitField: (unitId: string, field: string, value: string | boolean | null) => void;
  onPositionField: (positionId: string, field: string, value: string | boolean | null) => void;
  onToggleChief: (position: Position) => void;
}

const STATUS_BADGE: Record<Placement["status"], { label: string; color: string; bg: string }> = {
  current:   { label: "Current",   color: "var(--success)", bg: "var(--success-c)" },
  scheduled: { label: "Scheduled", color: "var(--warn)",     bg: "var(--warn-c)" },
  ended:     { label: "Ended",     color: "var(--on-variant)", bg: "var(--bg-low)" },
};

function initials(name: string): string {
  return name.split(/\s+/).slice(0, 2).map(w => w[0]).join("").toUpperCase();
}

function Avatar({ name, size = 30 }: { name: string; size?: number }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: "50%", flexShrink: 0,
      background: "var(--primary)", color: "#fff", fontSize: size * 0.36, fontWeight: 650,
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      {initials(name)}
    </div>
  );
}

function SectionTitle({ children }: { children: ReactNode }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, fontWeight: 650, letterSpacing: "0.05em", textTransform: "uppercase", color: "var(--outline)", marginTop: 20, marginBottom: 10 }}>
      {children}
      <span style={{ flex: 1, height: 1, background: "var(--outline-v)" }} />
    </div>
  );
}

function HeadBox({ icon, role, name, vacant, action }: { icon: ReactNode; role: string; name: string; vacant: boolean; action?: ReactNode }) {
  return (
    <div style={{
      border: `1px solid ${vacant ? "var(--warn)" : "var(--outline-v)"}`, borderRadius: 8, padding: "13px 14px",
      display: "flex", alignItems: "center", gap: 12,
      background: vacant ? "var(--warn-c)" : "var(--bg-low)",
    }}>
      <div style={{ width: 38, height: 38, borderRadius: 9, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", background: "#fff", border: "1px solid var(--outline-v)", color: vacant ? "var(--warn)" : "var(--info)" }}>
        {icon}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{role}</div>
        <div style={{ fontSize: 14.5, fontWeight: 620, marginTop: 1, color: vacant ? "var(--warn)" : "var(--on-bg)", fontStyle: vacant ? "italic" : "normal" }}>{name}</div>
      </div>
      {action}
    </div>
  );
}

function PositionRow({ p, onSelect, onAssign }: { p: Position; onSelect: () => void; onAssign: () => void }) {
  return (
    <div
      onClick={onSelect}
      style={{ display: "flex", alignItems: "center", gap: 11, padding: "11px 13px", border: "1px solid var(--outline-v)", borderRadius: 8, marginBottom: 8, cursor: "pointer", opacity: p.is_active ? 1 : 0.6 }}
    >
      <div style={{ width: 30, height: 30, borderRadius: 8, background: "var(--info-c)", color: "var(--info)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 750, flexShrink: 0 }}>S</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13.5, fontWeight: 580, display: "flex", alignItems: "center", gap: 7 }}>
          {p.title}
          {p.is_chief && <i className="ti ti-crown" style={{ color: "var(--warn)", fontSize: 13 }} />}
          {!p.is_active && <span className="badge" style={{ background: "var(--bg-low)", color: "var(--on-variant)", fontSize: 9.5, fontWeight: 650, padding: "2px 7px", borderRadius: 5 }}>Inactive</span>}
        </div>
        <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 2 }}>
          {p.job_template_name ?? "—"}{p.grade ? ` · ${p.grade}` : ""}{p.branch_name ? ` · ${p.branch_name}` : ""}
        </div>
      </div>
      {p.holder_name ? (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 550 }}>
          <Avatar name={p.holder_name} size={20} /> {p.holder_name}
        </span>
      ) : (
        <span style={{ fontSize: 12, color: "var(--warn)", fontStyle: "italic" }}>Vacant</span>
      )}
      <button
        className="btn btn-ghost btn-sm"
        onClick={e => { e.stopPropagation(); onAssign(); }}
      >
        {p.holder_name ? "Reassign" : "Assign"}
      </button>
    </div>
  );
}

export default function OrgDetail({
  selected, units, positions, jobs, branches, roles, canEdit, placementHistory, placementHistoryLoading, onSelect,
  onAddSubUnit, onDeleteUnit, onAddPosition, onAssign, onVacate, onDeactivate, onReactivate, canDelete, onDelete, onCancelScheduled, onUnitField, onPositionField, onToggleChief,
}: Props) {
  if (!selected) {
    return (
      <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--on-variant)" }}>
        <i className="ti ti-sitemap" style={{ fontSize: 34, color: "var(--outline)", display: "block", marginBottom: 10 }} />
        Select something in the structure to see its details.
      </div>
    );
  }

  const chiefOf = (unitId: string) => positions.find(p => p.org_unit === unitId && p.is_chief) ?? null;

  if (selected.type === "unit") {
    const unit = units.find(u => u.id === selected.id);
    if (!unit) return null;
    const poss = positions.filter(p => p.org_unit === unit.id);
    const filled = poss.filter(p => p.holder).length;
    const chief = chiefOf(unit.id);
    const parentOptions = units.filter(u => u.id !== unit.id);

    return (
      <div key={unit.id}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 13, marginBottom: 6 }}>
          <div style={{ width: 44, height: 44, borderRadius: 11, flexShrink: 0, background: "rgba(30,78,140,0.1)", color: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 750 }}>O</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 18, fontWeight: 680 }}>{unit.name}</div>
            <div style={{ fontSize: 11, fontWeight: 650, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--on-variant)", marginTop: 3, display: "flex", alignItems: "center", gap: 8 }}>
              Org unit
              {unit.code && <span style={{ fontFamily: "monospace", color: "var(--primary)", background: "rgba(30,78,140,0.08)", borderRadius: 5, padding: "1px 6px", fontSize: 11 }}>{unit.code}</span>}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
            {canEdit && (
              <button className="btn btn-ghost btn-sm" onClick={() => onAddSubUnit(unit.id)}>
                <i className="ti ti-plus" /> Sub-unit
              </button>
            )}
            {canDelete && (
              <button
                className="btn btn-ghost"
                style={{ width: 32, height: 32, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6, color: "var(--error)" }}
                onClick={() => {
                  if (window.confirm(`Permanently delete "${unit.name}"? This can't be undone, and only works if none of its positions have ever been held by anyone — if any have, this will be rejected; deactivate the unit instead.`)) {
                    onDeleteUnit(unit.id);
                  }
                }}
                title="Delete org unit — only possible if it has no sub-units and no position in it has ever had a holder"
              >
                <i className="ti ti-trash" style={{ fontSize: 13 }} />
              </button>
            )}
          </div>
        </div>

        <SectionTitle>Head of unit</SectionTitle>
        {!chief ? (
          <HeadBox
            icon={<i className="ti ti-user-question" />} role="Head of unit" name="No chief position yet" vacant
            action={canEdit && <button className="linkbtn" onClick={() => onAddPosition(unit.id)} style={{ background: "var(--primary)", color: "#fff", border: "none", borderRadius: 7, padding: "6px 10px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Add chief position</button>}
          />
        ) : chief.holder_name ? (
          <HeadBox
            icon={<Avatar name={chief.holder_name} size={30} />}
            role={`Head of unit · ${chief.title}${chief.holder_since ? ` · since ${chief.holder_since}` : ""}`}
            name={chief.holder_name} vacant={false}
            action={<button className="btn btn-ghost btn-sm" onClick={() => onSelect({ type: "position", id: chief.id })}>Open position</button>}
          />
        ) : (
          <HeadBox
            icon={<i className="ti ti-user-question" />} role={`Head of unit · ${chief.title}`} name="Vacant — no holder" vacant
            action={canEdit && <button className="linkbtn" onClick={() => onAssign(chief.id)} style={{ background: "var(--primary)", color: "#fff", border: "none", borderRadius: 7, padding: "6px 10px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Assign holder</button>}
          />
        )}

        <SectionTitle>Details</SectionTitle>
        <div className="form-row cols-2">
          <div className="field-group">
            <label className="field-label">Unit name</label>
            <input className="field-input" defaultValue={unit.name} disabled={!canEdit} onBlur={e => e.target.value !== unit.name && onUnitField(unit.id, "name", e.target.value)} />
          </div>
          <div className="field-group">
            <label className="field-label">Code</label>
            <input className="field-input" style={{ fontFamily: "monospace" }} defaultValue={unit.code} disabled={!canEdit} onBlur={e => onUnitField(unit.id, "code", e.target.value.toUpperCase())} />
          </div>
          <div className="field-group">
            <label className="field-label">Parent unit</label>
            <select className="field-input field-select" defaultValue={unit.parent ?? ""} disabled={!canEdit} onChange={e => onUnitField(unit.id, "parent", e.target.value || null)}>
              <option value="">None — top level</option>
              {parentOptions.map(o => <option key={o.id} value={o.id}>{o.name}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">Cost center <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
            <input className="field-input" style={{ fontFamily: "monospace" }} defaultValue={unit.cost_center} disabled={!canEdit} placeholder="CC-…" onBlur={e => onUnitField(unit.id, "cost_center", e.target.value.toUpperCase())} />
          </div>
        </div>
        <div style={{ marginTop: 4 }}>
          <ToggleSwitch
            checked={unit.is_department_level}
            disabled={!canEdit}
            onChange={checked => onUnitField(unit.id, "is_department_level", checked)}
            label={<>This unit counts as a <b>department</b> for leave eligibility and reporting.</>}
          />
        </div>

        <SectionTitle>
          Positions in this unit
          {canEdit && <button className="linkbtn" onClick={() => onAddPosition(unit.id)} style={{ background: "var(--primary-c, rgba(30,78,140,0.1))", color: "var(--primary)", border: "1px solid rgba(30,78,140,0.2)", borderRadius: 7, padding: "5px 10px", fontSize: 11.5, fontWeight: 600, cursor: "pointer", whiteSpace: "nowrap" }}><i className="ti ti-plus" style={{ fontSize: 11 }} /> Add position</button>}
        </SectionTitle>
        {poss.length === 0 && <div style={{ fontSize: 12.5, color: "var(--on-variant)", padding: "6px 0" }}>No positions yet in this unit.</div>}
        {poss.map(p => <PositionRow key={p.id} p={p} onSelect={() => onSelect({ type: "position", id: p.id })} onAssign={() => onAssign(p.id)} />)}
        <div style={{ display: "flex", gap: 20, marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--outline-v)" }}>
          <div style={{ fontSize: 12, color: "var(--on-variant)" }}><b style={{ fontSize: 16, fontWeight: 700, color: "var(--on-bg)", display: "block" }}>{poss.length}</b>positions</div>
          <div style={{ fontSize: 12, color: "var(--on-variant)" }}><b style={{ fontSize: 16, fontWeight: 700, color: "var(--on-bg)", display: "block" }}>{filled}</b>filled</div>
          <div style={{ fontSize: 12, color: "var(--on-variant)" }}><b style={{ fontSize: 16, fontWeight: 700, color: "var(--on-bg)", display: "block" }}>{poss.length - filled}</b>vacant</div>
        </div>
      </div>
    );
  }

  if (selected.type === "position") {
    const p = positions.find(x => x.id === selected.id);
    if (!p) return null;

    return (
      <div key={p.id}>
        <div style={{ display: "flex", alignItems: "flex-start", gap: 13, marginBottom: 6 }}>
          <div style={{ width: 44, height: 44, borderRadius: 11, flexShrink: 0, background: "var(--info-c)", color: "var(--info)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, fontWeight: 750, opacity: p.is_active ? 1 : 0.6 }}>S</div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 18, fontWeight: 680, display: "flex", alignItems: "center", gap: 8 }}>
              {p.title} {p.is_chief && <i className="ti ti-crown" style={{ color: "var(--warn)", fontSize: 16 }} />}
              {!p.is_active && <span className="badge" style={{ background: "var(--bg-low)", color: "var(--on-variant)", fontSize: 10.5, fontWeight: 650, padding: "2px 8px", borderRadius: 5 }}>Inactive</span>}
            </div>
            <div style={{ fontSize: 11, fontWeight: 650, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--on-variant)", marginTop: 3 }}>
              Position · {p.org_unit_name}{p.branch_name ? ` · ${p.branch_name}` : ""}
            </div>
          </div>
          <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
            {canEdit && (
              p.is_active ? (
                <button className="btn btn-ghost btn-sm" onClick={() => onDeactivate(p.id)}>
                  <i className="ti ti-eye-off" /> Deactivate
                </button>
              ) : (
                <button className="btn btn-ghost btn-sm" onClick={() => onReactivate(p.id)}>
                  <i className="ti ti-eye" /> Reactivate
                </button>
              )
            )}
            {canDelete && (
              <button
                className="btn btn-ghost"
                style={{ width: 32, height: 32, padding: 0, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: 6, color: "var(--error)" }}
                onClick={() => {
                  if (window.confirm(`Permanently delete "${p.title}"? This can't be undone, and only works if it has never had a holder — if it has any placement history, this will be rejected; deactivate it instead.`)) {
                    onDelete(p.id);
                  }
                }}
                title="Delete position — only possible if it has no placement history"
              >
                <i className="ti ti-trash" style={{ fontSize: 13 }} />
              </button>
            )}
          </div>
        </div>

        <SectionTitle>Holder</SectionTitle>
        {p.holder_name ? (
          <HeadBox
            icon={<Avatar name={p.holder_name} size={30} />}
            role={p.holder_since ? `Current holder · since ${p.holder_since}` : "Current holder"}
            name={p.holder_name} vacant={false}
            action={canEdit && (
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-ghost btn-sm" onClick={() => onAssign(p.id)}>Reassign</button>
                <button className="btn btn-ghost btn-sm" onClick={() => onVacate(p.id)}>Vacate</button>
              </div>
            )}
          />
        ) : (
          <HeadBox
            icon={<i className="ti ti-user-question" />} role="Current holder" name="Vacant" vacant
            action={canEdit && <button className="linkbtn" onClick={() => onAssign(p.id)} style={{ background: "var(--primary)", color: "#fff", border: "none", borderRadius: 7, padding: "6px 10px", fontSize: 12, fontWeight: 600, cursor: "pointer" }}>Assign holder</button>}
          />
        )}

        {p.scheduled && (() => {
          const scheduled = p.scheduled;
          return (
            <div style={{
              marginTop: 10, display: "flex", alignItems: "center", gap: 10, padding: "10px 14px",
              background: "var(--warn-c)", border: "1px solid var(--warn)", borderRadius: 8, fontSize: 12.5,
            }}>
              <i className="ti ti-clock" style={{ color: "var(--warn)", fontSize: 15 }} />
              <div style={{ flex: 1 }}>
                <b>{scheduled.employee_name}</b> is scheduled to take this seat on <b>{scheduled.effective_from}</b>.
              </div>
              {canEdit && (
                <button className="btn btn-ghost btn-sm" onClick={() => onCancelScheduled(scheduled.placement_id)}>Cancel</button>
              )}
            </div>
          );
        })()}

        <SectionTitle>Reporting</SectionTitle>
        <div className="field-group">
          <label className="field-label">Reports to</label>
          <input className="field-input" disabled value={p.reports_to ? `${p.reports_to.holder_name ?? "Vacant"} · ${p.reports_to.title}` : "—"} style={{ background: "var(--bg-low)", color: "var(--on-variant)" }} />
        </div>

        <SectionTitle>Details</SectionTitle>
        <div className="form-row cols-2">
          <div className="field-group">
            <label className="field-label">Position title</label>
            <input className="field-input" defaultValue={p.title} disabled={!canEdit} onBlur={e => e.target.value !== p.title && onPositionField(p.id, "title", e.target.value)} />
          </div>
          <div className="field-group">
            <label className="field-label">Grade / band</label>
            <input className="field-input" style={{ fontFamily: "monospace" }} defaultValue={p.grade} disabled={!canEdit} onBlur={e => onPositionField(p.id, "grade", e.target.value.toUpperCase())} />
          </div>
          <div className="field-group">
            <label className="field-label">Org unit</label>
            <select className="field-input field-select" defaultValue={p.org_unit} disabled={!canEdit} onChange={e => onPositionField(p.id, "org_unit", e.target.value)}>
              {units.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">Job template</label>
            <select className="field-input field-select" defaultValue={p.job_template ?? ""} disabled={!canEdit} onChange={e => onPositionField(p.id, "job_template", e.target.value || null)}>
              <option value="">None</option>
              {jobs.map(j => <option key={j.id} value={j.id}>{j.name}{j.band ? ` · ${j.band}` : ""}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">Company Code <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional — leave unset for a company-wide seat)</span></label>
            <select className="field-input field-select" defaultValue={p.branch ?? ""} disabled={!canEdit} onChange={e => onPositionField(p.id, "branch", e.target.value || null)}>
              <option value="">Company-wide</option>
              {branches.map(b => <option key={b.id} value={b.id}>{b.branch_name}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">Default role <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(suggested to HR when hiring into this seat)</span></label>
            <select className="field-input field-select" defaultValue={p.default_role ?? ""} disabled={!canEdit} onChange={e => onPositionField(p.id, "default_role", e.target.value || null)}>
              <option value="">None</option>
              {roles.map(r => <option key={r.id} value={r.id}>{r.display_name}</option>)}
            </select>
          </div>
        </div>
        <div style={{ marginTop: 4 }}>
          <ToggleSwitch
            checked={p.is_chief}
            disabled={!canEdit}
            onChange={() => onToggleChief(p)}
            label={<>This position is the <b>head</b> of {p.org_unit_name}.</>}
          />
        </div>

        <SectionTitle>Placement history</SectionTitle>
        {placementHistoryLoading && <div style={{ fontSize: 12.5, color: "var(--on-variant)", padding: "6px 0" }}>Loading…</div>}
        {!placementHistoryLoading && placementHistory.length === 0 && (
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", padding: "6px 0" }}>No placements yet on this seat.</div>
        )}
        {!placementHistoryLoading && placementHistory.map(pl => {
          const badge = STATUS_BADGE[pl.status];
          return (
            <div key={pl.id} style={{ display: "flex", alignItems: "center", gap: 11, padding: "9px 12px", border: "1px solid var(--outline-v)", borderRadius: 8, marginBottom: 7 }}>
              <Avatar name={pl.employee_name} size={26} />
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 570 }}>{pl.employee_name}</div>
                <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 1 }}>
                  {pl.effective_from} – {pl.effective_to ?? "present"}{pl.note ? ` · ${pl.note}` : ""}
                </div>
              </div>
              <span className="badge" style={{ background: badge.bg, color: badge.color, fontSize: 10.5, fontWeight: 650, padding: "3px 9px", borderRadius: 5, flexShrink: 0 }}>
                {badge.label}
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  // person
  const held = positions.filter(p => p.holder === selected.id);
  const name = held[0]?.holder_name ?? "Employee";
  const rep = held[0]?.reports_to;

  return (
    <div key={selected.id}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 13, marginBottom: 6 }}>
        <Avatar name={name} size={44} />
        <div>
          <div style={{ fontSize: 18, fontWeight: 680 }}>{name}</div>
          <div style={{ fontSize: 11, fontWeight: 650, letterSpacing: "0.04em", textTransform: "uppercase", color: "var(--on-variant)", marginTop: 3 }}>Employee</div>
        </div>
      </div>

      <SectionTitle>Holds</SectionTitle>
      {held.length === 0 && <div style={{ fontSize: 12.5, color: "var(--on-variant)" }}>Not placed on any position.</div>}
      {held.map(p => <PositionRow key={p.id} p={p} onSelect={() => onSelect({ type: "position", id: p.id })} onAssign={() => onAssign(p.id)} />)}

      <SectionTitle>Reporting</SectionTitle>
      <div className="field-group">
        <label className="field-label">Reports to</label>
        <input className="field-input" disabled value={rep ? `${rep.holder_name ?? "Vacant"} · ${rep.title}` : "—"} style={{ background: "var(--bg-low)", color: "var(--on-variant)" }} />
      </div>
    </div>
  );
}

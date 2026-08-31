"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useAnyPermission } from "@/hooks/usePermission";
import type { JobTemplate, OrgUnit, Placement, Position } from "@/types/orgStructure";
import OrgTree from "./OrgTree";
import OrgDetail from "./OrgDetail";
import AddUnitModal from "./AddUnitModal";
import AddPositionModal from "./AddPositionModal";
import AssignHolderModal from "./AssignHolderModal";
import EndPlacementModal from "./EndPlacementModal";
import ManageJobTemplatesModal from "./ManageJobTemplatesModal";

export interface EmployeeOption {
  id: string;
  full_name: string;
  employee_id: string;
}

export interface BranchOption {
  id: number;
  branch_name: string;
}

export type Selected = { type: "unit" | "position" | "person"; id: string } | null;

export default function OrgStructureClient() {
  const canEdit = useAnyPermission("org_structure.create", "org_structure.edit", "org_structure.delete");

  const [units,     setUnits]     = useState<OrgUnit[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [jobs,       setJobs]       = useState<JobTemplate[]>([]);
  const [employees,  setEmployees]  = useState<EmployeeOption[]>([]);
  const [branches,   setBranches]   = useState<BranchOption[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [loadError,  setLoadError]  = useState<string | null>(null);

  const [selected, setSelected] = useState<Selected>(null);
  const [search,   setSearch]   = useState("");
  const [branchFilter, setBranchFilter] = useState("");

  const [addUnitParent,    setAddUnitParent]    = useState<string | null | "new">(null);
  const [addPositionUnit,  setAddPositionUnit]  = useState<string | null>(null);
  const [assignPositionId, setAssignPositionId] = useState<string | null>(null);
  const [endPositionId,    setEndPositionId]    = useState<string | null>(null);
  const [manageJobsOpen,   setManageJobsOpen]   = useState(false);

  const [placementHistory,        setPlacementHistory]        = useState<Placement[]>([]);
  const [placementHistoryLoading, setPlacementHistoryLoading] = useState(false);

  // OrgDetail's fields auto-save on blur/change (no Save button, by design —
  // same pattern as Job Templates and the Document Type settings table).
  // This surfaces that as a brief "Saving…"/"Saved" pill so it doesn't look
  // like nothing happened, and — as importantly — actually shows the user
  // when a save silently failed instead of leaving the field looking saved
  // when it wasn't.
  const [saveStatus, setSaveStatus] = useState<{ state: "saving" | "saved" | "error"; message?: string } | null>(null);
  const saveStatusTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  function beginFieldSave() {
    if (saveStatusTimeout.current) clearTimeout(saveStatusTimeout.current);
    setSaveStatus({ state: "saving" });
  }
  function fieldSaveSucceeded() {
    setSaveStatus({ state: "saved" });
    saveStatusTimeout.current = setTimeout(() => setSaveStatus(null), 2000);
  }
  function fieldSaveFailed(err: unknown) {
    setSaveStatus({ state: "error", message: (err as { message?: string })?.message ?? "Failed to save — try again." });
  }

  async function load() {
    setLoading(true);
    setLoadError(null);
    try {
      const [unitsRes, posRes, jobsRes, empRes, branchRes] = await Promise.all([
        clientApi.get(`${API.orgStructure.units.list}?page_size=200`),
        clientApi.get(`${API.orgStructure.positions.list}?page_size=200`),
        clientApi.get(API.orgStructure.jobTemplates.list),
        clientApi.get(API.employees.list, { params: { page_size: 200, status: "active" } }),
        clientApi.get(API.branches.list, { params: { page_size: 200 } }),
      ]);
      setUnits(unitsRes.data?.data?.results ?? []);
      setPositions(posRes.data?.data?.results ?? []);
      setJobs(jobsRes.data?.data ?? []);
      setEmployees(empRes.data?.data?.results ?? []);
      setBranches(branchRes.data?.data?.results ?? []);
    } catch (err: unknown) {
      setLoadError((err as { message?: string })?.message ?? "Failed to load organisation structure.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (selected?.type !== "position") { setPlacementHistory([]); return; }
    let cancelled = false;
    setPlacementHistoryLoading(true);
    clientApi.get(API.orgStructure.positions.placements(selected.id))
      .then(res => { if (!cancelled) setPlacementHistory(res.data?.data ?? []); })
      .catch(() => { if (!cancelled) setPlacementHistory([]); })
      .finally(() => { if (!cancelled) setPlacementHistoryLoading(false); });
    return () => { cancelled = true; };
  }, [selected]);

  const stats = useMemo(() => {
    const vacant = positions.filter(p => !p.holder).length;
    const placed = new Set(positions.filter(p => p.holder).map(p => p.holder));
    return { units: units.length, positions: positions.length, vacant, placed: placed.size };
  }, [units, positions]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, gap: 10, color: "var(--on-variant)" }}>
        <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "spin 1s linear infinite" }} />
        Loading organisation structure…
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Organization Management</div>
          <div className="page-sub">Org units, the positions inside them, and who holds each seat. Modeled on positions, so structure exists before anyone is hired.</div>
        </div>
        {canEdit && (
          <div className="page-actions">
            <button className="btn btn-ghost" onClick={() => setManageJobsOpen(true)}>
              <i className="ti ti-briefcase" /> Manage job templates
            </button>
            <button className="btn btn-filled" onClick={() => setAddUnitParent("new")}>
              <i className="ti ti-plus" /> Add org unit
            </button>
          </div>
        )}
      </div>

      {loadError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /> <div>{loadError}</div>
        </div>
      )}

      <div className="alert alert-info mb-16" style={{ alignItems: "flex-start" }}>
        <i className="ti ti-info-circle" />
        <div>
          A unit&apos;s head is a <strong>position</strong>, not a person. You mark one position in each unit as <strong>chief</strong>;
          whoever holds it is the head. The seat can stay <strong>vacant</strong> until you hire, so you never have to invent an
          employee just to create a unit.
        </div>
      </div>

      <div className="stats-grid mb-16">
        <div className="stat-card">
          <div className="stat-icon si-primary"><i className="ti ti-sitemap" /></div>
          <div className="stat-label">Org Units</div>
          <div className="stat-value">{stats.units}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-primary"><i className="ti ti-id-badge-2" /></div>
          <div className="stat-label">Positions</div>
          <div className="stat-value">{stats.positions}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-warn"><i className="ti ti-user-question" /></div>
          <div className="stat-label">Vacant Positions</div>
          <div className="stat-value">{stats.vacant}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-primary"><i className="ti ti-users" /></div>
          <div className="stat-label">People Placed</div>
          <div className="stat-value">{stats.placed}</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: 16, alignItems: "start" }} className="org-split">
        <div className="card" style={{ overflow: "hidden" }}>
          <div className="card-header">
            <div>
              <div className="card-title">Structure</div>
              <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 2 }}>Org units · positions · holders</div>
            </div>
          </div>
          <div style={{ padding: 8 }}>
            <div style={{ position: "relative", margin: "6px 8px 0" }}>
              <i className="ti ti-search" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", fontSize: 14, color: "var(--outline)" }} />
              <input
                className="field-input"
                style={{ paddingLeft: 32 }}
                placeholder="Find unit, position or person"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <div style={{ margin: "8px 8px" }}>
              <select
                className="field-input"
                value={branchFilter}
                onChange={e => setBranchFilter(e.target.value)}
                title="Positions with no branch set always show, in every view"
              >
                <option value="">All branches</option>
                {branches.map(b => <option key={b.id} value={b.id}>{b.branch_name}</option>)}
              </select>
            </div>
            <div className="org-tree-scroll" style={{ maxHeight: 640, overflow: "auto" }}>
              <OrgTree
                units={units} positions={positions} search={search}
                branchFilter={branchFilter ? Number(branchFilter) : null}
                selected={selected} onSelect={setSelected}
              />
            </div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, padding: "10px 16px", borderTop: "1px solid var(--outline-v)", background: "var(--bg-low)", fontSize: 11, color: "var(--on-variant)" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span className="orgnode-glyph" style={{ background: "var(--primary-container, rgba(30,78,140,0.12))", color: "var(--primary)" }}>O</span> Org unit</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span className="orgnode-glyph" style={{ background: "var(--info-c)", color: "var(--info)" }}>S</span> Position</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span className="orgnode-glyph" style={{ background: "var(--success-c)", color: "var(--success)" }}>P</span> Employee</span>
            <span><i className="ti ti-crown" style={{ color: "var(--warn)" }} /> Chief</span>
            <span className="badge badge-warn">Vacant</span>
          </div>
        </div>

        <div className="card" style={{ position: "relative" }}>
          {saveStatus && (
            <div
              role="status"
              style={{
                position: "absolute", top: 14, right: 16, zIndex: 5,
                display: "flex", alignItems: "center", gap: 6,
                fontSize: 12, fontWeight: 600, padding: "5px 11px", borderRadius: 20,
                ...(saveStatus.state === "saving"
                  ? { background: "var(--bg-low)", color: "var(--on-variant)", border: "1px solid var(--outline-v)" }
                  : saveStatus.state === "saved"
                  ? { background: "var(--success-c)", color: "var(--success)", border: "1px solid var(--success)" }
                  : { background: "rgba(220,38,38,0.06)", color: "var(--error)", border: "1px solid rgba(220,38,38,0.3)" }),
              }}
            >
              {saveStatus.state === "saving" && <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>}
              {saveStatus.state === "saved" && <><i className="ti ti-check" /> Saved</>}
              {saveStatus.state === "error" && (
                <>
                  <i className="ti ti-alert-circle" /> {saveStatus.message}
                  <button
                    onClick={() => setSaveStatus(null)}
                    style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 0, marginLeft: 4, display: "flex" }}
                    title="Dismiss"
                  >
                    <i className="ti ti-x" style={{ fontSize: 12 }} />
                  </button>
                </>
              )}
            </div>
          )}
          <div style={{ padding: "18px 20px" }}>
            <OrgDetail
              selected={selected} units={units} positions={positions} jobs={jobs} branches={branches} canEdit={canEdit}
              placementHistory={placementHistory} placementHistoryLoading={placementHistoryLoading}
              onSelect={setSelected}
              onAddSubUnit={unitId => setAddUnitParent(unitId)}
              onAddPosition={unitId => setAddPositionUnit(unitId)}
              onAssign={positionId => setAssignPositionId(positionId)}
              onVacate={positionId => setEndPositionId(positionId)}
              onCancelScheduled={async placementId => {
                await clientApi.delete(API.orgStructure.placements.detail(placementId));
                load();
              }}
              onUnitField={async (unitId, field, value) => {
                beginFieldSave();
                try {
                  await clientApi.put(API.orgStructure.units.detail(unitId), { [field]: value });
                  await load();
                  fieldSaveSucceeded();
                } catch (err) {
                  fieldSaveFailed(err);
                }
              }}
              onPositionField={async (positionId, field, value) => {
                beginFieldSave();
                try {
                  await clientApi.put(API.orgStructure.positions.detail(positionId), { [field]: value });
                  await load();
                  fieldSaveSucceeded();
                } catch (err) {
                  fieldSaveFailed(err);
                }
              }}
              onToggleChief={async position => {
                beginFieldSave();
                try {
                  await clientApi.put(API.orgStructure.positions.detail(position.id), { is_chief: !position.is_chief });
                  await load();
                  fieldSaveSucceeded();
                } catch (err) {
                  fieldSaveFailed(err);
                }
              }}
            />
          </div>
        </div>
      </div>

      {addUnitParent !== null && (
        <AddUnitModal
          units={units}
          parentId={addUnitParent === "new" ? null : addUnitParent}
          onClose={() => setAddUnitParent(null)}
          onCreated={unit => { setAddUnitParent(null); setSelected({ type: "unit", id: unit.id }); load(); }}
        />
      )}
      {addPositionUnit !== null && (
        <AddPositionModal
          unit={units.find(u => u.id === addPositionUnit) ?? null}
          jobs={jobs}
          branches={branches}
          hasChief={positions.some(p => p.org_unit === addPositionUnit && p.is_chief)}
          onClose={() => setAddPositionUnit(null)}
          onCreated={position => { setAddPositionUnit(null); setSelected({ type: "position", id: position.id }); load(); }}
        />
      )}
      {assignPositionId !== null && (
        <AssignHolderModal
          position={positions.find(p => p.id === assignPositionId) ?? null}
          employees={employees}
          onClose={() => setAssignPositionId(null)}
          onAssigned={() => { setAssignPositionId(null); load(); }}
        />
      )}
      {endPositionId !== null && (
        <EndPlacementModal
          position={positions.find(p => p.id === endPositionId) ?? null}
          onClose={() => setEndPositionId(null)}
          onEnded={() => { setEndPositionId(null); load(); }}
        />
      )}
      {manageJobsOpen && (
        <ManageJobTemplatesModal
          jobs={jobs}
          canEdit={canEdit}
          onClose={() => setManageJobsOpen(false)}
          onChanged={load}
        />
      )}
    </>
  );
}

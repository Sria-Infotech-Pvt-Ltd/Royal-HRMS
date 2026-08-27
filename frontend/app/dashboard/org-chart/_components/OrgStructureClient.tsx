"use client";

import { useEffect, useMemo, useState } from "react";
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

export interface EmployeeOption {
  id: string;
  full_name: string;
  employee_id: string;
}

export interface BranchOption {
  id: number;
  branch_name: string;
}

export interface DepartmentOption {
  id: number;
  name: string;
}

export type Selected = { type: "unit" | "position" | "person"; id: string } | null;

export default function OrgStructureClient() {
  const canEdit = useAnyPermission("org_structure.create", "org_structure.edit", "org_structure.delete");

  const [units,     setUnits]     = useState<OrgUnit[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [jobs,       setJobs]       = useState<JobTemplate[]>([]);
  const [employees,  setEmployees]  = useState<EmployeeOption[]>([]);
  const [branches,   setBranches]   = useState<BranchOption[]>([]);
  const [departments, setDepartments] = useState<DepartmentOption[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [loadError,  setLoadError]  = useState<string | null>(null);

  const [selected, setSelected] = useState<Selected>(null);
  const [search,   setSearch]   = useState("");
  const [branchFilter, setBranchFilter] = useState("");

  const [addUnitParent,    setAddUnitParent]    = useState<string | null | "new">(null);
  const [addPositionUnit,  setAddPositionUnit]  = useState<string | null>(null);
  const [assignPositionId, setAssignPositionId] = useState<string | null>(null);
  const [endPositionId,    setEndPositionId]    = useState<string | null>(null);

  const [placementHistory,        setPlacementHistory]        = useState<Placement[]>([]);
  const [placementHistoryLoading, setPlacementHistoryLoading] = useState(false);

  async function load() {
    setLoading(true);
    setLoadError(null);
    try {
      const [unitsRes, posRes, jobsRes, empRes, branchRes, deptRes] = await Promise.all([
        clientApi.get(`${API.orgStructure.units.list}?page_size=200`),
        clientApi.get(`${API.orgStructure.positions.list}?page_size=200`),
        clientApi.get(API.orgStructure.jobTemplates),
        clientApi.get(API.employees.list, { params: { page_size: 200, status: "active" } }),
        clientApi.get(API.branches.list, { params: { page_size: 200 } }),
        clientApi.get(API.departments.list, { params: { page_size: 200 } }),
      ]);
      setUnits(unitsRes.data?.data?.results ?? []);
      setPositions(posRes.data?.data?.results ?? []);
      setJobs(jobsRes.data?.data ?? []);
      setEmployees(empRes.data?.data?.results ?? []);
      setBranches(branchRes.data?.data?.results ?? []);
      setDepartments(deptRes.data?.data?.results ?? []);
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
          <div className="page-title">Organisation Structure</div>
          <div className="page-sub">Org units, the positions inside them, and who holds each seat. Modeled on positions, so structure exists before anyone is hired.</div>
        </div>
        {canEdit && (
          <div className="page-actions">
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
            <div style={{ maxHeight: 640, overflow: "auto" }}>
              <OrgTree
                units={units} positions={positions} search={search}
                branchFilter={branchFilter ? Number(branchFilter) : null}
                selected={selected} onSelect={setSelected}
              />
            </div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, padding: "10px 16px", borderTop: "1px solid var(--outline-v)", background: "var(--bg-low)", fontSize: 11, color: "var(--on-variant)" }}>
            <span><i className="ti ti-square-rounded" style={{ color: "var(--primary)" }} /> Org unit</span>
            <span><i className="ti ti-square-rounded" style={{ color: "var(--info)" }} /> Position</span>
            <span><i className="ti ti-square-rounded" style={{ color: "var(--success)" }} /> Employee</span>
            <span><i className="ti ti-crown" style={{ color: "var(--warn)" }} /> Chief</span>
            <span className="badge badge-warn">Vacant</span>
          </div>
        </div>

        <div className="card">
          <div style={{ padding: "18px 20px" }}>
            <OrgDetail
              selected={selected} units={units} positions={positions} jobs={jobs} branches={branches} departments={departments} canEdit={canEdit}
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
                await clientApi.put(API.orgStructure.units.detail(unitId), { [field]: value });
                load();
              }}
              onPositionField={async (positionId, field, value) => {
                await clientApi.put(API.orgStructure.positions.detail(positionId), { [field]: value });
                load();
              }}
              onToggleChief={async position => {
                await clientApi.put(API.orgStructure.positions.detail(position.id), { is_chief: !position.is_chief });
                load();
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
    </>
  );
}

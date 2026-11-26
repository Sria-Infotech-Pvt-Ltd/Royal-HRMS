"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useAnyPermission, usePermission } from "@/hooks/usePermission";
import { useFetch } from "@/hooks/useFetch";
import { useT } from "@/hooks/useI18n";
import type { JobTemplate, OrgUnit, Placement, Position } from "@/types/orgStructure";
import OrgTree, { type SeatFilter, type TreeCommand } from "./OrgTree";
import OrgDetail from "./OrgDetail";
import OrgChartView from "./OrgChartView";
import OrgOverview from "./OrgOverview";
import OrgReportingChart from "./OrgReportingChart";
import { buildPositionsCsv, downloadTextFile } from "@/lib/orgExport";
import { findAttention, rollupUnits } from "@/lib/orgStructureStats";
import AddUnitModal from "./AddUnitModal";
import AddPositionModal from "./AddPositionModal";
import AssignHolderModal from "./AssignHolderModal";
import SearchableSelect from "@/components/SearchableSelect";
import EndPlacementModal from "./EndPlacementModal";
import DeactivatePositionModal from "./DeactivatePositionModal";
import PositionPermissionsModal from "./PositionPermissionsModal";
import ManageJobTemplatesModal from "./ManageJobTemplatesModal";
import BulkMoveOrgUnitModal from "@/components/orgMove/BulkMoveOrgUnitModal";
import { confirmDialog } from "@/components/DialogProvider";

export interface EmployeeOption {
  /** The employee code (e.g. 10000002), shown to people. */
  id: string;
  /** The database id: what the placement API expects as `employee`. */
  uuid: string;
  full_name: string;
  employee_id: string;
}

export interface BranchOption {
  id: number;
  branch_name: string;
}

export type OrgView = "tree" | "chart" | "reporting";

const VIEW_OPTIONS: { mode: OrgView; label: string; icon: string }[] = [
  { mode: "tree", label: "Tree view", icon: "ti-list-tree" },
  { mode: "chart", label: "Unit chart", icon: "ti-sitemap" },
  { mode: "reporting", label: "Reporting line", icon: "ti-hierarchy-3" },
];

export type Selected = { type: "unit" | "position" | "person"; id: string } | null;

export default function OrgStructureClient({ onBack, initialSelectedUnitId }: { onBack?: () => void; initialSelectedUnitId?: string }) {
  const t = useT();
  const canEdit = useAnyPermission("org_structure.create", "org_structure.edit", "org_structure.delete");
  const canDelete = usePermission("org_structure.delete");
  const canManagePermissions = usePermission("settings.edit");
  // Moving people between units changes their employee record, so it needs employees.edit (the same check the server makes).
  const canMoveEmployees = usePermission("employees.edit");
  // null = closed; "" = open with no "Move from" preset; a unit id = opened from that unit.
  const [moveFromUnitId, setMoveFromUnitId] = useState<string | null>(null);

  const [units,     setUnits]     = useState<OrgUnit[]>([]);
  const [positions, setPositions] = useState<Position[]>([]);
  const [jobs,       setJobs]       = useState<JobTemplate[]>([]);
  // Employees and branches only feed the edit pop-ups and the branch filter. Ask for them only when the viewer may read them:
  // an ordinary employee would be refused (403) on both lists, which is a red console error and a wasted request. The chart
  // itself must not depend on them, so a viewer without access simply gets empty lists, as before.
  const canListEmployees = usePermission("employees.view");
  const canListBranches  = usePermission("branches.view");
  const { data: employeesPage } = useFetch<{ results: EmployeeOption[] }>(canListEmployees ? `${API.employees.list}?page_size=200&status=active` : null);
  const { data: branchesPage }  = useFetch<{ results: BranchOption[] }>(canListBranches ? `${API.branches.list}?page_size=200` : null);
  const employees: EmployeeOption[] = employeesPage?.results ?? [];
  const branches: BranchOption[]    = branchesPage?.results ?? [];
  const [loading,    setLoading]    = useState(true);
  const [loadError,  setLoadError]  = useState<string | null>(null);

  const [selected, replaceSelected] = useState<Selected>(
    initialSelectedUnitId ? { type: "unit", id: initialSelectedUnitId } : null,
  );
  // What was open before, so the details panel can step Back (e.g. unit -> its position -> the person in it).
  const [history, setHistory] = useState<Selected[]>([]);
  const detailRef = useRef<HTMLDivElement>(null);
  const [search,   setSearch]   = useState("");
  const [branchFilter, setBranchFilter] = useState("");
  const [view, setView] = useState<OrgView>("tree");
  const [seatFilter, setSeatFilter] = useState<SeatFilter>("all");
  const [treeCommand, setTreeCommand] = useState<TreeCommand | null>(null);

  const [addUnitParent,    setAddUnitParent]    = useState<string | null | "new">(null);
  const [addPositionUnit,  setAddPositionUnit]  = useState<string | null>(null);
  const [assignPositionId, setAssignPositionId] = useState<string | null>(null);
  const [endPositionId,    setEndPositionId]    = useState<string | null>(null);
  const [deactivatePositionId, setDeactivatePositionId] = useState<string | null>(null);
  const [permissionsPositionId, setPermissionsPositionId] = useState<string | null>(null);
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
    setSaveStatus({ state: "error", message: (err as { message?: string })?.message ?? t("Failed to save — try again.") });
  }

  async function load() {
    setLoading(true);
    setLoadError(null);
    try {
      const [unitsRes, posRes, jobsRes] = await Promise.all([
        clientApi.get(`${API.orgStructure.units.list}?page_size=1000`),
        clientApi.get(`${API.orgStructure.positions.list}?page_size=1000`),
        clientApi.get(API.orgStructure.jobTemplates.list),
      ]);
      setUnits(unitsRes.data?.data?.results ?? []);
      setPositions(posRes.data?.data?.results ?? []);
      setJobs(jobsRes.data?.data ?? []);
    } catch (err: unknown) {
      setLoadError((err as { message?: string })?.message ?? t("Failed to load organisation structure."));
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

  function setSelected(next: Selected) {
    if (next === null) { setHistory([]); replaceSelected(null); return; }
    if (selected && (selected.type !== next.type || selected.id !== next.id)) setHistory(previous => [...previous.slice(-19), selected]);
    replaceSelected(next);
  }

  function goBack() {
    const stillExists = (item: Selected) => item === null ? false
      : item.type === "unit" ? units.some(unit => unit.id === item.id)
      : item.type === "position" ? positions.some(position => position.id === item.id)
      : positions.some(position => position.holder === item.id);
    const remaining = [...history];
    let target: Selected = null;
    // Skip anything that has been deleted since.
    while (remaining.length > 0) {
      const candidate = remaining.pop() ?? null;
      if (stillExists(candidate)) { target = candidate; break; }
    }
    setHistory(remaining);
    replaceSelected(target);
  }

  const rollups = useMemo(() => rollupUnits(units, positions), [units, positions]);
  const isDrawer = view !== "tree";
  const attention = useMemo(() => findAttention(units, rollups), [units, rollups]);
  const hasSelection = selected !== null;

  // Escape closes the slide-over details of the chart views.
  useEffect(() => {
    if (view === "tree" || !hasSelection) return;
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { setHistory([]); replaceSelected(null); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [view, hasSelection]);

  // On a phone the tree view stacks the details below the tree: bring them into view when something is tapped.
  useEffect(() => {
    if (view !== "tree" || !selected || typeof window.matchMedia !== "function") return;
    if (window.matchMedia("(max-width: 900px)").matches) detailRef.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  }, [view, selected]);
  // The chart draws units only, so a selected seat highlights the unit it sits in.
  const selectedUnitId = selected?.type === "unit"
    ? selected.id
    : selected?.type === "position" ? positions.find(p => p.id === selected.id)?.org_unit ?? null : null;

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, gap: 10, color: "var(--on-variant)" }}>
        <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "spin 1s linear infinite" }} />
        {t("Loading organisation structure…")}
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">{t("Organization Management")}</div>
          <div className="page-sub">{t("Org units, the positions inside them, and who holds each seat. Modeled on positions, so structure exists before anyone is hired.")}</div>
        </div>
        {(canEdit || canMoveEmployees || onBack) && (
          <div className="page-actions">
            {canEdit && (
              <button className="btn btn-ghost" onClick={() => setManageJobsOpen(true)}>
                <i className="ti ti-briefcase" /> {t("Manage job templates")}
              </button>
            )}
            {canMoveEmployees && (
              <button className="btn btn-ghost" onClick={() => setMoveFromUnitId("")}>
                <i className="ti ti-arrows-exchange" /> {t("Move employees")}
              </button>
            )}
            {canEdit && (
              <button className="btn btn-filled" onClick={() => setAddUnitParent("new")}>
                <i className="ti ti-plus" /> {t("Add org unit")}
              </button>
            )}
            {onBack && (
              <button className="btn btn-ghost" onClick={onBack}>
                <i className="ti ti-arrow-left" /> {t("Back")}
              </button>
            )}
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
          {t("A unit's head is a")} <strong>{t("position")}</strong>{t(", not a person. You mark one position in each unit as")} <strong>{t("chief")}</strong>{t("; whoever holds it is the head. The seat can stay")} <strong>{t("vacant")}</strong> {t("until you hire, so you never have to invent an employee just to create a unit.")}
          <span style={{ display: "block", marginTop: 6 }}>
            {t("To set access, select a position and choose")} <strong>{t("Permissions")}</strong>{t(". Access belongs to that seat—not the reporting chain; employees sharing a seat share its permissions. Use separate positions when employees need different access.")}
          </span>
        </div>
      </div>

      <div className="stats-grid mb-16">
        <div className="stat-card">
          <div className="stat-icon si-primary"><i className="ti ti-sitemap" /></div>
          <div className="stat-label">{t("Org Units")}</div>
          <div className="stat-value">{stats.units}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-primary"><i className="ti ti-id-badge-2" /></div>
          <div className="stat-label">{t("Positions")}</div>
          <div className="stat-value">{stats.positions}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-warn"><i className="ti ti-user-question" /></div>
          <div className="stat-label">{t("Vacant Positions")}</div>
          <div className="stat-value">{stats.vacant}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-primary"><i className="ti ti-users" /></div>
          <div className="stat-label">{t("People Placed")}</div>
          <div className="stat-value">{stats.placed}</div>
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8, marginBottom: 10, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-ghost btn-sm" title={t("Download every position as a spreadsheet file")}
          onClick={() => downloadTextFile(`organization-positions-${new Date().toISOString().slice(0, 10)}.csv`, buildPositionsCsv(units, positions))}>
          <i className="ti ti-download" /> {t("Export positions")}
        </button>
        <div role="group" aria-label={t("View")} style={{ display: "inline-flex", border: "1px solid var(--outline-v)", borderRadius: 8, overflow: "hidden" }}>
          {VIEW_OPTIONS.map(({ mode, label, icon }) => (
            <button key={mode} type="button" aria-pressed={view === mode} onClick={() => setView(mode)}
              style={{ padding: "6px 14px", border: "none", cursor: "pointer", fontSize: 12.5, fontWeight: 600, background: view === mode ? "var(--primary)" : "transparent", color: view === mode ? "#fff" : "var(--on-variant)" }}>
              <i className={`ti ${icon}`} /> {t(label)}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: view === "tree" ? "360px 1fr" : "minmax(0, 1fr)", gap: 16, alignItems: "start" }} className="org-split">
        {view !== "tree" ? (
          <div className="card" style={{ overflow: "hidden" }}>
            <div className="card-header"><div>
              <div className="card-title">{view === "chart" ? t("Unit chart") : t("Reporting line")}</div>
              <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 2 }}>
                {view === "chart" ? t("One box per org unit · click a box for details") : t("One box per position, joined by who it reports to · click a box for details")}
              </div></div></div>
            <div style={{ padding: 12 }}>
              {view === "chart" ? (
                <OrgChartView units={units} positions={positions} rollups={rollups} selectedUnitId={selectedUnitId}
                  onSelectUnit={unitId => setSelected({ type: "unit", id: unitId })} />
              ) : (
                <OrgReportingChart positions={positions} selectedPositionId={selected?.type === "position" ? selected.id : null}
                  onSelectPosition={positionId => setSelected({ type: "position", id: positionId })} />
              )}
            </div>
          </div>
        ) : (
        <div className="card" style={{ overflow: "hidden" }}>
          <div className="card-header">
            <div>
              <div className="card-title">{t("Structure")}</div>
              <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 2 }}>{t("Org units · positions · holders")}</div>
            </div>
          </div>
          <div style={{ padding: 8 }}>
            <div style={{ position: "relative", margin: "6px 8px 0" }}>
              <i className="ti ti-search" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", fontSize: 14, color: "var(--outline)" }} />
              <input
                className="field-input"
                style={{ paddingLeft: 32 }}
                placeholder={t("Find unit, position or person")}
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <div style={{ margin: "8px 8px" }}>
              <SearchableSelect
                inputClassName="field-input"
                value={branchFilter}
                onChange={setBranchFilter}
                placeholder={t("All Company Codes")}
                options={branches.map(b => ({ value: String(b.id), label: b.branch_name }))}
              />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 6, margin: "0 8px 8px" }}>
              {(["all", "vacant", "filled"] as const).map(option => (
                <button key={option} type="button" aria-pressed={seatFilter === option} onClick={() => setSeatFilter(option)}
                  className={seatFilter === option ? "btn btn-filled btn-sm" : "btn btn-ghost btn-sm"}>
                  {option === "all" ? t("All") : option === "vacant" ? t("Vacant") : t("Filled")}
                </button>
              ))}
              <span style={{ flex: 1 }} />
              <button type="button" className="btn btn-ghost btn-sm" title={t("Expand all")} aria-label={t("Expand all")}
                onClick={() => setTreeCommand(previous => ({ id: (previous?.id ?? 0) + 1, action: "expand" }))}><i className="ti ti-arrows-diagonal" /></button>
              <button type="button" className="btn btn-ghost btn-sm" title={t("Collapse all")} aria-label={t("Collapse all")}
                onClick={() => setTreeCommand(previous => ({ id: (previous?.id ?? 0) + 1, action: "collapse" }))}><i className="ti ti-arrows-diagonal-minimize-2" /></button>
            </div>
            <div className="org-tree-scroll" style={{ maxHeight: 640, overflow: "auto" }}>
              <OrgTree
                units={units} positions={positions} search={search}
                branchFilter={branchFilter ? Number(branchFilter) : null}
                selected={selected} onSelect={setSelected}
                rollups={rollups} seatFilter={seatFilter} command={treeCommand}
              />
            </div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, padding: "10px 16px", borderTop: "1px solid var(--outline-v)", background: "var(--bg-low)", fontSize: 11, color: "var(--on-variant)" }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span className="orgnode-glyph" style={{ background: "var(--primary-container, color-mix(in srgb, var(--brand) 12%, transparent))", color: "var(--primary)" }}>O</span> {t("Org unit")}</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span className="orgnode-glyph" style={{ background: "var(--info-c)", color: "var(--info)" }}>S</span> {t("Position")}</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><span className="orgnode-glyph" style={{ background: "var(--success-c)", color: "var(--success)" }}>P</span> {t("Employee")}</span>
            <span><i className="ti ti-crown" style={{ color: "var(--warn)" }} /> {t("Chief")}</span>
            <span className="badge badge-warn">{t("Vacant")}</span>
            <span><span className="orgnode-count" style={{ fontSize: 10.5, fontWeight: 650, padding: "1px 7px", borderRadius: 10, border: "1px solid var(--outline-v)" }}>3/5</span> {t("filled / seats")}</span>
          </div>
        </div>
        )}

        {/* In the chart views the chart takes the whole width and the details open as a slide-over panel. */}
        <div className="card" ref={detailRef} style={isDrawer ? {
          position: "fixed", top: 76, right: 16, bottom: 16, width: 460, maxWidth: "calc(100vw - 32px)", zIndex: 60, overflow: "auto",
          display: selected ? "block" : "none", boxShadow: "0 24px 64px rgba(15, 23, 42, 0.28)", borderRadius: 16,
        } : { position: "relative" }}>
          {isDrawer && (
            <button type="button" onClick={() => setSelected(null)} aria-label={t("Close details")} title={t("Close")}
              style={{ position: "absolute", top: 12, right: 12, zIndex: 6, width: 30, height: 30, borderRadius: 15, border: "1px solid var(--outline-v)", background: "var(--surface, #fff)", cursor: "pointer", color: "var(--on-variant)" }}>
              <i className="ti ti-x" />
            </button>
          )}
          {saveStatus && (
            <div
              role="status"
              style={{
                position: "absolute", top: 14, right: isDrawer ? 52 : 16, zIndex: 5,
                display: "flex", alignItems: "center", gap: 6,
                fontSize: 12, fontWeight: 600, padding: "5px 11px", borderRadius: 20,
                ...(saveStatus.state === "saving"
                  ? { background: "var(--bg-low)", color: "var(--on-variant)", border: "1px solid var(--outline-v)" }
                  : saveStatus.state === "saved"
                  ? { background: "var(--success-c)", color: "var(--success)", border: "1px solid var(--success)" }
                  : { background: "rgba(220,38,38,0.06)", color: "var(--error)", border: "1px solid rgba(220,38,38,0.3)" }),
              }}
            >
              {saveStatus.state === "saving" && <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> {t("Saving…")}</>}
              {saveStatus.state === "saved" && <><i className="ti ti-check" /> {t("Saved")}</>}
              {saveStatus.state === "error" && (
                <>
                  <i className="ti ti-alert-circle" /> {saveStatus.message}
                  <button
                    onClick={() => setSaveStatus(null)}
                    style={{ background: "none", border: "none", color: "inherit", cursor: "pointer", padding: 0, marginLeft: 4, display: "flex" }}
                    title={t("Dismiss")}
                   aria-label={t("Dismiss")}>
                    <i className="ti ti-x" style={{ fontSize: 12 }} />
                  </button>
                </>
              )}
            </div>
          )}
          <div style={{ padding: "18px 20px" }}>
            {history.length > 0 && selected && (
              <button type="button" className="btn btn-ghost btn-sm" onClick={goBack} style={{ marginBottom: 12 }}>
                <i className="ti ti-arrow-left" /> {t("Back")}
              </button>
            )}
            {!selected ? (
              <OrgOverview attention={attention} onSelectUnit={unitId => setSelected({ type: "unit", id: unitId })} />
            ) : (
            <OrgDetail
              selected={selected} units={units} positions={positions} jobs={jobs} branches={branches} canEdit={canEdit}
              placementHistory={placementHistory} placementHistoryLoading={placementHistoryLoading}
              onSelect={setSelected}
              onMoveEmployees={canMoveEmployees ? unitId => setMoveFromUnitId(unitId) : undefined}
              onAddSubUnit={unitId => setAddUnitParent(unitId)}
              onDeleteUnit={async unitId => {
                beginFieldSave();
                try {
                  await clientApi.delete(API.orgStructure.units.detail(unitId));
                  setSelected(null);
                  await load();
                  fieldSaveSucceeded();
                } catch (err) {
                  fieldSaveFailed(err);
                }
              }}
              onAddPosition={unitId => setAddPositionUnit(unitId)}
              onAssign={positionId => setAssignPositionId(positionId)}
              onVacate={positionId => setEndPositionId(positionId)}
              onDeactivate={positionId => setDeactivatePositionId(positionId)}
              canManagePermissions={canManagePermissions}
              onPermissions={positionId => setPermissionsPositionId(positionId)}
              canDelete={canDelete}
              onDelete={async positionId => {
                beginFieldSave();
                try {
                  await clientApi.delete(API.orgStructure.positions.detail(positionId));
                  setSelected(null);
                  await load();
                  fieldSaveSucceeded();
                } catch (err) {
                  fieldSaveFailed(err);
                }
              }}
              onReactivate={async positionId => {
                beginFieldSave();
                try {
                  await clientApi.post(API.orgStructure.positions.activate(positionId));
                  await load();
                  fieldSaveSucceeded();
                } catch (err) {
                  fieldSaveFailed(err);
                }
              }}
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
                  const e = err as { status?: number; message?: string };
                  // Turning off is_department_level can silently change Leave
                  // Policy eligibility for employees currently resolving their
                  // department through this unit — the backend 409s with who's
                  // affected instead of just failing; confirm here, then
                  // resubmit with confirm_department_change so it's an
                  // informed choice, not a silent block.
                  if (field === "is_department_level" && e.status === 409 && e.message) {
                    if (await confirmDialog({ title: t("Proceed anyway?"), body: e.message, confirmLabel: t("Proceed") })) {
                      try {
                        await clientApi.put(API.orgStructure.units.detail(unitId), { [field]: value, confirm_department_change: true });
                        await load();
                        fieldSaveSucceeded();
                      } catch (retryErr) {
                        fieldSaveFailed(retryErr);
                      }
                    } else {
                      setSaveStatus(null);
                    }
                    return;
                  }
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
            )}
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
      {moveFromUnitId !== null && (
        <BulkMoveOrgUnitModal initialFromUnitId={moveFromUnitId} onClose={() => setMoveFromUnitId(null)} onDone={() => { load(); }} />
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
      {deactivatePositionId !== null && (
        <DeactivatePositionModal
          position={positions.find(p => p.id === deactivatePositionId) ?? null}
          onClose={() => setDeactivatePositionId(null)}
          onDeactivated={() => { setDeactivatePositionId(null); load(); }}
        />
      )}
      {permissionsPositionId !== null && (
        <PositionPermissionsModal
          position={positions.find(p => p.id === permissionsPositionId) ?? null}
          onClose={() => setPermissionsPositionId(null)}
          onSaved={() => { setPermissionsPositionId(null); load(); }}
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

"use client";

import { useEffect, useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useDepartmentOptions } from "@/hooks/useDepartmentOptions";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import {
  attendanceExportFilename, attendanceExportParams, exportRangeProblem,
  type AttendanceExportMode, type AttendanceExportScope,
} from "@/lib/attendanceExport";
import { useToast } from "@/components/ToastProvider";
import BranchFilterSelect from "@/components/BranchFilterSelect";
import type { DashboardData, PaginatedAttendance } from "@/types/attendance";
import ImportModal from "./ImportModal";
import AttendanceDetailDrawer from "./AttendanceDetailDrawer";

interface Props {
  onMutated?: () => void;
}

interface BranchOption { id: number; branch_name: string }

interface ExportEmployeeOption { id: string; employee_id: string; full_name: string; department: string; status?: string }

const STATUS_BADGE: Record<string, string> = {
  present:    "badge badge-success",
  late:       "badge badge-warn",
  absent:     "badge badge-error",
  on_leave:   "badge badge-info",
  half_day:   "badge badge-primary",
  weekly_off: "badge badge-neutral",
  holiday:    "badge badge-neutral",
};

const CHIP_CONFIG: { key: keyof DashboardData["summary_chips"]; label: string; color: string }[] = [
  { key: "present",    label: "Present",    color: "var(--success)" },
  { key: "late",       label: "Late",       color: "var(--warn)"    },
  { key: "absent",     label: "Absent",     color: "var(--error)"   },
  { key: "on_leave",   label: "On Leave",   color: "var(--info)"    },
  { key: "half_day",   label: "Half Day",   color: "var(--primary)" },
  { key: "weekly_off", label: "Weekly Off", color: "var(--outline)" },
];

function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

function shiftDate(iso: string, delta: number): string {
  const d = new Date(iso + "T00:00:00");
  d.setDate(d.getDate() + delta);
  return d.toISOString().slice(0, 10);
}

function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export default function AttendanceTab({ onMutated }: Props) {
  const { showToast } = useToast();
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);
  const canExport       = usePermission("attendance.export");
  const canImport       = usePermission("attendance.create");

  const [date, setDate]                 = useState(todayISO());
  const [branchInput, setBranchInput]   = useState("");
  const [department, setDepartment]     = useState("");
  const [page, setPage]                 = useState(1);
  const [showImport, setShowImport]     = useState(false);
  const [viewingId, setViewingId]       = useState<string | null>(null);
  const [exporting, setExporting]       = useState(false);
  const [exportMode, setExportMode]     = useState<AttendanceExportMode>("day");
  const [exportMonth, setExportMonth]   = useState(todayISO().slice(0, 7));
  const [exportFrom, setExportFrom]     = useState(`${todayISO().slice(0, 8)}01`);
  const [exportTo, setExportTo]         = useState(todayISO());
  const [exportScope, setExportScope]   = useState<AttendanceExportScope>("all");
  const [empQuery, setEmpQuery]         = useState("");
  const [empSearch, setEmpSearch]       = useState("");
  const [empDropOpen, setEmpDropOpen]   = useState(false);
  const [exportEmployee, setExportEmployee] = useState<ExportEmployeeOption | null>(null);

  // Search the employees API (already scoped to the caller's branch / direct
  // reports) as the user types, rather than loading a capped list up front.
  useEffect(() => {
    const t = setTimeout(() => setEmpSearch(empQuery.trim()), 300);
    return () => clearTimeout(t);
  }, [empQuery]);
  const empSearchUrl = canExport && exportScope === "single" && !exportEmployee && empSearch.length >= 2
    ? `${API.employees.list}${toQuery({ search: empSearch, page_size: 20 })}`
    : null;
  const { data: empResults, loading: empLoading, error: empError } =
    useFetch<{ results: ExportEmployeeOption[] }>(empSearchUrl);
  // The export only covers active employees.
  const empOptions = (empResults?.results ?? []).filter(e => e.status !== "inactive").slice(0, 8);

  // hr_admin never gets to choose a branch — it's always their own, locked.
  const branch = unrestricted ? branchInput : effectiveBranch;

  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(
    unrestricted ? `${API.branches.list}?page_size=100` : null
  );
  const branches    = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);
  const departments = useDepartmentOptions(unrestricted, effectiveBranch);

  const filters = { date, branch, department };

  // Wait for the user to resolve before firing any request — otherwise an
  // hr_admin's very first fetch would briefly go out unscoped.
  const recordsUrl   = user ? `${API.attendance.records}${toQuery({ ...filters, page, page_size: 20 })}` : null;
  const dashboardUrl = user ? `${API.attendance.dashboard}${toQuery(filters)}` : null;

  const { data: records, loading, error, refetch: refetchRecords } = useFetch<PaginatedAttendance>(recordsUrl);
  const { data: dashboard, refetch: refetchChips } = useFetch<DashboardData>(dashboardUrl);

  const rows  = useMemo(() => records?.results ?? [], [records]);
  const chips = dashboard?.summary_chips;

  function refetchAll() {
    refetchRecords();
    refetchChips();
    onMutated?.();
  }

  const rangeProblem = exportMode === "range" ? exportRangeProblem(exportFrom, exportTo, todayISO()) : null;

  async function handleExport() {
    setExporting(true);
    try {
      const exportInput = {
        mode: exportMode, date, month: exportMonth, fromDate: exportFrom, toDate: exportTo, branch, department,
        employeeId: exportScope === "single" ? exportEmployee?.employee_id : undefined,
      };
      const url = `${API.attendance.export}${toQuery(attendanceExportParams(exportInput))}`;
      const response = await clientApi.get(url, { responseType: "blob" });
      const blobUrl = URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = blobUrl;
      const branchSlug = !unrestricted && effectiveBranch ? `${effectiveBranch.trim().replace(/\s+/g, "-")}_` : "";
      link.download = attendanceExportFilename(exportInput, branchSlug);
      link.click();
      URL.revokeObjectURL(blobUrl);
    } catch (err: unknown) {
      const message = (err as { message?: string })?.message ?? "Failed to export attendance data.";
      showToast(message, "error");
    } finally {
      setExporting(false);
    }
  }

  return (
    <>
      {/* Toolbar */}
      <div className="filter-bar" style={{ marginBottom: 14 }}>
        <button
          className="btn btn-ghost btn-sm"
          style={{ padding: "0 8px" }}
          onClick={() => { setDate(d => shiftDate(d, -1)); setPage(1); }}
        >
          <i className="ti ti-chevron-left" />
        </button>
        <input
          type="date"
          className="field-input"
          style={{ width: 160 }}
          value={date}
          max={todayISO()}
          onChange={e => { setDate(e.target.value); setPage(1); }}
        />
        <button
          className="btn btn-ghost btn-sm"
          style={{ padding: "0 8px" }}
          disabled={date >= todayISO()}
          onClick={() => { setDate(d => shiftDate(d, 1)); setPage(1); }}
        >
          <i className="ti ti-chevron-right" />
        </button>
        <BranchFilterSelect
          branches={branches}
          value={branchInput}
          onChange={value => { setBranchInput(value); setPage(1); }}
          locked={!unrestricted}
          lockedBranchName={effectiveBranch}
        />
        <select
          className="field-input"
          style={{ width: 180 }}
          value={department}
          onChange={e => { setDepartment(e.target.value); setPage(1); }}
        >
          <option value="">All Departments</option>
          {departments.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
        <div style={{ flex: 1 }} />
        {canExport && (
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--on-variant)" }}>
            Export:
            <select
              className="field-input"
              style={{ width: 160 }}
              aria-label="Export period"
              value={exportMode}
              onChange={e => setExportMode(e.target.value as AttendanceExportMode)}
            >
              <option value="day">Single Day</option>
              <option value="month">Month</option>
              <option value="range">Custom Date Range</option>
            </select>
          </label>
        )}
        {canExport && exportMode === "month" && (
          <input
            type="month"
            className="field-input"
            style={{ width: 150 }}
            aria-label="Export month"
            value={exportMonth}
            max={todayISO().slice(0, 7)}
            onChange={e => setExportMonth(e.target.value)}
          />
        )}
        {canExport && exportMode === "range" && (
          <>
            <input
              type="date"
              className="field-input"
              style={{ width: 150 }}
              aria-label="Export from date"
              title="From date"
              value={exportFrom}
              max={exportTo || todayISO()}
              onChange={e => setExportFrom(e.target.value)}
            />
            <input
              type="date"
              className="field-input"
              style={{ width: 150 }}
              aria-label="Export to date"
              title="To date"
              value={exportTo}
              min={exportFrom}
              max={todayISO()}
              onChange={e => setExportTo(e.target.value)}
            />
          </>
        )}
        {canExport && (
          <select
            className="field-input"
            style={{ width: 150 }}
            aria-label="Export employees"
            value={exportScope}
            onChange={e => setExportScope(e.target.value as AttendanceExportScope)}
          >
            <option value="all">All Employees</option>
            <option value="single">Single Employee</option>
          </select>
        )}
        {canExport && exportScope === "single" && (
          <div style={{ position: "relative", width: 230 }}>
            <input
              className="field-input"
              style={{ width: "100%", paddingLeft: 28 }}
              aria-label="Export employee"
              placeholder="Search employee by name or ID…"
              value={empQuery}
              onChange={e => { setEmpQuery(e.target.value); setExportEmployee(null); setEmpDropOpen(true); }}
              onFocus={() => setEmpDropOpen(true)}
              onBlur={() => setTimeout(() => setEmpDropOpen(false), 160)}
            />
            <i className="ti ti-search" style={{ position: "absolute", left: 9, top: "50%", transform: "translateY(-50%)", fontSize: 13, color: "var(--on-variant)", pointerEvents: "none" }} />
            {empDropOpen && !exportEmployee && empSearchUrl && (
              <div style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, minWidth: 260, background: "var(--bg)", border: "1px solid var(--outline-v)", borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,0.12)", zIndex: 50, overflow: "hidden" }}>
                {empLoading && <div style={{ padding: "9px 14px", fontSize: 12, color: "var(--on-variant)" }}>Searching…</div>}
                {!empLoading && empError && <div style={{ padding: "9px 14px", fontSize: 12, color: "var(--error)" }}>{empError}</div>}
                {!empLoading && !empError && empOptions.length === 0 && (
                  <div style={{ padding: "9px 14px", fontSize: 12, color: "var(--on-variant)" }}>No matching employees.</div>
                )}
                {!empLoading && empOptions.map(emp => (
                  <div
                    key={emp.id}
                    onMouseDown={() => { setExportEmployee(emp); setEmpQuery(`${emp.full_name} (${emp.employee_id})`); setEmpDropOpen(false); }}
                    style={{ padding: "9px 14px", cursor: "pointer", fontSize: 13, borderBottom: "1px solid var(--outline-v)" }}
                  >
                    <span style={{ fontWeight: 600 }}>{emp.full_name}</span>
                    <span style={{ marginLeft: 8, fontSize: 11, color: "var(--on-variant)" }}>{emp.employee_id}{emp.department ? ` · ${emp.department}` : ""}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {canExport && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={handleExport}
            disabled={
              exporting || (exportMode === "month" && !exportMonth) || !!rangeProblem
              || (exportScope === "single" && !exportEmployee)
            }
            title={rangeProblem ?? (exportScope === "single" && !exportEmployee ? "Select an employee to export." : undefined)}
          >
            <i className="ti ti-download" /> {exporting ? "Exporting…" : "Export CSV"}
          </button>
        )}
        {canExport && rangeProblem && (
          <span role="alert" style={{ fontSize: 11.5, color: "var(--error)" }}>{rangeProblem}</span>
        )}
        {canExport && !rangeProblem && exportScope === "single" && !exportEmployee && (
          <span role="alert" style={{ fontSize: 11.5, color: "var(--error)" }}>Select an employee from the list to export.</span>
        )}
        {canImport && (
          <button className="btn btn-filled btn-sm" onClick={() => setShowImport(true)}>
            <i className="ti ti-upload" /> Import Attendance
          </button>
        )}
      </div>

      {/* Summary chips */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 }}>
        {CHIP_CONFIG.map(item => (
          <div key={item.key} style={{ display: "flex", alignItems: "center", gap: 7, padding: "5px 12px", background: "#fff", border: "1px solid var(--outline-v)", borderRadius: 6, fontSize: 12 }}>
            <span style={{ width: 7, height: 7, borderRadius: "50%", background: item.color, flexShrink: 0, display: "inline-block" }} />
            <span style={{ fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{chips?.[item.key] ?? 0}</span>
            <span style={{ color: "var(--on-variant)", fontSize: 11 }}>{item.label}</span>
          </div>
        ))}
        <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "5px 12px", background: "#fff", border: "1px solid var(--outline-v)", borderRadius: 6, fontSize: 11, marginLeft: "auto", color: "var(--on-variant)" }}>
          Total: {records?.count ?? 0} employees
        </div>
      </div>

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      {/* Table */}
      <div className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th>Department</th>
                <th>Branch</th>
                <th>Clock In</th>
                <th>Clock Out</th>
                <th>Total Hrs</th>
                <th>OT</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={9} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>Loading…</td></tr>
              )}
              {!loading && rows.length === 0 && (
                <tr><td colSpan={9} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>No attendance records for this filter.</td></tr>
              )}
              {rows.map((r, idx) => (
                <tr key={`${r.record_id ?? r.employee_id ?? "row"}-${idx}`}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                      <div style={{ width: 30, height: 30, borderRadius: "50%", background: "rgba(30,78,140,0.1)", color: "var(--primary)", fontSize: 10, fontWeight: 700, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                        {r.initials}
                      </div>
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13, color: "var(--on-bg)" }}>{r.name}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.employee_id}</div>
                      </div>
                    </div>
                  </td>
                  <td>{r.department}</td>
                  <td>{r.branch}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: r.clock_in === "—" ? "var(--outline-v)" : r.is_late ? "var(--error)" : "var(--on-bg)" }}>
                    {r.clock_in}
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: r.clock_out === "—" ? "var(--outline-v)" : "var(--on-bg)" }}>
                    {r.clock_out}
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12 }}>{r.total_hours}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12, color: r.ot === "—" ? "var(--outline-v)" : "var(--success)" }}>{r.ot}</td>
                  <td><span className={STATUS_BADGE[r.status_key] ?? "badge badge-neutral"}>{r.status}</span></td>
                  <td>
                    <button
                      className="btn btn-ghost btn-sm"
                      style={{ padding: "3px 10px", fontSize: 11 }}
                      onClick={() => {
                        if (r.record_id) {
                          setViewingId(r.record_id);
                        } else {
                          showToast("No attendance record to view — employee was absent this day.", "info");
                        }
                      }}
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {records && records.total_pages > 1 && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Page {records.page} of {records.total_pages}</span>
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= records.total_pages} onClick={() => setPage(p => Math.min(p + 1, records.total_pages))}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          </div>
        )}
      </div>

      {showImport && (
        <ImportModal
          onClose={() => setShowImport(false)}
          onImported={result => {
            setShowImport(false);
            if (result.first_imported_date) {
              setDate(result.first_imported_date);
              setPage(1);
            }
            refetchAll();
            if (result.failed > 0) {
              showToast(`Import complete: ${result.successful} succeeded, ${result.failed} failed.`, "error");
            } else {
              showToast(`Import complete: ${result.successful} record(s) imported.`, "success");
            }
          }}
        />
      )}

      {viewingId && (
        <AttendanceDetailDrawer recordId={viewingId} date={date} onClose={() => setViewingId(null)} />
      )}
    </>
  );
}

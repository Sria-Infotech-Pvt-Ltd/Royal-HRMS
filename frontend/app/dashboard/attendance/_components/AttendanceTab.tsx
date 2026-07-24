"use client";

import { useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useDepartmentOptions } from "@/hooks/useDepartmentOptions";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import { useToast } from "@/components/ToastProvider";
import BranchFilterSelect from "@/components/BranchFilterSelect";
import type { DashboardData, PaginatedAttendance } from "@/types/attendance";
import ImportModal from "./ImportModal";
import AttendanceDetailDrawer from "./AttendanceDetailDrawer";

interface Props {
  onMutated?: () => void;
}

interface BranchOption { id: number; branch_name: string }

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

  async function handleExport() {
    setExporting(true);
    try {
      const url = `${API.attendance.export}${toQuery(filters)}`;
      const response = await clientApi.get(url, { responseType: "blob" });
      const blobUrl = URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = blobUrl;
      const branchSlug = !unrestricted && effectiveBranch ? `${effectiveBranch.trim().replace(/\s+/g, "-")}_` : "";
      link.download = `attendance_${branchSlug}${date}.csv`;
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
          <button className="btn btn-ghost btn-sm" onClick={handleExport} disabled={exporting}>
            <i className="ti ti-download" /> {exporting ? "Exporting…" : "Export CSV"}
          </button>
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

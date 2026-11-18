"use client";

import { useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { useDepartmentOptions } from "@/hooks/useDepartmentOptions";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";
import { useToast } from "@/components/ToastProvider";
import BranchFilterSelect from "@/components/BranchFilterSelect";
import type { AttendanceRow, DashboardData, PaginatedAttendance } from "@/types/attendance";
import ImportModal from "./ImportModal";
import AttendanceDetailDrawer from "./AttendanceDetailDrawer";
import AttendanceDatePicker from "./AttendanceDatePicker";
import AttendanceStatusTabs from "./AttendanceStatusTabs";
import AttendanceTable from "./AttendanceTable";
import type { SortState } from "./attendanceView";
import { localISODate } from "./monthView";

interface Props {
  onMutated?: () => void;
  /** Lifted up so the page's summary strip (Present/Absent/Late/On Leave) can jump straight to the matching rows in one click, and
      the status tabs below stay in sync with whatever triggered the filter. */
  status: string;
  onStatusChange: (status: string) => void;
}

interface BranchOption { id: number; branch_name: string }

const SEARCH_DELAY_MS = 350;

function toQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") search.append(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export default function AttendanceTab({ onMutated, status, onStatusChange }: Props) {
  const { showToast } = useToast();
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);
  const canExport       = usePermission("attendance.export");
  const canImport       = usePermission("attendance.create");

  const [today]                         = useState(() => localISODate());   // the viewer's own calendar day, not the UTC one
  const [date, setDate]                 = useState(today);
  const [branchInput, setBranchInput]   = useState("");
  const [department, setDepartment]     = useState("");
  const [searchText, setSearchText]     = useState("");
  const [sort, setSort]                 = useState<SortState>({ by: "name", dir: "asc" });
  const [page, setPage]                 = useState(1);
  const [showImport, setShowImport]     = useState(false);
  const [viewingId, setViewingId]       = useState<string | null>(null);
  const [exporting, setExporting]       = useState(false);

  // The server is asked only after typing pauses, so each keystroke is not a request.
  const search = useDebouncedValue(searchText.trim(), SEARCH_DELAY_MS);

  // hr_admin never gets to choose a branch — it's always their own, locked.
  const branch = unrestricted ? branchInput : effectiveBranch;

  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(
    unrestricted ? `${API.branches.list}?page_size=100` : null
  );
  const branches    = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);
  const departments = useDepartmentOptions(unrestricted, effectiveBranch);

  const filters = { date, branch, department, status, search };

  // Wait for the user to resolve before firing any request — otherwise an
  // hr_admin's very first fetch would briefly go out unscoped.
  const recordsUrl   = user ? `${API.attendance.records}${toQuery({ ...filters, sort_by: sort.by, sort_dir: sort.dir, page, page_size: 20 })}` : null;
  const dashboardUrl = user ? `${API.attendance.dashboard}${toQuery(filters)}` : null;

  const { data: records, loading, error, refetch: refetchRecords } = useFetch<PaginatedAttendance>(recordsUrl);
  const { data: dashboard, refetch: refetchChips } = useFetch<DashboardData>(dashboardUrl);

  const rows  = useMemo(() => records?.results ?? [], [records]);

  function refetchAll() {
    refetchRecords();
    refetchChips();
    onMutated?.();
  }

  function openRow(row: AttendanceRow) {
    if (row.record_id) setViewingId(row.record_id);
    else showToast("No attendance record to view — employee was absent this day.", "info");
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
        <AttendanceDatePicker date={date} todayISO={today} onChange={isoDate => { setDate(isoDate); setPage(1); }} />
        <BranchFilterSelect
          branches={branches}
          value={branchInput}
          onChange={value => { setBranchInput(value); setPage(1); }}
          locked={!unrestricted}
          lockedBranchName={effectiveBranch}
        />
        <select className="field-input field-select" style={{ width: 180 }} value={department} onChange={e => { setDepartment(e.target.value); setPage(1); }}>
          <option value="">All Org Units</option>
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

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

      <div className="card">
        <AttendanceStatusTabs
          status={status} onStatusChange={value => { onStatusChange(value); setPage(1); }} chips={dashboard?.summary_chips}
          search={searchText} onSearchChange={value => { setSearchText(value); setPage(1); }}
        />
        <AttendanceTable rows={rows} loading={loading} sort={sort} onSortChange={value => { setSort(value); setPage(1); }} onOpen={openRow} />

        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
            {records ? `Showing ${records.count} ${records.count === 1 ? "employee" : "employees"}` : ""}
            {records && records.total_pages > 1 ? ` · Page ${records.page} of ${records.total_pages}` : ""}
          </span>
          {records && records.total_pages > 1 && (
            <div style={{ display: "flex", gap: 6 }}>
              <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(p => Math.max(p - 1, 1))}>
                <i className="ti ti-chevron-left" /> Prev
              </button>
              <button className="btn btn-ghost btn-sm" disabled={page >= records.total_pages} onClick={() => setPage(p => Math.min(p + 1, records.total_pages))}>
                Next <i className="ti ti-chevron-right" />
              </button>
            </div>
          )}
        </div>
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

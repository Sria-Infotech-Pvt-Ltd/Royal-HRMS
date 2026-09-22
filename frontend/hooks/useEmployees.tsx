import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getStoredUser } from "@/lib/auth";
import {
  apiToEmployee, fullName,
  type ApiEmployee, type Employee, type EmployeeStatusFilter,
} from "@/app/dashboard/employees/_data";
import type { EmployeeStatCard } from "@/app/dashboard/employees/_components/EmployeeStatCards";

interface EmployeeStats {
  total: number; active: number; onboarding: number; departments: number;
  branch_names: string[]; department_names: string[];
  new_this_month: number; onboarding_or_probation: number;
  needs_reporting_manager: number; notice_period: number;
}

const EMPTY_STATS: EmployeeStats = {
  total: 0, active: 0, onboarding: 0, departments: 0,
  branch_names: [], department_names: [],
  new_this_month: 0, onboarding_or_probation: 0, needs_reporting_manager: 0, notice_period: 0,
};

/** Data-fetching + filter state for the Employee Directory list/stats — the
 * page component only composes UI around what this returns. */
export function useEmployees() {
  const [isAdmin, setIsAdmin] = useState(false);
  const [userBranch, setUserBranch] = useState("");

  const [employees, setEmployees] = useState<Employee[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState("");
  const [search, setSearch] = useState("");
  const [branch, setBranch] = useState("all");
  const [dept, setDept] = useState("all");
  const [status, setStatus] = useState<"all" | EmployeeStatusFilter>("all");
  const [exporting, setExporting] = useState(false);
  const [toggling, setToggling] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [empStats, setEmpStats] = useState<EmployeeStats>(EMPTY_STATS);

  const searchRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchEmployees = useCallback(async (
    q = "", p = 1,
    overrides?: { branch?: string; dept?: string; status?: "all" | EmployeeStatusFilter },
  ) => {
    setLoading(true);
    setFetchError("");
    const effBranch = overrides?.branch ?? branch;
    const effDept   = overrides?.dept   ?? dept;
    const effStatus = overrides?.status ?? status;
    try {
      const params: Record<string, string | number> = { page: p };
      if (q)                  params.search     = q;
      if (effBranch !== "all") params.branch     = effBranch;
      if (effDept   !== "all") params.department = effDept;
      if (effStatus !== "all") params.status     = effStatus;
      const { data } = await clientApi.get<{
        data: { results: ApiEmployee[]; count: number; page: number; total_pages: number };
      }>(API.employees.list, { params });
      setEmployees((data.data?.results ?? []).map(apiToEmployee));
      setTotalPages(data.data?.total_pages ?? 1);
      setTotalCount(data.data?.count ?? 0);
      setPage(data.data?.page ?? p);
    } catch {
      setFetchError("Could not load employees. Please refresh.");
    } finally {
      setLoading(false);
    }
  }, [branch, dept, status]);

  // Runs on mount, and again whenever a filter changes (fetchEmployees'
  // identity changes with branch/dept/status) — always resets to page 1,
  // keeps the current search term.
  useEffect(() => { fetchEmployees(search, 1); }, [fetchEmployees]); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchStats = useCallback(async (br: string) => {
    try {
      const { data } = await clientApi.get<{ data: EmployeeStats }>(
        API.employees.stats, { params: br === "all" ? {} : { branch: br } },
      );
      if (data.data) setEmpStats(data.data);
    } catch {
      // keep previous stats on failure rather than zeroing the cards out
    }
  }, []);

  useEffect(() => { fetchStats(branch); }, [branch, fetchStats]);

  useEffect(() => {
    const user = getStoredUser();
    setIsAdmin(user?.is_superuser === true);
    setUserBranch(user?.branch ?? "");
  }, []);

  function handleSearch(val: string) {
    setSearch(val);
    if (searchRef.current) clearTimeout(searchRef.current);
    searchRef.current = setTimeout(() => fetchEmployees(val, 1), 350);
  }

  function handlePageChange(newPage: number) {
    fetchEmployees(search, newPage);
  }

  function handleBranchChange(v: string) {
    setBranch(v);
    setDept("all");
  }

  function clearFilters() {
    setSearch(""); setBranch("all"); setDept("all"); setStatus("all");
    fetchEmployees("", 1);
  }

  function applyFilters(result: { status: "all" | EmployeeStatusFilter | null; branch: string | null; dept: string | null; search: string }) {
    const nextStatus = result.status ?? "all";
    const nextBranch = result.branch ?? "all";
    const nextDept = result.dept ?? "all";
    setStatus(nextStatus);
    setBranch(nextBranch);
    setDept(nextDept);
    setSearch(result.search);
    fetchEmployees(result.search, 1, { branch: nextBranch, dept: nextDept, status: nextStatus });
  }

  // Downloads the full currently-filtered set (not just the loaded page) as
  // CSV — a second request with a large page_size, same params fetchEmployees
  // already builds, so "Export" always reflects the active filters.
  async function handleExport() {
    setExporting(true);
    try {
      const params: Record<string, string | number> = { page: 1, page_size: 1000 };
      if (search)          params.search     = search;
      if (branch !== "all") params.branch     = branch;
      if (dept   !== "all") params.department = dept;
      if (status !== "all") params.status     = status;
      const { data } = await clientApi.get<{ data: { results: ApiEmployee[] } }>(API.employees.list, { params });
      const rows = data.data?.results ?? [];
      const headers = ["Employee ID", "Name", "Email", "Phone", "Department", "Designation", "Branch", "Role", "Date of Joining", "Status"];
      const csvRows = rows.map(r => [
        r.employee_id, r.full_name, r.email, r.phone, r.department, r.designation, r.branch, r.role_display, r.date_of_joining, r.status,
      ]);
      const escape = (v: unknown) => `"${String(v ?? "").replace(/"/g, '""')}"`;
      const csv = [headers, ...csvRows].map(row => row.map(escape).join(",")).join("\r\n");
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `employee-directory-${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // no error UI for a best-effort export — the filters/table are unaffected either way
    } finally {
      setExporting(false);
    }
  }

  async function toggleStatus(employee: Employee) {
    const isCurrentlyActive = employee.status !== "inactive";
    const label = isCurrentlyActive ? "deactivate" : "activate";
    if (!window.confirm(`Are you sure you want to ${label} ${fullName(employee)}?`)) return;
    setToggling(employee.id);
    try {
      await clientApi.patch(API.employees.detail(employee.id), { is_active: !isCurrentlyActive });
      setEmployees(prev => prev.map(e =>
        e.id === employee.id ? { ...e, status: isCurrentlyActive ? "inactive" : "active" } : e,
      ));
    } catch {
      // silently ignore — employee list state unchanged
    } finally {
      setToggling(null);
    }
  }

  const branchOptions = empStats.branch_names;
  const deptOptions = empStats.department_names;
  const activePct = empStats.total ? Math.round((empStats.active / empStats.total) * 100) : 0;

  const stats: EmployeeStatCard[] = useMemo(() => [
    {
      label: "TOTAL HEADCOUNT", value: empStats.total, icon: "ti-users", tint: "primary" as const,
      sub: <>across {empStats.departments} org units · <b>+{empStats.new_this_month}</b> this month</>,
      onClick: () => setStatus("all"),
    },
    {
      label: "ACTIVE", value: empStats.active, icon: "ti-user-check", tint: "success" as const,
      sub: `${activePct}% of headcount`,
      onClick: () => setStatus("active"),
    },
    {
      label: "ONBOARDING / PROBATION", value: empStats.onboarding_or_probation, icon: "ti-clock", tint: "warn" as const,
      sub: empStats.needs_reporting_manager > 0
        ? <><b>{empStats.needs_reporting_manager}</b> need a reporting manager</>
        : "all assigned a reporting manager",
      subTone: empStats.needs_reporting_manager > 0 ? "warn" as const : undefined,
      // The card combines two distinct filter values into one count — jumps
      // to "onboarding" (the more common of the two) rather than nothing.
      onClick: () => setStatus("onboarding"),
    },
    {
      label: "NOTICE PERIOD", value: empStats.notice_period, icon: "ti-alert-triangle", tint: "error" as const,
      sub: "exit clearance opens automatically",
      subTone: "crit" as const,
      onClick: () => setStatus("notice_period"),
    },
  ], [empStats, activePct]);

  return {
    isAdmin, userBranch,
    employees, loading, fetchError, total: empStats.total,
    search, setSearch: handleSearch,
    branch, setBranch: handleBranchChange,
    dept, setDept,
    status, setStatus,
    page, totalPages, totalCount,
    branchOptions, deptOptions, stats,
    exporting, toggling,
    fetchEmployees, handlePageChange, handleExport, toggleStatus, clearFilters, applyFilters,
  };
}

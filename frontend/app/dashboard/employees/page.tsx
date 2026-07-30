"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getStoredUser } from "@/lib/auth";
import { usePermission } from "@/hooks/usePermission";
import {
  fullName,
  initials,
  formatDate,
  deptTint,
  avatarColor,
  type Employee,
  type EmployeeStatus,
} from "./_data";
import Avatar from "./_components/Avatar";
import StatusBadge from "./_components/StatusBadge";
import AddEmployeeModal  from "./_components/AddEmployeeModal";
import BulkImportModal  from "./_components/BulkImportModal";
import EditEmployeeModal from "./_components/EditEmployeeModal";

/* ── API response shape ─────────────────────────────────────── */
export interface ApiEmployee {
  id: string; employee_id: string;
  first_name: string; last_name: string; full_name: string;
  email: string; phone: string;
  department: string; designation: string; branch: string;
  role: string; role_display: string;
  date_of_joining: string; is_active: boolean; status: string;
}

function apiToEmployee(u: ApiEmployee): Employee {
  return {
    id:            u.employee_id || u.id,
    uuid:          u.id,
    code:          u.employee_id || u.id,
    firstName:     u.first_name,
    middleName:    "",
    lastName:      u.last_name,
    email:         u.email,
    phone:         u.phone,
    department:    u.department,
    designation:   u.designation,
    dateOfJoining: u.date_of_joining,
    dateOfBirth:   "",
    location:      u.branch,
    gender:        "male",
    status:        (u.status as EmployeeStatus) || (u.is_active ? "active" : "inactive"),
    details: {
      code:          u.employee_id,
      firstName:     u.first_name,
      middleName:    "",
      lastName:      u.last_name,
      gender:        "",
      dateOfBirth:   "",
      dateOfJoining: u.date_of_joining,
      department:    u.department,
      designation:   u.designation,
      branch:        u.branch,
      category:      "General",
      esiLocation:   "Corporate",
      metroTds:      "Metro",
      esiDispensary: "N/A",
      nationality:   "Indian",
      country:       "India",
      loginEmail:    u.email,
      personalEmail: u.email,
      ssRole:        u.role_display || "Employee",
      portalAccess:  "enabled",
      mobileNumber:  u.phone,
    },
    tables: {},
  };
}

const STATUS_FILTERS: { value: "all" | EmployeeStatus; label: string }[] = [
  { value: "all",        label: "All Status"  },
  { value: "active",     label: "Active"      },
  { value: "onboarding", label: "Onboarding"  },
  { value: "inactive",   label: "Inactive"    },
];

const SEL_CLS =
  "px-3.5 py-2.5 pr-9 rounded-lg border border-[var(--outline-v)] bg-white text-[13px] font-medium text-[var(--on-bg)] focus:border-[var(--primary)] focus:ring-2 focus:ring-[rgba(30,78,140,0.12)] transition-colors appearance-none bg-no-repeat cursor-pointer";

const SEL_STYLE = {
  backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%237c8aa3' stroke-width='2'><path d='M4 6l4 4 4-4'/></svg>\")",
  backgroundPosition: "right 10px center",
};

export default function EmployeesPage() {
  const router = useRouter();

  const canCreate = usePermission("employees.create");
  const canEdit   = usePermission("employees.edit");

  const [isAdmin,    setIsAdmin]    = useState(false);
  const [userBranch, setUserBranch] = useState("");

  const [employees,   setEmployees]   = useState<Employee[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [fetchError,  setFetchError]  = useState("");
  const [search,      setSearch]      = useState("");
  const [branch,      setBranch]      = useState("all");
  const [dept,        setDept]        = useState("all");
  const [status,      setStatus]      = useState<"all" | EmployeeStatus>("all");
  const [showModal,   setShowModal]   = useState(false);
  const [showImport,  setShowImport]  = useState(false);
  const [editing,     setEditing]     = useState<Employee | null>(null);
  const [toggling,    setToggling]    = useState<string | null>(null);
  const [page,        setPage]        = useState(1);
  const [totalPages,  setTotalPages]  = useState(1);
  const [totalCount,  setTotalCount]  = useState(0);

  const searchRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchEmployees = useCallback(async (q = "", p = 1) => {
    setLoading(true);
    setFetchError("");
    try {
      const params: Record<string, string | number> = { page: p };
      if (q) params.search = q;
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
  }, []);

  useEffect(() => { fetchEmployees(); }, [fetchEmployees]);

  function handleSearch(val: string) {
    setSearch(val);
    if (searchRef.current) clearTimeout(searchRef.current);
    searchRef.current = setTimeout(() => fetchEmployees(val, 1), 350);
  }

  function handlePageChange(newPage: number) {
    fetchEmployees(search, newPage);
  }

  useEffect(() => {
    const user = getStoredUser();
    setIsAdmin(user?.is_superuser === true);
    setUserBranch(user?.branch ?? "");
  }, []);

  /* derive unique branches + departments from loaded data */
  const branchOptions = useMemo(
    () => [...new Set(employees.map(e => e.location).filter(Boolean))].sort(),
    [employees],
  );
  const deptOptions = useMemo(
    () => [...new Set(employees.map(e => e.department).filter(Boolean))].sort(),
    [employees],
  );

  const filtered = useMemo(() => {
    return employees.filter(e => {
      const matchesBranch = branch === "all" || e.location === branch;
      const matchesDept   = dept   === "all" || e.department === dept;
      const matchesStatus = status === "all" || e.status === status;
      return matchesBranch && matchesDept && matchesStatus;
    });
  }, [employees, branch, dept, status]);

  const stats = useMemo(() => {
    const source     = branch === "all" ? employees : employees.filter(e => e.location === branch);
    const active     = source.filter(e => e.status === "active").length;
    const onboarding = source.filter(e => e.status === "onboarding").length;
    const depts      = new Set(source.map(e => e.department)).size;
    return [
      { label: "Total Employees", value: totalCount,    icon: "ti-users",      tint: "primary" as const },
      { label: "Active",          value: active,        icon: "ti-user-check", tint: "success" as const },
      { label: "Onboarding",      value: onboarding,    icon: "ti-user-plus",  tint: "warn"    as const },
      { label: "Departments",     value: depts,         icon: "ti-building",   tint: "info"    as const },
    ];
  }, [employees, branch, totalCount]);

  function open(id: string) {
    router.push(`/dashboard/employees/${id}`);
  }

  async function toggleStatus(employee: Employee) {
    const isCurrentlyActive = employee.status !== "inactive";
    const label = isCurrentlyActive ? "deactivate" : "activate";
    if (!window.confirm(`Are you sure you want to ${label} ${fullName(employee)}?`)) return;
    setToggling(employee.id);
    try {
      await clientApi.patch(API.employees.detail(employee.id), { is_active: !isCurrentlyActive });
      setEmployees(prev => prev.map(e =>
        e.id === employee.id
          ? { ...e, status: isCurrentlyActive ? "inactive" : "active" }
          : e,
      ));
    } catch {
      // silently ignore — employee list state unchanged
    } finally {
      setToggling(null);
    }
  }

  return (
    <div>
      {/* ── Header ── */}
      <div className="page-header">
        <div>
          <div className="page-title">Employees</div>
          <div className="page-sub">
            {isAdmin
              ? "All employees across all branches"
              : userBranch
                ? `${userBranch} — your branch`
                : "All active and onboarding employees"
            }
          </div>
        </div>
        <div className="page-actions" style={{ gap: 10 }}>
          <div className="search-bar">
            <i className="ti ti-search" />
            <input
              placeholder="Search employees…"
              value={search}
              onChange={e => handleSearch(e.target.value)}
              suppressHydrationWarning
            />
          </div>
          {canCreate && (
            <>
              <button onClick={() => setShowImport(true)} suppressHydrationWarning
                className="btn btn-ghost" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <i className="ti ti-file-upload" style={{ fontSize: 15 }} />
                Bulk Import
              </button>
              <button onClick={() => setShowModal(true)} suppressHydrationWarning
                className="btn btn-filled" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <i className="ti ti-plus" style={{ fontSize: 15 }} />
                Add Employee
              </button>
            </>
          )}
        </div>
      </div>

      {/* ── Stats ── */}
      <div className="stats-grid mb-6">
        {stats.map(st => (
          <div key={st.label} className="stat-card">
            <div>
              <div className="stat-label">{st.label}</div>
              <div className="stat-value">{st.value}</div>
            </div>
            <div className={`stat-icon ${
              st.tint === "primary" ? "si-primary" :
              st.tint === "success" ? "si-success" :
              st.tint === "warn"    ? "si-warn"    :
              "si-info"
            }`}>
              <i className={`ti ${st.icon}`} />
            </div>
          </div>
        ))}
      </div>

      {/* ── Filters ── */}
      <div className="flex items-center gap-3 flex-wrap mb-4">
        {/* Branch */}
        <select
          value={branch}
          onChange={e => { setBranch(e.target.value); setDept("all"); }}
          suppressHydrationWarning
          className={SEL_CLS}
          style={SEL_STYLE}
        >
          <option value="all">All Branches</option>
          {branchOptions.map(b => <option key={b} value={b}>{b}</option>)}
        </select>

        {/* Department */}
        <select
          value={dept}
          onChange={e => setDept(e.target.value)}
          suppressHydrationWarning
          className={SEL_CLS}
          style={SEL_STYLE}
        >
          <option value="all">All Departments</option>
          {deptOptions.map(d => <option key={d} value={d}>{d}</option>)}
        </select>

        {/* Status */}
        <select
          value={status}
          onChange={e => setStatus(e.target.value as "all" | EmployeeStatus)}
          suppressHydrationWarning
          className={SEL_CLS}
          style={SEL_STYLE}
        >
          {STATUS_FILTERS.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </div>

      {/* ── Table ── */}
      <div className="bg-white rounded-xl border border-[var(--outline-v)] overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16 gap-2 text-[13px] text-[var(--on-variant)]">
            <i className="ti ti-loader-2 animate-spin text-[20px]" style={{ color: "var(--primary)" }} />
            Loading employees…
          </div>
        ) : fetchError ? (
          <div className="py-14 text-center">
            <i className="ti ti-alert-circle text-3xl block mb-2" style={{ color: "var(--error)" }} />
            <p className="text-[13px] text-[var(--on-variant)]">{fetchError}</p>
            <button onClick={() => fetchEmployees()} suppressHydrationWarning
              className="mt-3 text-[13px] font-medium px-4 py-2 rounded-lg border border-[var(--outline-v)] text-[var(--primary)] hover:bg-[var(--bg-low)] transition-colors">
              Retry
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse min-w-[900px]">
              <thead>
                <tr className="bg-[var(--bg-low)] border-b border-[var(--outline-v)]">
                  {["Employee", "Branch", "Department", "Role", "Date of Joining", "Status", "Actions"].map(h => (
                    <th key={h}
                      className="text-left text-[11px] font-semibold uppercase tracking-wide text-[var(--on-variant)] px-5 py-3 whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-5 py-14 text-center">
                      <i className="ti ti-users-group text-4xl text-[var(--outline)] block mb-3" />
                      <p className="text-[13px] text-[var(--on-variant)]">No employees match your filters.</p>
                    </td>
                  </tr>
                ) : (
                  filtered.map(e => (
                    <tr key={e.id} onClick={() => open(e.id)}
                      className="border-b border-[var(--outline-v)] last:border-0 hover:bg-[var(--bg-low)] transition-colors cursor-pointer">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <Avatar text={initials(e.firstName, e.lastName)} size={38} color={avatarColor(e.department)} />
                          <div className="min-w-0">
                            <div className="text-[14px] font-semibold text-[var(--on-bg)] leading-tight truncate">{fullName(e)}</div>
                            <div className="text-[12px] text-[var(--on-variant)] truncate">{e.email}</div>
                            <div className="text-[11px] text-[var(--outline)] truncate">{e.code}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-[13px] text-[var(--on-bg)] whitespace-nowrap">
                        {e.location
                          ? <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                              <i className="ti ti-building" style={{ fontSize: 12, color: "var(--outline)" }} />
                              {e.location}
                            </span>
                          : <span className="text-[var(--outline)]">—</span>
                        }
                      </td>
                      <td className="px-5 py-3.5 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[12px] font-medium ${deptTint(e.department).bg} ${deptTint(e.department).text}`}>
                          {e.department || "—"}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-[13px] text-[var(--on-bg)] whitespace-nowrap">{e.details.ssRole || "—"}</td>
                      <td className="px-5 py-3.5 text-[13px] text-[var(--on-variant)] whitespace-nowrap">{formatDate(e.dateOfJoining)}</td>
                      <td className="px-5 py-3.5"><StatusBadge status={e.status} /></td>
                      <td className="px-5 py-3.5" onClick={ev => ev.stopPropagation()}>
                        <div className="flex items-center gap-1">
                          <button onClick={() => open(e.id)} suppressHydrationWarning title="View"
                            className="flex items-center justify-center w-8 h-8 rounded-lg border border-[var(--outline-v)] text-[var(--on-bg)] bg-white hover:border-[var(--primary)] hover:text-[var(--primary)] transition-colors">
                            <i className="ti ti-eye text-[15px]" />
                          </button>
                          {canEdit && (
                            <button onClick={() => setEditing(e)} suppressHydrationWarning title="Edit"
                              className="flex items-center justify-center w-8 h-8 rounded-lg border border-[var(--outline-v)] text-[var(--on-bg)] bg-white hover:border-[var(--primary)] hover:text-[var(--primary)] transition-colors">
                              <i className="ti ti-edit text-[15px]" />
                            </button>
                          )}
                          {canEdit && (
                            <button
                              onClick={() => toggleStatus(e)}
                              disabled={toggling === e.id}
                              suppressHydrationWarning
                              title={e.status === "inactive" ? "Activate" : "Deactivate"}
                              className={[
                                "flex items-center justify-center w-8 h-8 rounded-lg border transition-colors",
                                e.status === "inactive"
                                  ? "border-[var(--success)] text-[var(--success)] bg-white hover:bg-[var(--success-c)]"
                                  : "border-[var(--error)] text-[var(--error)] bg-white hover:bg-[var(--error-c)]",
                                toggling === e.id ? "opacity-50 cursor-not-allowed" : "",
                              ].join(" ")}
                            >
                              {toggling === e.id
                                ? <i className="ti ti-loader-2 animate-spin text-[15px]" />
                                : e.status === "inactive"
                                  ? <i className="ti ti-user-check text-[15px]" />
                                  : <i className="ti ti-user-off text-[15px]" />
                              }
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Pagination ── */}
      {totalPages > 1 && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: 16, flexWrap: "wrap", gap: 8 }}>
          <span style={{ fontSize: 13, color: "var(--on-variant)" }}>
            Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, totalCount)} of {totalCount} employees
          </span>
          <div style={{ display: "flex", gap: 4 }}>
            <button
              className="btn btn-ghost btn-sm"
              disabled={page <= 1}
              onClick={() => handlePageChange(page - 1)}
              suppressHydrationWarning
            >
              <i className="ti ti-chevron-left" /> Prev
            </button>
            {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
              <button
                key={p}
                className={`btn btn-sm ${p === page ? "btn-filled" : "btn-ghost"}`}
                onClick={() => handlePageChange(p)}
                suppressHydrationWarning
              >
                {p}
              </button>
            ))}
            <button
              className="btn btn-ghost btn-sm"
              disabled={page >= totalPages}
              onClick={() => handlePageChange(page + 1)}
              suppressHydrationWarning
            >
              Next <i className="ti ti-chevron-right" />
            </button>
          </div>
        </div>
      )}

      {/* ── Add Employee Modal ── */}
      {showModal && (
        <AddEmployeeModal
          onClose={() => setShowModal(false)}
          onCreated={() => {
            setShowModal(false);
            fetchEmployees(search, 1);
          }}
        />
      )}

      {/* ── Bulk Import Modal ── */}
      {showImport && (
        <BulkImportModal
          onClose={() => setShowImport(false)}
          onSuccess={() => fetchEmployees(search, 1)}
        />
      )}

      {/* ── Edit Employee Modal ── */}
      {editing && (
        <EditEmployeeModal
          employee={editing}
          branchOptions={branchOptions}
          deptOptions={deptOptions}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            fetchEmployees(search, page);
          }}
        />
      )}
    </div>
  );
}

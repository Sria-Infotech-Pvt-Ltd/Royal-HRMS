"use client";

import BranchFilterSelect from "@/components/BranchFilterSelect";
import type { EmployeeStatusFilter } from "../_data";

interface StatusFilterOption { value: "all" | EmployeeStatusFilter; label: string }

interface Props {
  search: string;
  onSearchChange: (value: string) => void;
  branch: string;
  branchOptions: string[];
  onBranchChange: (value: string) => void;
  isAdmin: boolean;
  userBranch: string;
  dept: string;
  deptOptions: string[];
  onDeptChange: (value: string) => void;
  status: "all" | EmployeeStatusFilter;
  statusFilters: StatusFilterOption[];
  onStatusChange: (value: "all" | EmployeeStatusFilter) => void;
  hasActiveFilters: boolean;
  onClearFilters: () => void;
  canImport: boolean;
  onBulkImport: () => void;
}

export default function EmployeeToolbar({
  search, onSearchChange, branch, branchOptions, onBranchChange, isAdmin, userBranch,
  dept, deptOptions, onDeptChange, status, statusFilters, onStatusChange,
  hasActiveFilters, onClearFilters, canImport, onBulkImport,
}: Props) {
  return (
    <div className="flex items-center gap-3 flex-wrap mb-4">
      <div className="search-bar">
        <i className="ti ti-search" />
        <input
          placeholder="Search by name, ID or email"
          value={search}
          onChange={e => onSearchChange(e.target.value)}
          suppressHydrationWarning
        />
      </div>

      {/* Branch — locked to the user's own branch for anyone but system_admin;
          the backend already enforces this, this just keeps the UI honest about it. */}
      <BranchFilterSelect
        branches={branchOptions.map((b, i) => ({ id: i, branch_name: b }))}
        value={branch === "all" ? "" : branch}
        onChange={v => onBranchChange(v || "all")}
        locked={!isAdmin}
        lockedBranchName={userBranch}
        width={180}
      />

      {/* Department — system_admin only; managers and employees are
          already scoped to their own team/branch so this filter doesn't apply. */}
      {isAdmin && (
        <select
          value={dept}
          onChange={e => onDeptChange(e.target.value)}
          suppressHydrationWarning
          className="field-input field-select"
          style={{ width: "auto" }}
        >
          <option value="all">All Org Units</option>
          {deptOptions.map(d => <option key={d} value={d}>{d}</option>)}
        </select>
      )}

      <select
        value={status}
        onChange={e => onStatusChange(e.target.value as "all" | EmployeeStatusFilter)}
        suppressHydrationWarning
        className="field-input field-select"
        style={{ width: "auto" }}
      >
        {statusFilters.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
      </select>

      {hasActiveFilters && (
        <button
          onClick={onClearFilters}
          style={{ background: "none", border: "none", color: "var(--on-variant)", fontSize: 12.5, fontWeight: 600, cursor: "pointer" }}
          suppressHydrationWarning
        >
          Clear filters
        </button>
      )}

      {canImport && (
        <button
          onClick={onBulkImport}
          className="btn btn-ghost btn-sm" style={{ display: "flex", alignItems: "center", gap: 6, marginLeft: "auto" }}
          title="Bulk import employees from a spreadsheet"
          suppressHydrationWarning
        >
          <i className="ti ti-file-upload" style={{ fontSize: 14 }} /> Bulk Import
        </button>
      )}
    </div>
  );
}

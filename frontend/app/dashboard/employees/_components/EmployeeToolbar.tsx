"use client";

// The directory's filter bar, laid out as the reference's `.toolbar`: search, Department, Location, Status,
// then "Clear filters" (and Bulk Import for those who can hire) on the right. Every control filters the
// server-side list; scope is enforced by the API regardless of what is shown here.

import BranchFilterSelect from "@/components/BranchFilterSelect";
import type { EmployeeStatusFilter } from "../_data";

interface StatusFilterOption { value: "all" | EmployeeStatusFilter; label: string }

interface Props {
  search: string;
  onSearchChange: (value: string) => void;
  onSearchSubmit: () => void;
  searching: boolean;
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
  search, onSearchChange, onSearchSubmit, searching, branch, branchOptions, onBranchChange, isAdmin, userBranch,
  dept, deptOptions, onDeptChange, status, statusFilters, onStatusChange,
  hasActiveFilters, onClearFilters, canImport, onBulkImport,
}: Props) {
  return (
    <div className="toolbar">
      <div className="search">
        {searching ? (
          <i className="ti ti-loader-2 animate-spin" aria-hidden="true" style={{ fontSize: 16 }} />
        ) : (
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
            <circle cx="11" cy="11" r="7" /><path d="m21 21-4.3-4.3" />
          </svg>
        )}
        <input
          placeholder="Search by name, ID or email"
          aria-label="Search employees by name, ID or email. Results update as you type; press Enter to search now."
          value={search}
          onChange={event => onSearchChange(event.target.value)}
          onKeyDown={event => {
            if (event.key === "Enter") {
              event.preventDefault();
              onSearchSubmit();
            }
          }}
          suppressHydrationWarning
        />
        {searching && <span className="sr-only" role="status" aria-live="polite">Searching employees</span>}
      </div>

      <select className="sel" value={dept} onChange={event => onDeptChange(event.target.value)} aria-label="Department" suppressHydrationWarning>
        <option value="all">All Departments</option>
        {deptOptions.map(name => <option key={name} value={name}>{name}</option>)}
      </select>

      {/* Location — locked to the user's own branch for anyone but system_admin; the backend already
          enforces this, this just keeps the UI honest about it. */}
      <BranchFilterSelect
        branches={branchOptions.map((name, index) => ({ id: index, branch_name: name }))}
        value={branch === "all" ? "" : branch}
        onChange={value => onBranchChange(value || "all")}
        locked={!isAdmin}
        lockedBranchName={userBranch}
        variant="reference"
      />

      <select
        className="sel" value={status} aria-label="Status" suppressHydrationWarning
        onChange={event => onStatusChange(event.target.value as "all" | EmployeeStatusFilter)}
      >
        {statusFilters.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
      </select>

      <span className="spacer" />

      {hasActiveFilters && (
        <button className="rvbtn ghost" type="button" onClick={onClearFilters} suppressHydrationWarning>Clear filters</button>
      )}
      {canImport && (
        <button className="rvbtn" type="button" onClick={onBulkImport} title="Bulk import employees from a spreadsheet" suppressHydrationWarning>
          <i className="ti ti-file-upload" style={{ fontSize: 14 }} /> Bulk Import
        </button>
      )}
    </div>
  );
}

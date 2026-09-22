"use client";

import type { Employee } from "../_data";
import EmployeeTableRow from "./EmployeeTableRow";

const COLUMNS = ["Employee", "Position", "Department", "Location", "Status", "Joined", "Reporting Manager", "Action"];

interface Props {
  employees: Employee[];
  loading: boolean;
  fetchError: string;
  canEditOnboarding: boolean;
  canEdit: boolean;
  togglingId: string | null;
  onOpen: (id: string) => void;
  onToggleStatus: (employee: Employee) => void;
  onRetry: () => void;
  /** Refetches the directory after a "Perform an action" apply. */
  onActionApplied: () => void;
}

export default function EmployeeTable({
  employees, loading, fetchError, canEditOnboarding, canEdit, togglingId, onOpen, onToggleStatus, onRetry, onActionApplied,
}: Props) {
  return (
    <div className="tbl-wrap">
      {loading ? (
        <div className="flex items-center justify-center py-16 gap-2 text-[13px]" style={{ color: "var(--muted)" }}>
          <i className="ti ti-loader-2 animate-spin text-[20px]" style={{ color: "var(--brand)" }} />
          Loading employees…
        </div>
      ) : fetchError ? (
        <div className="py-14 text-center">
          <i className="ti ti-alert-circle text-3xl block mb-2" style={{ color: "var(--crit)" }} />
          <p className="text-[13px]" style={{ color: "var(--muted)" }}>{fetchError}</p>
          <button onClick={onRetry} suppressHydrationWarning
            className="mt-3 text-[13px] font-medium px-4 py-2 rounded-lg border border-[var(--line)]" style={{ color: "var(--brand)" }}>
            Retry
          </button>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <div style={{ minWidth: 980 }}>
            <div className="tbl-h grid-cols-emp">
              {COLUMNS.map(h => <div key={h}>{h}</div>)}
            </div>
            {employees.length === 0 ? (
              <div className="px-5 py-14 text-center">
                <i className="ti ti-users-group text-4xl block mb-3" style={{ color: "var(--faint)" }} />
                <p className="text-[13px]" style={{ color: "var(--muted)" }}>No employees match your filters.</p>
              </div>
            ) : (
              <div className="rows">
                {employees.map(e => (
                  <EmployeeTableRow
                    key={e.id}
                    employee={e}
                    canEditOnboarding={canEditOnboarding}
                    canEdit={canEdit}
                    toggling={togglingId === e.id}
                    onOpen={onOpen}
                    onToggleStatus={onToggleStatus}
                    onActionApplied={onActionApplied}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

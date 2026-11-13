"use client";

// "My projects" on the employee's Home tab — the projects they're currently assigned to in Project Budgeting
// (read-only here). Same data as the Employment tab's Work Status section (useWorkStatus), just the current ones.
// Always shown (loading, error and empty included) so an employee can tell "nothing assigned" apart from "not working";
// it disappears only when the account has no employee ID at all (404) or may not see Work Status (403).

import { useWorkStatus } from "@/hooks/useWorkStatus";
import { STATUS_BADGE, endLabel, fmtDate, statusLabel } from "@/components/work-status/workStatusFormat";

const MAX_PROJECTS_SHOWN = 5;

interface Props {
  onViewAll: () => void;
}

export default function HomeProjectsPanel({ onViewAll }: Props) {
  const { data, loading, error, status } = useWorkStatus();
  const current = data?.current ?? [];

  if (status === 403 || status === 404) return null;

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <div className="card-title" style={{ fontSize: 20 }}><i className="ti ti-briefcase" /> Work status</div>
          <p style={{ margin: "4px 0 0", fontSize: 11, color: "var(--on-variant)" }}>
            Projects assigned to you in Project Budgeting.
          </p>
        </div>
        <button onClick={onViewAll} className="btn btn-ghost btn-sm">
          Work status &amp; history <i className="ti ti-arrow-right" />
        </button>
      </div>

      {loading && !data ? (
        <div style={{ padding: "16px 20px", fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : error || !data ? (
        <div style={{ padding: "16px 20px", fontSize: 13, color: "var(--on-variant)" }}>
          Could not load your project assignments right now.
        </div>
      ) : current.length === 0 ? (
        <div style={{ padding: "16px 20px", fontSize: 13, color: "var(--on-variant)" }}>
          No project is assigned to you in Project Budgeting right now.
        </div>
      ) : (
      <div>
        {current.slice(0, MAX_PROJECTS_SHOWN).map(assignment => (
          <div
            key={assignment.assignment_id}
            onClick={onViewAll}
            style={{ display: "flex", alignItems: "center", gap: 12, padding: "16px 20px", borderBottom: "1px solid var(--outline-v)", cursor: "pointer" }}
          >
            <i className="ti ti-briefcase" style={{ fontSize: 16, color: "var(--primary)", flexShrink: 0 }} />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{assignment.project_name}</div>
              <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                {assignment.milestone_name || "Whole project"}
                {assignment.role && ` · ${assignment.role}`}
                {assignment.allocation_percent && ` · ${assignment.allocation_percent}% allocated`}
                {" · "}{fmtDate(assignment.start_date)} – {endLabel(assignment)}
              </div>
            </div>
            <span className={STATUS_BADGE[assignment.assignment_status] ?? "badge badge-neutral"} style={{ flexShrink: 0 }}>
              {statusLabel(assignment)}
            </span>
          </div>
        ))}
      </div>
      )}
    </div>
  );
}

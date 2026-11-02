"use client";

// "My projects" on the employee's Home tab — the projects they're currently assigned to in Project Budgeting
// (read-only here). Same data as the Employment tab's Work Status section (useWorkStatus), just the current ones.
// Renders nothing while loading and when there is no current assignment: most employees aren't on a project, and an
// empty card would only be noise on their Home page.

import { useWorkStatus } from "@/hooks/useWorkStatus";
import { STATUS_BADGE, endLabel, fmtDate, statusLabel } from "@/components/work-status/workStatusFormat";

const MAX_PROJECTS_SHOWN = 5;

interface Props {
  onViewAll: () => void;
}

export default function HomeProjectsPanel({ onViewAll }: Props) {
  const { data, loading } = useWorkStatus();
  const current = data?.current ?? [];

  if (loading || current.length === 0) return null;

  return (
    <div className="card" style={{ marginBottom: 20 }}>
      <div className="card-header" style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        <div>
          <div className="card-title" style={{ fontSize: 20 }}><i className="ti ti-briefcase" /> My projects</div>
          <p style={{ margin: "4px 0 0", fontSize: 11, color: "var(--on-variant)" }}>
            Assigned in Project Budgeting.
          </p>
        </div>
        <button onClick={onViewAll} className="btn btn-ghost btn-sm">
          Work status &amp; history <i className="ti ti-arrow-right" />
        </button>
      </div>

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
    </div>
  );
}

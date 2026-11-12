"use client";

import type { ReactNode } from "react";
import { STATUS_BADGE, STATUS_LABEL, type AssignmentRow, type Course } from "@/lib/training";

export function CourseTable({ courses, onOpen }: { courses: Course[]; onOpen: (id: string) => void }) {
  if (!courses.length) return null;
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "2px solid var(--outline-v)", textAlign: "left", color: "var(--on-variant)" }}>
            <th style={{ padding: 10 }}>Course</th>
            <th style={{ padding: 10 }}>Materials</th>
            <th style={{ padding: 10 }}>Assessment</th>
            <th style={{ padding: 10 }}>Assigned</th>
            <th style={{ padding: 10 }}>Completed</th>
            <th style={{ padding: 10 }}>Status</th>
          </tr>
        </thead>
        <tbody>
          {courses.map(c => (
            <tr key={c.id} style={{ borderBottom: "1px solid var(--outline-v)", cursor: "pointer" }} onClick={() => onOpen(c.id)}>
              <td style={{ padding: 10 }}>
                <div style={{ fontWeight: 600 }}>{c.title}</div>
                <div className="text-[11px] text-[var(--on-variant)]">
                  {[c.category, c.is_mandatory ? "Mandatory" : "Optional", c.auto_assign_new_joiners ? "New joiners" : ""]
                    .filter(Boolean).join(" · ")}
                </div>
              </td>
              <td style={{ padding: 10 }}>{c.material_count ?? 0}</td>
              <td style={{ padding: 10 }}>{c.assessment ? c.assessment.title : "—"}</td>
              <td style={{ padding: 10 }}>{c.assigned_count ?? 0}</td>
              <td style={{ padding: 10 }}>{c.completed_count ?? 0}</td>
              <td style={{ padding: 10 }}>
                <span className={`badge ${c.archived ? "badge-neutral" : c.is_active ? "badge-success" : "badge-warn"}`}>
                  {c.archived ? "Archived" : c.is_active ? "Active" : "Inactive"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ProgressTable({ rows, showCourse = false, actions }: {
  rows: AssignmentRow[]; showCourse?: boolean; actions?: (r: AssignmentRow) => ReactNode;
}) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "2px solid var(--outline-v)", textAlign: "left", color: "var(--on-variant)" }}>
            <th style={{ padding: 8 }}>Employee</th>
            {showCourse && <th style={{ padding: 8 }}>Course</th>}
            <th style={{ padding: 8 }}>Status</th>
            <th style={{ padding: 8 }}>Progress</th>
            <th style={{ padding: 8 }}>Due</th>
            <th style={{ padding: 8 }}>Completed</th>
            <th style={{ padding: 8 }}>Best score</th>
            {actions && <th style={{ padding: 8 }} />}
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.id} style={{ borderBottom: "1px solid var(--outline-v)" }}>
              <td style={{ padding: 8 }}>
                {r.employee.name}
                <div className="text-[11px] text-[var(--on-variant)]">
                  {[r.employee.employee_id, r.employee.department, r.employee.branch].filter(Boolean).join(" · ")}
                </div>
              </td>
              {showCourse && <td style={{ padding: 8 }}>{r.course_title}</td>}
              <td style={{ padding: 8 }}><span className={STATUS_BADGE[r.status]}>{STATUS_LABEL[r.status]}</span></td>
              <td style={{ padding: 8 }}>{r.progress_percent ?? 0}%</td>
              <td style={{ padding: 8 }}>{r.due_date ?? "—"}</td>
              <td style={{ padding: 8 }}>{r.completed_at ? r.completed_at.slice(0, 10) : "—"}</td>
              <td style={{ padding: 8 }}>{r.best_score_percent == null ? "—" : `${r.best_score_percent}%`}</td>
              {actions && <td style={{ padding: 8, textAlign: "right" }}>{actions(r)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

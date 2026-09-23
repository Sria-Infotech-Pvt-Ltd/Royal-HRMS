import { Fragment } from "react";
import { fmt, type Assessment, type AssessmentCandidate } from "../_types";

function StatusBadge({ status }: { status: AssessmentCandidate["status"] }) {
  if (status === "complete")    return <span className="badge badge-success">Completed</span>;
  if (status === "in_progress") return <span className="badge badge-info">In Progress</span>;
  return <span className="badge" style={{ background: "var(--bg-mid)", color: "var(--on-variant)" }}>Pending</span>;
}

interface AssessmentResultsPanelProps {
  assessment: Assessment;
  expandedBreakdown: string | null;
  onToggleBreakdown: (candidateId: string) => void;
}

export default function AssessmentResultsPanel({ assessment: a, expandedBreakdown, onToggleBreakdown }: AssessmentResultsPanelProps) {
  return (
    <div style={{ borderTop: "1px solid var(--outline-v)", paddingTop: 14 }}>
      {/* Per-test stats */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 8, marginBottom: 16 }}>
        {[
          { label: "Items",       value: a.item_count        ?? 0, icon: "ti-list",         color: "var(--on-variant)" },
          { label: "Assigned",    value: a.assigned_count    ?? 0, icon: "ti-users",        color: "var(--primary)" },
          { label: "Pending",     value: a.pending_count     ?? 0, icon: "ti-clock",        color: "#d97706" },
          { label: "In Progress", value: a.in_progress_count ?? 0, icon: "ti-pencil",       color: "#0284c7" },
          { label: "Completed",   value: a.completed_count   ?? 0, icon: "ti-circle-check", color: "#16a34a" },
        ].map(s => (
          <div key={s.label} className="settings-card" style={{ padding: "10px 12px", textAlign: "center" }}>
            <i className={`ti ${s.icon}`} style={{ color: s.color, fontSize: 15, display: "block", marginBottom: 4 }} />
            <div style={{ fontSize: 18, fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.value}</div>
            <div className="text-xs text-[var(--on-variant)]" style={{ marginTop: 3 }}>{s.label}</div>
          </div>
        ))}
      </div>
      {/* Candidate log */}
      {a.candidates && a.candidates.length > 0 ? (
        <div>
          <p className="text-xs font-semibold text-[var(--on-variant)] mb-8" style={{ textTransform: "uppercase", letterSpacing: "0.06em" }}>
            Candidate Results
          </p>
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "var(--bg-mid, #f8fafc)" }}>
                  {["Candidate", "Status", "Result", "Score %", "Attempts", "Assigned", "Completed", ""].map(h => (
                    <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600, color: "var(--on-variant)", whiteSpace: "nowrap", fontSize: 12 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {a.candidates.map((c, idx) => {
                  const breakdownOpen = expandedBreakdown === c.id;
                  const hasBreakdown  = c.status === "complete" && c.sections_breakdown?.length > 0;
                  return (
                  <Fragment key={c.id}>
                  <tr style={{ borderTop: "1px solid var(--outline-v)", background: idx % 2 === 1 ? "var(--bg-mid, #fafafa)" : "transparent" }}>
                    <td style={{ padding: "10px 12px" }}>
                      <div className="font-medium text-[var(--on-bg)]">{c.assignee_name}</div>
                      <div className="text-xs text-[var(--on-variant)]">{c.assignee_email}</div>
                    </td>
                    <td style={{ padding: "10px 12px" }}><StatusBadge status={c.status} /></td>
                    <td style={{ padding: "10px 12px" }}>
                      {c.status !== "complete"
                        ? <span style={{ color: "var(--on-variant)" }}>—</span>
                        : c.passed === true
                          ? <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontWeight: 700, color: "#15803d", background: "#dcfce7", padding: "2px 10px", borderRadius: 20, fontSize: 12 }}><i className="ti ti-circle-check" style={{ fontSize: 13 }} />Passed</span>
                          : <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontWeight: 700, color: "#dc2626", background: "#fee2e2", padding: "2px 10px", borderRadius: 20, fontSize: 12 }}><i className="ti ti-circle-x" style={{ fontSize: 13 }} />Failed</span>
                      }
                    </td>
                    <td style={{ padding: "10px 12px" }}>
                      <span style={{ fontWeight: 600, color: c.score_percentage === "N/A" ? "var(--on-variant)" : c.passed ? "#16a34a" : "#dc2626" }}>
                        {c.score_percentage}
                      </span>
                    </td>
                    <td style={{ padding: "10px 12px", textAlign: "center", fontWeight: 500 }}>{c.attempt_count}</td>
                    <td style={{ padding: "10px 12px", color: "var(--on-variant)", whiteSpace: "nowrap" }}>{fmt(c.created_at)}</td>
                    <td style={{ padding: "10px 12px", color: "var(--on-variant)", whiteSpace: "nowrap" }}>{fmt(c.completed_at)}</td>
                    <td style={{ padding: "10px 12px", textAlign: "right" }}>
                      {hasBreakdown && (
                        <button
                          className="btn btn-ghost"
                          style={{ padding: "3px 8px", fontSize: 11 }}
                          onClick={() => onToggleBreakdown(c.id)}
                        >
                          <i className={`ti ${breakdownOpen ? "ti-chevron-up" : "ti-chart-bar"}`} />
                          {breakdownOpen ? "" : " Breakdown"}
                        </button>
                      )}
                    </td>
                  </tr>
                  {breakdownOpen && (
                    <tr key={`${c.id}-breakdown`} style={{ background: "var(--bg-mid, #f8fafc)" }}>
                      <td colSpan={8} style={{ padding: "0 12px 12px 12px" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginTop: 8 }}>
                          <thead>
                            <tr style={{ borderBottom: "1px solid var(--outline-v)" }}>
                              {["Section", "Score", "Correct", "Percentage"].map(h => (
                                <th key={h} style={{ padding: "6px 10px", textAlign: "left", fontWeight: 600, color: "var(--on-variant)" }}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {c.sections_breakdown.map((s, si) => (
                              <tr key={si} style={{ borderBottom: "1px solid var(--outline-v)" }}>
                                <td style={{ padding: "6px 10px", fontWeight: 500, color: "var(--on-bg)" }}>{s.title}</td>
                                <td style={{ padding: "6px 10px", fontWeight: 600 }}>{s.achieved_score} / {s.max_score}</td>
                                <td style={{ padding: "6px 10px", color: "var(--on-variant)" }}>{s.correct_answers} / {s.total_questions}</td>
                                <td style={{ padding: "6px 10px", fontWeight: 700, color: parseInt(s.percentage) >= 100 ? "#16a34a" : parseInt(s.percentage) >= 50 ? "#d97706" : "#dc2626" }}>
                                  {s.percentage}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </td>
                    </tr>
                  )}
                  </Fragment>
                );
              })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <p className="text-xs text-[var(--on-variant)] text-center py-8">
          <i className="ti ti-users mr-4" />No candidates assigned yet.
        </p>
      )}
    </div>
  );
}

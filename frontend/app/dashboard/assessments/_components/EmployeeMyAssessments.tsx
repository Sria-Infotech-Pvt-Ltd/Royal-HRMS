"use client";

import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";

interface MyAssignment {
  id: string;
  assessment_title: string;
  pass_percentage: number;
  status: "pending" | "in_progress" | "complete";
  score: number;
  max_score: number;
  total_items: number;
  completed_items: number;
  attempt_count: number;
  effective_max_attempts: number;
  attempts_remaining: number | null;
  deadline: string | null;
  completed_at: string | null;
}

interface MyAssessmentData {
  assignments: MyAssignment[];
  all_complete: boolean;
}

function fmt(iso: string | null) {
  if (!iso) return "—";
  return formatDate(iso);
}

export default function EmployeeMyAssessments() {
  const router = useRouter();
  const { data, loading, error } = useFetch<MyAssessmentData>(API.assessments.my);
  const assignments = data?.assignments ?? [];
  const pending     = assignments.filter(a => a.status !== "complete");
  const completed   = assignments.filter(a => a.status === "complete");

  return (
    <>
      <div className="page-header">
        <div>
          <h2 className="page-title">My Assessments</h2>
          <p className="page-sub">Your assigned assessments and their completion status.</p>
        </div>
      </div>

      {error && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /><div>{error}</div>
        </div>
      )}

      {loading ? (
        <div className="text-center py-20">
          <i className="ti ti-loader-2 spin" style={{ fontSize: 28 }} />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      ) : assignments.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-clipboard-check" style={{ fontSize: 40 }} />
          <h3>No assessments assigned</h3>
          <p>You have no assessments assigned at the moment. Check back later.</p>
        </div>
      ) : (
        <>
          {/* ── Stat cards ── */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginBottom: 24 }}>
            {[
              { label: "Total",     value: assignments.length, icon: "ti-clipboard",      color: "var(--primary)" },
              { label: "Pending",   value: pending.length,     icon: "ti-clock",          color: "#d97706" },
              { label: "Completed", value: completed.length,   icon: "ti-circle-check",   color: "#16a34a" },
            ].map(s => (
              <div key={s.label} className="card" style={{ padding: "16px 20px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                  <div style={{ width: 40, height: 40, borderRadius: 10, background: `color-mix(in srgb, ${s.color} 12%, transparent)`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                    <i className={`ti ${s.icon}`} style={{ color: s.color, fontSize: 18 }} />
                  </div>
                  <div>
                    <div style={{ fontSize: 24, fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.value}</div>
                    <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>{s.label}</div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* ── Pending / In Progress ── */}
          {pending.length > 0 && (
            <div className="mb-24">
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--on-variant)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                <i className="ti ti-clock" style={{ color: "#d97706", marginRight: 6 }} />
                Pending ({pending.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {pending.map(a => {
                  const progress = a.total_items > 0
                    ? Math.round((a.completed_items / a.total_items) * 100)
                    : 0;
                  return (
                    <div key={a.id} className="card" style={{ padding: "16px 20px" }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 600, color: "var(--on-bg)", marginBottom: 6 }}>{a.assessment_title}</div>
                          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: "var(--on-variant)" }}>
                            <span><i className="ti ti-list" style={{ marginRight: 4 }} />{a.completed_items}/{a.total_items} items done</span>
                            <span><i className="ti ti-percentage" style={{ marginRight: 4 }} />{a.pass_percentage}% to pass</span>
                            {a.deadline && (
                              <span><i className="ti ti-calendar-event" style={{ marginRight: 4 }} />Due: {fmt(a.deadline)}</span>
                            )}
                            {a.attempt_count > 0 && (
                              <span><i className="ti ti-refresh" style={{ marginRight: 4 }} />Attempt {a.attempt_count}</span>
                            )}
                          </div>
                          {a.total_items > 0 && (
                            <div style={{ marginTop: 10 }}>
                              <div style={{ height: 4, background: "var(--outline-v)", borderRadius: 4, overflow: "hidden" }}>
                                <div style={{ width: `${progress}%`, height: "100%", background: "#0284c7", borderRadius: 4, transition: "width 0.3s" }} />
                              </div>
                              <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 3 }}>{progress}% complete</div>
                            </div>
                          )}
                        </div>
                        <div style={{ flexShrink: 0, display: "flex", alignItems: "center", gap: 8 }}>
                          {a.status === "in_progress"
                            ? <span className="badge badge-info">In Progress</span>
                            : <span className="badge" style={{ background: "var(--bg-mid)", color: "var(--on-variant)" }}>Pending</span>}
                          <button
                            className="btn btn-filled btn-sm"
                            onClick={() => router.push("/onboarding/assessments")}
                          >
                            <i className="ti ti-pencil" /> {a.status === "in_progress" ? "Continue" : "Start"}
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Completed ── */}
          {completed.length > 0 && (
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, color: "var(--on-variant)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                <i className="ti ti-circle-check" style={{ color: "#16a34a", marginRight: 6 }} />
                Completed ({completed.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {completed.map(a => {
                  const pct    = a.max_score > 0 ? Math.round((a.score / a.max_score) * 100) : 0;
                  const passed = pct >= a.pass_percentage;
                  return (
                    <div key={a.id} className="card" style={{ padding: "16px 20px" }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 600, color: "var(--on-bg)", marginBottom: 6 }}>{a.assessment_title}</div>
                          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: "var(--on-variant)" }}>
                            <span><i className="ti ti-calendar-check" style={{ marginRight: 4 }} />Completed: {fmt(a.completed_at)}</span>
                            <span><i className="ti ti-refresh" style={{ marginRight: 4 }} />{a.attempt_count} attempt{a.attempt_count !== 1 ? "s" : ""}</span>
                            {a.max_score > 0 && (
                              <span style={{ fontWeight: 600, color: passed ? "#16a34a" : "#dc2626" }}>
                                Score: {pct}% (pass: {a.pass_percentage}%)
                              </span>
                            )}
                          </div>
                        </div>
                        <div style={{ flexShrink: 0 }}>
                          {passed ? (
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontWeight: 700, color: "#15803d", background: "#dcfce7", padding: "4px 12px", borderRadius: 20, fontSize: 12 }}>
                              <i className="ti ti-circle-check" style={{ fontSize: 13 }} />Passed
                            </span>
                          ) : (
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontWeight: 700, color: "#dc2626", background: "#fee2e2", padding: "4px 12px", borderRadius: 20, fontSize: 12 }}>
                              <i className="ti ti-circle-x" style={{ fontSize: 13 }} />Failed
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}

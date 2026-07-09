"use client";

import { useState, Fragment } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import ItemsModal from "./_components/ItemsModal";

interface AssessmentSettings {
  default_pass_percentage: number;
  max_attempts:            number;
  time_limit_mins:         number | null;
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AssessmentSection {
  id: string;
  title: string;
  order: number;
  score: number;
  item_count: number;
}

export interface AssessmentItem {
  id: string;
  item_type: "video" | "quiz";
  title: string;
  order: number;
  section: string | null;   // sent on POST/PUT
  section_id: string | null; // returned by GET
  video_url: string;
  duration_secs: number | null;
  question: string;
  option_a: string; option_b: string; option_c: string; option_d: string;
  correct_option: string;
  pass_score: number;
  created_at: string;
}

interface SectionBreakdown {
  title: string;
  max_score: number;
  achieved_score: number;
  correct_answers: number;
  total_questions: number;
  percentage: string;
}

export interface AssessmentCandidate {
  id: string;
  assignee_type: string;
  assignee_id: number;
  assignee_name: string;
  assignee_email: string;
  status: "pending" | "in_progress" | "complete";
  attempt_count: number;
  pass_score: number;
  score_awarded: number;
  pass_percentage: string;
  passed: boolean | null;
  sections_breakdown: SectionBreakdown[];
  completed_at: string | null;
  created_at: string;
}

export interface Assessment {
  id: string;
  title: string;
  description: string;
  is_active: boolean;
  is_default: boolean;
  item_count: number;
  assigned_count: number;
  pending_count: number;
  in_progress_count: number;
  completed_count: number;
  candidates: AssessmentCandidate[];
  items: AssessmentItem[];
  created_at: string;
  // per-assessment overrides (null = inherit global)
  pass_percentage:          number;
  max_attempts:             number | null;
  time_limit_mins:          number | null;
  effective_max_attempts:   number;
  effective_time_limit_mins: number | null;
}

interface AssignEmployee { id: string; employee_id: string; full_name: string; email: string; department: string; }

interface AssessmentForm {
  title: string; description: string; is_active: boolean; is_default: boolean;
  pass_percentage: string;
  max_attempts: string;        // "" = inherit global (null), "0" = unlimited
  time_limit_mins: string;     // "" = no limit (null)
}
const EMPTY: AssessmentForm = {
  title: "", description: "", is_active: true, is_default: false,
  pass_percentage: "70", max_attempts: "", time_limit_mins: "",
};

function apiErr(e: unknown) {
  return (e as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Action failed.";
}

function fmt(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

function StatusBadge({ status }: { status: AssessmentCandidate["status"] }) {
  if (status === "complete")    return <span className="badge badge-success">Completed</span>;
  if (status === "in_progress") return <span className="badge badge-info">In Progress</span>;
  return <span className="badge" style={{ background: "var(--bg-mid)", color: "var(--on-variant)" }}>Pending</span>;
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AssessmentsPage() {
  const { data, loading, error, refetch } = useFetch<{ results: Assessment[] }>(API.assessments.list);
  const assessments = data?.results ?? [];

  const { data: settingsData } = useFetch<AssessmentSettings>(API.settings.assessmentConfig);

  const [formModal, setFormModal] = useState<{ open: boolean; target: Assessment | null }>({ open: false, target: null });
  const [form,      setForm]      = useState<AssessmentForm>(EMPTY);
  const [saving,    setSaving]    = useState(false);
  const [formErr,   setFormErr]   = useState("");

  const [itemsFor,    setItemsFor]    = useState<Assessment | null>(null);
  const [expandedId,  setExpandedId]  = useState<string | null>(null);
  const [expandedBreakdown, setExpandedBreakdown] = useState<string | null>(null);

  function toggleResults(id: string) { setExpandedId(prev => prev === id ? null : id); }

  const [assignFor,    setAssignFor]    = useState<Assessment | null>(null);
  const [assignCids,   setAssignCids]   = useState<string[]>([]);
  const [assignSearch, setAssignSearch] = useState("");
  const [assigning,    setAssigning]    = useState(false);
  const [assignErr,    setAssignErr]    = useState("");
  const [assignOk,     setAssignOk]     = useState("");

  const { data: empData } = useFetch<{ results: AssignEmployee[] }>(
    assignFor ? `${API.employees.list}?page_size=500` : null
  );
  const assignCandidates = empData?.results ?? [];
  const filteredCandidates = assignCandidates.filter(e =>
    assignSearch === "" ||
    e.full_name.toLowerCase().includes(assignSearch.toLowerCase()) ||
    e.email.toLowerCase().includes(assignSearch.toLowerCase()) ||
    e.employee_id.toLowerCase().includes(assignSearch.toLowerCase())
  );

  // ── Overall stats ──────────────────────────────────────────────────────────

  const totalAssigned    = assessments.reduce((s, a) => s + (a.assigned_count    ?? 0), 0);
  const totalPending     = assessments.reduce((s, a) => s + (a.pending_count     ?? 0), 0);
  const totalInProgress  = assessments.reduce((s, a) => s + (a.in_progress_count ?? 0), 0);
  const totalCompleted   = assessments.reduce((s, a) => s + (a.completed_count   ?? 0), 0);

  // ── Assessment CRUD ────────────────────────────────────────────────────────

  function openCreate() {
    setForm({
      ...EMPTY,
      pass_percentage: String(settingsData?.default_pass_percentage ?? 70),
      max_attempts:    "",
      time_limit_mins: settingsData?.time_limit_mins ? String(settingsData.time_limit_mins) : "",
    });
    setFormErr(""); setFormModal({ open: true, target: null });
  }
  function openEdit(a: Assessment) {
    setForm({
      title: a.title, description: a.description, is_active: a.is_active, is_default: a.is_default,
      pass_percentage: String(a.pass_percentage),
      max_attempts:    a.max_attempts != null ? String(a.max_attempts) : "",
      time_limit_mins: a.time_limit_mins != null ? String(a.time_limit_mins) : "",
    });
    setFormErr(""); setFormModal({ open: true, target: a });
  }

  async function saveAssessment() {
    if (!form.title.trim()) { setFormErr("Title is required."); return; }
    setSaving(true); setFormErr("");
    const payload = {
      title:          form.title,
      description:    form.description,
      is_active:      form.is_active,
      is_default:     form.is_default,
      pass_percentage: Number(form.pass_percentage) || 70,
      max_attempts:   form.max_attempts !== "" ? Number(form.max_attempts) : null,
      time_limit_mins: form.time_limit_mins !== "" ? Number(form.time_limit_mins) : null,
    };
    try {
      formModal.target
        ? await clientApi.put(API.assessments.detail(formModal.target.id), payload)
        : await clientApi.post(API.assessments.list, payload);
      refetch();
      setFormModal({ open: false, target: null });
    } catch (e) { setFormErr(apiErr(e)); }
    finally { setSaving(false); }
  }

  async function deleteAssessment(id: string) {
    if (!confirm("Delete this assessment? This cannot be undone.")) return;
    try { await clientApi.delete(API.assessments.detail(id)); refetch(); }
    catch (e) { alert(apiErr(e)); }
  }

  // ── Assign ─────────────────────────────────────────────────────────────────

  function openAssign(a: Assessment) {
    setAssignFor(a); setAssignCids([]); setAssignSearch(""); setAssignErr(""); setAssignOk("");
  }

  function toggleAssignCid(id: string) {
    setAssignCids(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]);
  }

  function toggleSelectAll() {
    setAssignCids(prev =>
      prev.length === filteredCandidates.length ? [] : filteredCandidates.map(e => e.id)
    );
  }

  async function doAssign() {
    if (assignCids.length === 0) { setAssignErr("Select at least one employee."); return; }
    setAssigning(true); setAssignErr(""); setAssignOk("");
    let ok = 0;
    const errors: string[] = [];
    for (const empId of assignCids) {
      try {
        await clientApi.post(API.assessments.assign, { candidate_id: empId, assessment_id: assignFor!.id });
        ok++;
      } catch (e) { errors.push(apiErr(e)); }
    }
    setSaving(false);
    if (errors.length === 0) {
      setAssignOk(`Assigned to ${ok} employee${ok !== 1 ? "s" : ""} successfully!`);
      setAssignCids([]);
    } else {
      setAssignErr(`${ok} succeeded, ${errors.length} failed: ${errors[0]}`);
    }
    setAssigning(false);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="page-body">

      {/* Page header */}
      <div className="flex items-center justify-between mb-16">
        <div>
          <h2 className="page-title">Assessment Management</h2>
          <p className="page-subtitle">Build pre-onboarding assessments and assign them to candidates</p>
        </div>
        <button className="btn btn-primary" onClick={openCreate}>
          <i className="ti ti-plus" /> New Assessment
        </button>
      </div>

      {/* Overall stats */}
      {!loading && assessments.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 24 }}>
          {[
            { label: "Total Assigned",    value: totalAssigned,   icon: "ti-users",        color: "var(--primary)" },
            { label: "Pending",           value: totalPending,    icon: "ti-clock",        color: "#d97706" },
            { label: "In Progress",       value: totalInProgress, icon: "ti-pencil",       color: "#0284c7" },
            { label: "Completed",         value: totalCompleted,  icon: "ti-circle-check", color: "#16a34a" },
          ].map(s => (
            <div key={s.label} className="card" style={{ padding: "16px 20px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 40, height: 40, borderRadius: 10, background: `color-mix(in srgb, ${s.color} 12%, transparent)`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <i className={`ti ${s.icon}`} style={{ color: s.color, fontSize: 18 }} />
                </div>
                <div>
                  <div style={{ fontSize: 24, fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.value}</div>
                  <div className="text-xs text-[var(--on-variant)]" style={{ marginTop: 3 }}>{s.label}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /><div>{error}</div></div>}

      {loading ? (
        <div className="text-center py-20"><i className="ti ti-loader-2 spin" style={{ fontSize: 28 }} /></div>
      ) : assessments.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-clipboard" />
          <h3>No assessments yet</h3>
          <p>Create your first assessment to assign to candidates during onboarding.</p>
          <button className="btn btn-primary mt-12" onClick={openCreate}>Create Assessment</button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {assessments.map(a => (
            <div key={a.id} className="card">
              <div className="card-body">

                {/* Assessment header row */}
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 16, marginBottom: expandedId === a.id ? 14 : 0 }}>
                  <div className="flex-1">
                    <div className="flex items-center gap-8 flex-wrap mb-4">
                      <span className="font-semibold text-[var(--on-bg)]">{a.title}</span>
                      {a.is_active  && <span className="badge badge-success">Active</span>}
                      {a.is_default && <span className="badge badge-info">Default</span>}
                    </div>
                    {a.description && <p className="text-sm text-[var(--on-variant)] mb-4">{a.description}</p>}
                    <div className="flex items-center gap-12 flex-wrap" style={{ fontSize: 12, color: "var(--on-variant)" }}>
                      <span><i className="ti ti-percentage mr-4" />{a.pass_percentage}% pass</span>
                      <span><i className="ti ti-refresh mr-4" />{a.effective_max_attempts === 0 ? "Unlimited" : `${a.effective_max_attempts} attempt${a.effective_max_attempts !== 1 ? "s" : ""}`}{a.max_attempts == null ? " (global)" : ""}</span>
                      <span><i className="ti ti-clock mr-4" />{a.effective_time_limit_mins ? `${a.effective_time_limit_mins} min` : "No limit"}{a.time_limit_mins == null && a.effective_time_limit_mins ? " (global)" : ""}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-8 flex-wrap shrink-0">
                    <button className="btn btn-ghost btn-sm" onClick={() => toggleResults(a.id)}>
                      <i className={`ti ${expandedId === a.id ? "ti-chevron-up" : "ti-chevron-down"}`} /> Results
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setItemsFor(a)}>
                      <i className="ti ti-layout-list" /> Sections
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => openAssign(a)}>
                      <i className="ti ti-user-plus" /> Assign
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => openEdit(a)}>
                      <i className="ti ti-pencil" />
                    </button>
                    <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }} onClick={() => deleteAssessment(a.id)}>
                      <i className="ti ti-trash" />
                    </button>
                  </div>
                </div>

                {/* Expandable results: stats + candidate log */}
                {expandedId === a.id && (
                  <div style={{ borderTop: "1px solid var(--outline-v)", paddingTop: 14 }}>
                    {/* Per-test stats */}
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 8, marginBottom: 16 }}>
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
                                {["Candidate", "Status", "Result", "Pass %", "Attempts", "Assigned", "Completed", ""].map(h => (
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
                                    <span style={{ fontWeight: 600, color: c.pass_percentage === "N/A" ? "var(--on-variant)" : parseInt(c.pass_percentage) >= 100 ? "#16a34a" : "#dc2626" }}>
                                      {c.pass_percentage}
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
                                        onClick={() => setExpandedBreakdown(breakdownOpen ? null : c.id)}
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
                )}

              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Assessment create / edit modal ── */}
      {formModal.open && (
        <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && setFormModal({ open: false, target: null })}>
          <div className="modal" style={{ maxWidth: 500 }}>
            <div className="modal-header">
              <div className="modal-title">{formModal.target ? "Edit Assessment" : "New Assessment"}</div>
              <button className="modal-close" onClick={() => setFormModal({ open: false, target: null })}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              {formErr && <div className="alert alert-error mb-12"><i className="ti ti-alert-circle" /><div>{formErr}</div></div>}
              <div className="field-group mb-12">
                <label className="field-label">Title *</label>
                <input className="field-input" value={form.title} placeholder="e.g. Onboarding Assessment"
                  onChange={e => setForm(p => ({ ...p, title: e.target.value }))} />
              </div>
              <div className="field-group mb-12">
                <label className="field-label">Description</label>
                <textarea className="field-input" rows={2} value={form.description}
                  onChange={e => setForm(p => ({ ...p, description: e.target.value }))} />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 12 }}>
                <div className="field-group mb-0">
                  <label className="field-label">Pass % *</label>
                  <input type="number" min={1} max={100} className="field-input"
                    value={form.pass_percentage}
                    onChange={e => setForm(p => ({ ...p, pass_percentage: e.target.value }))}
                    placeholder="70" />
                </div>
                <div className="field-group mb-0">
                  <label className="field-label">Max Attempts</label>
                  <input type="number" min={0} className="field-input"
                    value={form.max_attempts}
                    onChange={e => setForm(p => ({ ...p, max_attempts: e.target.value }))}
                    placeholder="Use global (0=∞)" />
                </div>
                <div className="field-group mb-0">
                  <label className="field-label">Time Limit (min)</label>
                  <input type="number" min={1} className="field-input"
                    value={form.time_limit_mins}
                    onChange={e => setForm(p => ({ ...p, time_limit_mins: e.target.value }))}
                    placeholder="None" />
                </div>
              </div>
              <div style={{ fontSize: ".72rem", color: "var(--on-variant)", marginBottom: 12 }}>
                Leave Max Attempts / Time Limit blank to inherit the global default from Settings → Assessment Config.
              </div>
              <div className="flex gap-20">
                <label className="flex items-center gap-8 cursor-pointer text-sm">
                  <input type="checkbox" checked={form.is_active}
                    onChange={e => setForm(p => ({ ...p, is_active: e.target.checked }))} />
                  Active
                </label>
                <label className="flex items-center gap-8 cursor-pointer text-sm">
                  <input type="checkbox" checked={form.is_default}
                    onChange={e => setForm(p => ({ ...p, is_default: e.target.checked }))} />
                  Default (auto-assign)
                </label>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setFormModal({ open: false, target: null })}>Cancel</button>
              <button className="btn btn-primary" onClick={saveAssessment} disabled={saving}>
                {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Assign modal ── */}
      {assignFor && (
        <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && setAssignFor(null)}>
          <div className="modal" style={{ maxWidth: 500 }}>
            <div className="modal-header">
              <div className="modal-title">Assign — {assignFor.title}</div>
              <button className="modal-close" onClick={() => setAssignFor(null)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              {assignErr && <div className="alert alert-error mb-12"><i className="ti ti-alert-circle" /><div>{assignErr}</div></div>}
              {assignOk  && <div className="alert alert-success mb-12"><i className="ti ti-check" /><div>{assignOk}</div></div>}

              {/* Search */}
              <div className="field-group mb-8">
                <div style={{ position: "relative" }}>
                  <i className="ti ti-search" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--on-variant)", fontSize: 14, pointerEvents: "none" }} />
                  <input
                    className="field-input"
                    style={{ paddingLeft: 32 }}
                    placeholder="Search by name, email or ID…"
                    value={assignSearch}
                    onChange={e => setAssignSearch(e.target.value)}
                  />
                </div>
              </div>

              {/* Select All / count */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                <button
                  className="btn btn-ghost"
                  style={{ fontSize: 12, padding: "2px 8px" }}
                  onClick={toggleSelectAll}
                  disabled={filteredCandidates.length === 0}
                >
                  {assignCids.length === filteredCandidates.length && filteredCandidates.length > 0 ? "Deselect All" : "Select All"}
                </button>
                <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
                  {assignCids.length} selected · {filteredCandidates.length} shown
                </span>
              </div>

              {/* Employee checklist */}
              <div style={{ maxHeight: 260, overflowY: "auto", border: "1px solid var(--outline-v)", borderRadius: 8 }}>
                {filteredCandidates.length === 0 && (
                  <div style={{ padding: "20px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
                    {assignCandidates.length === 0 ? <><i className="ti ti-loader-2 spin mr-6" />Loading…</> : "No employees match."}
                  </div>
                )}
                {filteredCandidates.map((e, idx) => {
                  const checked = assignCids.includes(e.id);
                  return (
                    <label
                      key={e.id}
                      style={{
                        display: "flex", alignItems: "center", gap: 10,
                        padding: "9px 12px", cursor: "pointer",
                        borderTop: idx === 0 ? "none" : "1px solid var(--outline-v)",
                        background: checked ? "var(--primary-c, rgba(30,78,140,0.07))" : "transparent",
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggleAssignCid(e.id)}
                        style={{ flexShrink: 0 }}
                      />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{e.full_name}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{e.employee_id} · {e.email}{e.department ? ` · ${e.department}` : ""}</div>
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setAssignFor(null)}>Close</button>
              <button className="btn btn-primary" onClick={doAssign} disabled={assigning || assignCids.length === 0}>
                {assigning
                  ? <><i className="ti ti-loader-2 spin" /> Assigning…</>
                  : <><i className="ti ti-user-plus" /> Assign{assignCids.length > 1 ? ` (${assignCids.length})` : ""}</>}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Items management modal ── */}
      {itemsFor && (
        <ItemsModal
          assessment={itemsFor}
          onClose={() => { setItemsFor(null); refetch(); }}
        />
      )}
    </div>
  );
}

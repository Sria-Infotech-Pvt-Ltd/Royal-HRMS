"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import ItemsModal from "./_components/ItemsModal";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AssessmentItem {
  id: string;
  item_type: "video" | "quiz";
  title: string;
  order: number;
  video_url: string;
  duration_secs: number | null;
  question: string;
  option_a: string; option_b: string; option_c: string; option_d: string;
  correct_option: string;
  pass_score: number;
  created_at: string;
}

export interface AssessmentCandidate {
  id: string;
  candidate_id: number;
  candidate_name: string;
  candidate_email: string;
  status: "pending" | "in_progress" | "complete";
  attempt_count: number;
  pass_score: number;
  score_awarded: number;
  pass_percentage: string;
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
}

interface ReviewCandidate { id: string; name: string; email: string; }

interface AssessmentForm { title: string; description: string; is_active: boolean; is_default: boolean; }
const EMPTY: AssessmentForm = { title: "", description: "", is_active: true, is_default: false };

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

  const [formModal, setFormModal] = useState<{ open: boolean; target: Assessment | null }>({ open: false, target: null });
  const [form,      setForm]      = useState<AssessmentForm>(EMPTY);
  const [saving,    setSaving]    = useState(false);
  const [formErr,   setFormErr]   = useState("");

  const [itemsFor,    setItemsFor]    = useState<Assessment | null>(null);
  const [expandedId,  setExpandedId]  = useState<string | null>(null);

  function toggleResults(id: string) { setExpandedId(prev => prev === id ? null : id); }

  const [assignFor, setAssignFor] = useState<Assessment | null>(null);
  const [assignCid, setAssignCid] = useState("");
  const [assigning, setAssigning] = useState(false);
  const [assignErr, setAssignErr] = useState("");
  const [assignOk,  setAssignOk]  = useState("");

  const { data: candData } = useFetch<{ results: ReviewCandidate[] }>(
    assignFor ? API.recruitment.review : null
  );
  const reviewCandidates = candData?.results ?? [];

  // ── Overall stats ──────────────────────────────────────────────────────────

  const totalAssigned    = assessments.reduce((s, a) => s + (a.assigned_count    ?? 0), 0);
  const totalPending     = assessments.reduce((s, a) => s + (a.pending_count     ?? 0), 0);
  const totalInProgress  = assessments.reduce((s, a) => s + (a.in_progress_count ?? 0), 0);
  const totalCompleted   = assessments.reduce((s, a) => s + (a.completed_count   ?? 0), 0);

  // ── Assessment CRUD ────────────────────────────────────────────────────────

  function openCreate() { setForm(EMPTY); setFormErr(""); setFormModal({ open: true, target: null }); }
  function openEdit(a: Assessment) {
    setForm({ title: a.title, description: a.description, is_active: a.is_active, is_default: a.is_default });
    setFormErr(""); setFormModal({ open: true, target: a });
  }

  async function saveAssessment() {
    if (!form.title.trim()) { setFormErr("Title is required."); return; }
    setSaving(true); setFormErr("");
    try {
      formModal.target
        ? await clientApi.put(API.assessments.detail(formModal.target.id), form)
        : await clientApi.post(API.assessments.list, form);
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
    setAssignFor(a); setAssignCid(""); setAssignErr(""); setAssignOk("");
  }

  async function doAssign() {
    if (!assignCid) { setAssignErr("Select a candidate."); return; }
    setAssigning(true); setAssignErr(""); setAssignOk("");
    try {
      await clientApi.post(API.assessments.assign, { candidate_id: assignCid, assessment_id: assignFor!.id });
      setAssignOk("Assessment assigned successfully!"); setAssignCid("");
    } catch (e) { setAssignErr(apiErr(e)); }
    finally { setAssigning(false); }
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
                    {a.description && <p className="text-sm text-[var(--on-variant)] mb-0">{a.description}</p>}
                  </div>
                  <div className="flex items-center gap-8 flex-wrap shrink-0">
                    <button className="btn btn-ghost btn-sm" onClick={() => toggleResults(a.id)}>
                      <i className={`ti ${expandedId === a.id ? "ti-chevron-up" : "ti-chevron-down"}`} /> Results
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => setItemsFor(a)}>
                      <i className="ti ti-list-details" /> Items
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
                                {["Candidate", "Status", "Score", "Pass %", "Attempts", "Assigned", "Completed"].map(h => (
                                  <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontWeight: 600, color: "var(--on-variant)", whiteSpace: "nowrap", fontSize: 12 }}>{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {a.candidates.map((c, idx) => (
                                <tr key={c.id} style={{ borderTop: "1px solid var(--outline-v)", background: idx % 2 === 1 ? "var(--bg-mid, #fafafa)" : "transparent" }}>
                                  <td style={{ padding: "10px 12px" }}>
                                    <div className="font-medium text-[var(--on-bg)]">{c.candidate_name}</div>
                                    <div className="text-xs text-[var(--on-variant)]">{c.candidate_email}</div>
                                  </td>
                                  <td style={{ padding: "10px 12px" }}><StatusBadge status={c.status} /></td>
                                  <td style={{ padding: "10px 12px", fontWeight: 600 }}>
                                    {c.status === "complete" ? `${c.score_awarded} / ${c.pass_score}` : "—"}
                                  </td>
                                  <td style={{ padding: "10px 12px" }}>
                                    <span style={{ fontWeight: 600, color: c.pass_percentage === "N/A" ? "var(--on-variant)" : parseInt(c.pass_percentage) >= 100 ? "#16a34a" : "#dc2626" }}>
                                      {c.pass_percentage}
                                    </span>
                                  </td>
                                  <td style={{ padding: "10px 12px", textAlign: "center", fontWeight: 500 }}>{c.attempt_count}</td>
                                  <td style={{ padding: "10px 12px", color: "var(--on-variant)", whiteSpace: "nowrap" }}>{fmt(c.created_at)}</td>
                                  <td style={{ padding: "10px 12px", color: "var(--on-variant)", whiteSpace: "nowrap" }}>{fmt(c.completed_at)}</td>
                                </tr>
                              ))}
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
          <div className="modal" style={{ maxWidth: 460 }}>
            <div className="modal-header">
              <div className="modal-title">Assign — {assignFor.title}</div>
              <button className="modal-close" onClick={() => setAssignFor(null)}><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body">
              {assignErr && <div className="alert alert-error mb-12"><i className="ti ti-alert-circle" /><div>{assignErr}</div></div>}
              {assignOk  && <div className="alert alert-success mb-12"><i className="ti ti-check" /><div>{assignOk}</div></div>}
              <div className="field-group">
                <label className="field-label">Candidate *</label>
                <select className="field-input field-select" value={assignCid} onChange={e => setAssignCid(e.target.value)}>
                  <option value="">— Select candidate —</option>
                  {reviewCandidates.map(c => (
                    <option key={c.id} value={c.id}>{c.name} · {c.email}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setAssignFor(null)}>Close</button>
              <button className="btn btn-primary" onClick={doAssign} disabled={assigning || !assignCid}>
                {assigning ? <><i className="ti ti-loader-2 spin" /> Assigning…</> : <><i className="ti ti-user-plus" /> Assign</>}
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

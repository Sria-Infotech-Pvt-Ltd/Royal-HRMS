"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission, useAnyPermission } from "@/hooks/usePermission";
import ItemsModal from "./_components/ItemsModal";
import EmployeeMyAssessments from "./_components/EmployeeMyAssessments";
import AssessmentResultsPanel from "./_components/AssessmentResultsPanel";
import AssignAssessmentModal from "./_components/AssignAssessmentModal";
import Modal from "@/components/Modal";
import {
  EMPTY, apiErr,
  type AssessmentSettings, type Assessment, type AssignEmployee,
  type EmailTemplateOption, type AssessmentForm,
} from "./_types";

export type { AssessmentSection, AssessmentItem, AssessmentCandidate, Assessment } from "./_types";

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AssessmentsPage() {
  // Users with assessments permissions see the HR management view;
  // everyone else (e.g. employees) sees their own assignments.
  // (The backend gates every assessments/* endpoint on assessments.*, not
  // recruitment.* — see apps/assessments/views/admin.py — so a role granted
  // only the Assessments permission set was previously bounced to the
  // employee "My Assessments" view with no way to create/edit/delete.)
  const isAdminView = useAnyPermission("assessments.view", "assessments.create", "assessments.edit", "assessments.delete");

  const canCreate = usePermission("assessments.create");
  // Assigning an assessment and managing its sections both PUT/POST through
  // endpoints gated on assessments.edit on the backend (AssignAssessmentView,
  // AssessmentItemListCreateView) — not assessments.create.
  const canEdit   = usePermission("assessments.edit");
  const canDelete = usePermission("assessments.delete");

  // Skip the admin list fetch for employees — useFetch(null) is a no-op.
  const { data, loading, error, refetch } = useFetch<{ results: Assessment[] }>(
    isAdminView ? API.assessments.list : null
  );
  const assessments = data?.results ?? [];

  const { data: settingsData } = useFetch<AssessmentSettings>(
    isAdminView ? API.settings.assessmentConfig : null
  );

  const [formModal, setFormModal] = useState<{ open: boolean; target: Assessment | null }>({ open: false, target: null });
  const [form,      setForm]      = useState<AssessmentForm>(EMPTY);
  const [saving,    setSaving]    = useState(false);
  const [formErr,   setFormErr]   = useState("");

  const [deleteErr,   setDeleteErr]   = useState("");
  const [itemsFor,    setItemsFor]    = useState<Assessment | null>(null);
  const [expandedId,  setExpandedId]  = useState<string | null>(null);
  const [expandedBreakdown, setExpandedBreakdown] = useState<string | null>(null);

  function toggleResults(id: string) { setExpandedId(prev => prev === id ? null : id); }

  const [assignFor,      setAssignFor]      = useState<Assessment | null>(null);
  const [assignCids,     setAssignCids]     = useState<string[]>([]);
  const [assignSearch,   setAssignSearch]   = useState("");
  const [assigning,      setAssigning]      = useState(false);
  const [assignErr,      setAssignErr]      = useState("");
  const [assignOk,       setAssignOk]       = useState("");
  const [assignTemplate, setAssignTemplate] = useState("assessment_assigned");

  const { data: empData } = useFetch<{ results: AssignEmployee[] }>(
    assignFor ? `${API.employees.list}?page_size=500` : null
  );
  const assignCandidates = empData?.results ?? [];

  const { data: emailTemplateOptions } = useFetch<EmailTemplateOption[]>(
    assignFor ? API.assessments.emailTemplateOptions : null
  );
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
    setDeleteErr("");
    try { await clientApi.delete(API.assessments.detail(id)); refetch(); }
    catch (e) { setDeleteErr(apiErr(e)); }
  }

  // ── Assign ─────────────────────────────────────────────────────────────────

  function openAssign(a: Assessment) {
    setAssignFor(a); setAssignCids([]); setAssignSearch(""); setAssignErr(""); setAssignOk(""); setAssignTemplate("assessment_assigned");
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
        await clientApi.post(API.assessments.assign, { candidate_id: empId, assessment_id: assignFor!.id, template_name: assignTemplate });
        ok++;
      } catch (e) { errors.push(apiErr(e)); }
    }
    setSaving(false);
    if (errors.length === 0) {
      setAssignOk(`Assigned to ${ok} employee${ok !== 1 ? "s" : ""} successfully!`);
      setAssignCids([]);
      refetch();
    } else {
      setAssignErr(`${ok} succeeded, ${errors.length} failed: ${errors[0]}`);
    }
    setAssigning(false);
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  // Employees see their own assignments, not the management view.
  if (!isAdminView) return <EmployeeMyAssessments />;

  return (
    <>

      {/* Page header */}
      <div className="page-header">
        <div>
          <h2 className="page-title">Assessment Management</h2>
          <p className="page-sub">Build pre-onboarding assessments and assign them to candidates</p>
        </div>
        <div className="page-actions">
          {canCreate && (
            <button className="btn btn-filled" onClick={openCreate}>
              <i className="ti ti-plus" /> New Assessment
            </button>
          )}
        </div>
      </div>

      {/* Overall stats */}
      {!loading && assessments.length > 0 && (
        <div className="stats-grid">
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
      {deleteErr && (
        <div className="alert alert-error mb-16" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <i className="ti ti-alert-circle" style={{ flexShrink: 0 }} />
          <div style={{ flex: 1 }}>{deleteErr}</div>
          <button
            onClick={() => setDeleteErr("")}
            style={{ background: "none", border: "none", cursor: "pointer", padding: 4, color: "inherit" }}
          >
            <i className="ti ti-x" style={{ fontSize: 14 }} />
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-center py-20"><i className="ti ti-loader-2 spin" style={{ fontSize: 28 }} /></div>
      ) : assessments.length === 0 ? (
        <div className="empty-state">
          <i className="ti ti-clipboard" />
          <h3>No assessments yet</h3>
          <p>Create your first assessment to assign to candidates during onboarding.</p>
          {canCreate && <button className="btn btn-filled mt-12" onClick={openCreate}>Create Assessment</button>}
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
                    {canEdit && (
                      <button className="btn btn-ghost btn-sm" onClick={() => setItemsFor(a)}>
                        <i className="ti ti-layout-list" /> Sections
                      </button>
                    )}
                    {canEdit && (
                      <button className="btn btn-ghost btn-sm" onClick={() => openAssign(a)}>
                        <i className="ti ti-user-plus" /> Assign
                      </button>
                    )}
                    {canEdit && (
                      <button className="btn btn-ghost btn-sm" title="Edit assessment" onClick={() => openEdit(a)}>
                        <i className="ti ti-pencil" />
                      </button>
                    )}
                    {canDelete && (
                      <button className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }} title="Delete assessment" onClick={() => deleteAssessment(a.id)}>
                        <i className="ti ti-trash" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Expandable results: stats + candidate log */}
                {expandedId === a.id && (
                  <AssessmentResultsPanel
                    assessment={a}
                    expandedBreakdown={expandedBreakdown}
                    onToggleBreakdown={id => setExpandedBreakdown(prev => prev === id ? null : id)}
                  />
                )}

              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Assessment create / edit modal ── */}
      {formModal.open && (
        <Modal
          title={formModal.target ? "Edit Assessment" : "New Assessment"}
          onClose={() => setFormModal({ open: false, target: null })}
          maxWidth={500}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setFormModal({ open: false, target: null })}>Cancel</button>
              <button className="btn btn-primary" onClick={saveAssessment} disabled={saving}>
                {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Save"}
              </button>
            </>
          }
        >
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
        </Modal>
      )}

      {/* ── Assign modal ── */}
      {assignFor && (
        <AssignAssessmentModal
          assignFor={assignFor}
          onClose={() => setAssignFor(null)}
          assignCids={assignCids}
          toggleAssignCid={toggleAssignCid}
          toggleSelectAll={toggleSelectAll}
          assignSearch={assignSearch}
          setAssignSearch={setAssignSearch}
          assignTemplate={assignTemplate}
          setAssignTemplate={setAssignTemplate}
          emailTemplateOptions={emailTemplateOptions}
          assignCandidates={assignCandidates}
          filteredCandidates={filteredCandidates}
          assigning={assigning}
          assignErr={assignErr}
          assignOk={assignOk}
          doAssign={doAssign}
        />
      )}

      {/* ── Items management modal ── */}
      {itemsFor && (
        <ItemsModal
          assessment={itemsFor}
          onClose={() => { setItemsFor(null); refetch(); }}
        />
      )}
    </>
  );
}

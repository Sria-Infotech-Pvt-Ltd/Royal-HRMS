"use client";

import { useCallback, useState } from "react";
import clientApi from "@/lib/clientApi";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import DocPreviewModal from "@/components/DocPreviewModal";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ProfileData {
  date_of_birth?: string; gender?: string; marital_status?: string;
  father_name?: string; blood_group?: string;
  current_address?: string; permanent_address?: string;
  highest_qualification?: string; institution?: string;
  year_of_passing?: number; specialization?: string;
  total_experience_years?: string; previous_employer?: string;
  previous_designation?: string;
  account_number?: string; ifsc_code?: string; bank_name?: string;
  bank_branch_name?: string; account_holder_name?: string; account_type?: string;
  emergency_name?: string; emergency_relationship?: string;
  emergency_phone?: string; emergency_email?: string;
}

interface OnboardingDocument { id: number; document_type_display: string; file_name: string; file_url: string; file_size?: number; }

interface ApprovalUser {
  id: string; full_name: string; email: string; phone: string;
  department: string; designation: string; branch: string;
  role_name: string; role_display: string; employee_id: string;
  onboarding_status: string; date_joined: string;
  profile: ProfileData | null;
  documents: OnboardingDocument[];
}

interface PageData { count: number; page: number; total_pages: number; results: ApprovalUser[]; }

interface EmailTemplate { id: number; name: string; display_name: string; subject: string; is_active: boolean; template_type: string; }
interface AssessmentOption { id: string; title: string; is_default: boolean; is_active: boolean; }
interface ApiDept { id: number; name: string; is_active: boolean; }
interface ApiManager { id: string; full_name: string; employee_id: string; }

// ── Sub-components ────────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: "1.25rem" }}>
      <div style={{ fontWeight: 700, fontSize: ".8rem", textTransform: "uppercase", letterSpacing: ".05em", color: "var(--text-muted)", marginBottom: ".5rem" }}>
        {title}
      </div>
      {children}
    </div>
  );
}

function Row({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: ".3rem 0", fontSize: ".85rem", borderBottom: "1px solid var(--border)" }}>
      <span style={{ color: "var(--text-secondary)" }}>{label}</span>
      <span style={{ fontWeight: 500 }}>{value}</span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export default function OnboardingQueueTab() {
  const [page,       setPage]       = useState(1);
  const [selected,   setSelected]   = useState<ApprovalUser | null>(null);
  const [remarks,    setRemarks]    = useState("");
  const [acting,     setActing]     = useState(false);
  const [actionMsg,  setActionMsg]  = useState<string | null>(null);
  const [actionErr,  setActionErr]  = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<OnboardingDocument | null>(null);

  // Approval popup modal state
  const [showApprovalModal,    setShowApprovalModal]    = useState(false);
  const [selectedTemplateId,    setSelectedTemplateId]    = useState<number | "">("");
  const [selectedAssessmentIds, setSelectedAssessmentIds] = useState<string[]>([]);
  const [approvalDept,         setApprovalDept]         = useState("");
  const [approvalDesig,        setApprovalDesig]        = useState("");
  const [approvalManagerId,    setApprovalManagerId]    = useState("");
  const [approvalCtc,          setApprovalCtc]          = useState("");
  const [modalErr,             setModalErr]             = useState<string | null>(null);

  const url = `${API.onboarding.approvals}?page=${page}&page_size=20`;
  const { data, loading, error, refetch } = useFetch<PageData>(url);

  // Prefetch while drawer is open
  const { data: tmplData   } = useFetch<Record<string, EmailTemplate[]>>(selected ? API.settings.emailTemplates                : null);
  const { data: assData    } = useFetch<{ results: AssessmentOption[] }>(selected ? API.assessments.list                       : null);
  const { data: deptData   } = useFetch<ApiDept[]>(                     selected ? API.departments.list                        : null);
  const { data: managerRaw } = useFetch<{ results: ApiManager[] }>(     selected ? `${API.employees.managerList}?page_size=200` : null);

  const allTemplates:   EmailTemplate[]   = tmplData ? Object.values(tmplData).flat().filter(t => t.is_active) : [];
  const allAssessments: AssessmentOption[] = (assData?.results ?? []).filter(a => a.is_active);
  const allDepts:       ApiDept[]          = (deptData ?? []).filter(d => d.is_active);
  const allManagers:    ApiManager[]       = managerRaw?.results ?? [];

  function openApprovalModal() {
    setSelectedAssessmentIds(allAssessments.filter(a => a.is_default).map(a => a.id));
    setSelectedTemplateId("");
    setApprovalDept(selected?.department ?? "");
    setApprovalDesig(selected?.designation ?? "");
    setApprovalManagerId("");
    setApprovalCtc("");
    setModalErr(null);
    setShowApprovalModal(true);
  }

  function closeApprovalModal() {
    setShowApprovalModal(false);
    setModalErr(null);
  }

  function closeDrawer() {
    setSelected(null);
    setRemarks("");
    setShowApprovalModal(false);
    setActionMsg(null);
    setActionErr(null);
  }

  const act = useCallback(async (userId: string, decision: "approve" | "reject") => {
    if (decision === "approve") {
      if (!approvalDept)      { setModalErr("Department is required."); return; }
      if (!approvalDesig)     { setModalErr("Designation is required."); return; }
      if (!approvalManagerId) { setModalErr("Reporting Manager is required."); return; }
    }

    setActing(true); setModalErr(null); setActionErr(null);
    try {
      const payload: Record<string, unknown> = { decision, remarks };
      if (decision === "approve") {
        payload.department           = approvalDept;
        payload.designation          = approvalDesig;
        payload.reporting_manager_id = approvalManagerId;
        if (approvalCtc)                     payload.annual_ctc        = approvalCtc;
        if (selectedTemplateId)              payload.email_template_id = selectedTemplateId;
        if (selectedAssessmentIds.length > 0) payload.assessment_ids    = selectedAssessmentIds;
      }
      const r = await clientApi.post(API.onboarding.approve(userId), payload);
      setActionMsg(r.data?.message ?? "Done.");
      closeApprovalModal();
      closeDrawer();
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Action failed.";
      if (decision === "approve") setModalErr(msg);
      else setActionErr(msg);
    } finally {
      setActing(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remarks, selectedTemplateId, selectedAssessmentIds, approvalDept, approvalDesig, approvalManagerId, approvalCtc, refetch]);

  const results = data?.results ?? [];

  return (
    <>
      {previewDoc && (
        <DocPreviewModal
          name={previewDoc.document_type_display}
          fileName={previewDoc.file_name}
          fileUrl={previewDoc.file_url}
          fileSize={previewDoc.file_size}
          onClose={() => setPreviewDoc(null)}
        />
      )}

      {actionMsg && <div className="alert alert-success" style={{ marginBottom: "1rem" }}>{actionMsg}</div>}
      {actionErr && !selected && <div className="alert alert-error" style={{ marginBottom: "1rem" }}>{actionErr}</div>}

      {loading && <div className="empty-state">Loading…</div>}
      {error   && <div className="alert alert-error">Failed to load approvals.</div>}

      {!loading && !error && results.length === 0 && (
        <div className="empty-state">
          <div className="empty-state-icon">✅</div>
          <div className="empty-state-title">No pending onboarding submissions</div>
          <div className="empty-state-desc">All employees have completed their profiles or none have submitted yet.</div>
        </div>
      )}

      {results.length > 0 && (
        <div className="card">
          <div className="table-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th><th>Email</th><th>Role</th>
                  <th>Branch</th><th>Docs</th><th>Joined</th><th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {results.map(u => (
                  <tr key={u.id}>
                    <td>
                      <div style={{ fontWeight: 600 }}>{u.full_name}</div>
                      {u.employee_id && <div style={{ fontSize: ".78rem", color: "var(--text-muted)" }}>{u.employee_id}</div>}
                    </td>
                    <td>{u.email}</td>
                    <td><span className="status-badge status-active">{u.role_display || "Candidate"}</span></td>
                    <td>{u.branch || "—"}</td>
                    <td>
                      <span style={{ color: u.documents.length >= 2 ? "var(--success)" : "var(--warning)" }}>
                        {u.documents.length} uploaded
                      </span>
                    </td>
                    <td>{new Date(u.date_joined).toLocaleDateString("en-IN")}</td>
                    <td>
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: ".82rem" }}
                        onClick={() => { setSelected(u); setRemarks(""); setActionMsg(null); setActionErr(null); }}
                      >
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {(data?.total_pages ?? 1) > 1 && (
            <div className="pagination">
              <button className="btn btn-ghost" onClick={() => setPage(p => p - 1)} disabled={page <= 1}>← Prev</button>
              <span className="pagination-info">Page {page} of {data?.total_pages}</span>
              <button className="btn btn-ghost" onClick={() => setPage(p => p + 1)} disabled={page >= (data?.total_pages ?? 1)}>Next →</button>
            </div>
          )}
        </div>
      )}

      {/* ── Review drawer ── */}
      {selected && (
        <div className="drawer-overlay open" onClick={closeDrawer}>
          <div className="drawer open" onClick={e => e.stopPropagation()}>
            <div className="drawer-header">
              <span className="drawer-title">Review — {selected.full_name}</span>
              <button className="drawer-close" onClick={closeDrawer}>✕</button>
            </div>

            <div className="drawer-body">
              {actionErr && <div className="alert alert-error" style={{ marginBottom: "1rem" }}>{actionErr}</div>}

              <Section title="Basic Info">
                <Row label="Email"       value={selected.email} />
                <Row label="Phone"       value={selected.phone} />
                <Row label="Department"  value={selected.department} />
                <Row label="Designation" value={selected.designation} />
                <Row label="Branch"      value={selected.branch} />
                <Row label="Role"        value={selected.role_display || "Candidate (no role yet)"} />
              </Section>

              {selected.profile && (
                <>
                  <Section title="Personal">
                    <Row label="DOB"             value={selected.profile.date_of_birth} />
                    <Row label="Gender"          value={selected.profile.gender} />
                    <Row label="Marital Status"  value={selected.profile.marital_status} />
                    <Row label="Father Name"     value={selected.profile.father_name} />
                    <Row label="Blood Group"     value={selected.profile.blood_group} />
                    <Row label="Current Address" value={selected.profile.current_address} />
                  </Section>
                  <Section title="Education & Experience">
                    <Row label="Qualification"    value={selected.profile.highest_qualification} />
                    <Row label="Institution"      value={selected.profile.institution} />
                    <Row label="Year of Passing"  value={selected.profile.year_of_passing?.toString()} />
                    <Row label="Experience (yrs)" value={selected.profile.total_experience_years} />
                    <Row label="Prev Employer"    value={selected.profile.previous_employer} />
                  </Section>
                  <Section title="Bank Details">
                    <Row label="Account Holder" value={selected.profile.account_holder_name} />
                    <Row label="Account No."    value={selected.profile.account_number ? `••••${selected.profile.account_number.slice(-4)}` : undefined} />
                    <Row label="IFSC"           value={selected.profile.ifsc_code} />
                    <Row label="Bank"           value={selected.profile.bank_name} />
                    <Row label="Branch"         value={selected.profile.bank_branch_name} />
                    <Row label="Account Type"   value={selected.profile.account_type} />
                  </Section>
                  <Section title="Emergency Contact">
                    <Row label="Name"         value={selected.profile.emergency_name} />
                    <Row label="Relationship" value={selected.profile.emergency_relationship} />
                    <Row label="Phone"        value={selected.profile.emergency_phone} />
                  </Section>
                </>
              )}

              <Section title={`Documents (${selected.documents.length})`}>
                {selected.documents.length === 0
                  ? <p style={{ color: "var(--text-muted)", fontSize: ".85rem" }}>No documents uploaded.</p>
                  : selected.documents.map(d => (
                    <div key={d.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: ".4rem 0", borderBottom: "1px solid var(--border)", fontSize: ".85rem" }}>
                      <span style={{ fontWeight: 500 }}>{d.document_type_display}</span>
                      <div style={{ display: "flex", alignItems: "center", gap: ".5rem" }}>
                        <span style={{ color: "var(--text-secondary)" }}>{d.file_name}</span>
                        <button className="btn btn-ghost btn-sm" onClick={() => setPreviewDoc(d)} title="Preview">
                          <i className="ti ti-eye" />
                        </button>
                      </div>
                    </div>
                  ))
                }
              </Section>

              <div className="field-group" style={{ marginTop: "1rem" }}>
                <label className="field-label">Remarks (optional)</label>
                <textarea
                  className="field-input"
                  rows={3}
                  value={remarks}
                  onChange={e => setRemarks(e.target.value)}
                  placeholder="Notes for the employee or for record…"
                />
              </div>
            </div>

            <div className="drawer-footer">
              <button
                className="btn btn-ghost"
                style={{ color: "var(--error)", borderColor: "var(--error)" }}
                onClick={() => act(selected.id, "reject")}
                disabled={acting}
              >
                {acting ? "…" : "Send Back for Corrections"}
              </button>
              <button className="btn btn-filled" onClick={openApprovalModal}>
                Approve & Activate ✓
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Approval popup modal ── */}
      {showApprovalModal && selected && (
        <div
          className="modal-overlay open"
          onClick={e => { if (e.target === e.currentTarget) closeApprovalModal(); }}
        >
          <div className="modal modal-lg">
            <div className="modal-header">
              <span className="modal-title">Approve — {selected.full_name}</span>
              <button className="modal-close" onClick={closeApprovalModal}>
                <i className="ti ti-x" />
              </button>
            </div>

            <div className="modal-body">
              {modalErr && (
                <div className="alert alert-error" style={{ marginBottom: "1.25rem" }}>{modalErr}</div>
              )}

              {/* Employment details */}
              <div style={{ marginBottom: "1.5rem" }}>
                <div style={{ fontWeight: 700, fontSize: ".8rem", textTransform: "uppercase", letterSpacing: ".05em", color: "var(--text-muted)", marginBottom: "1rem" }}>
                  Employment Details
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  <div className="field-group">
                    <label className="field-label">
                      Department <span style={{ color: "var(--error)" }}>*</span>
                    </label>
                    {allDepts.length > 0 ? (
                      <select
                        className="field-input field-select"
                        value={approvalDept}
                        onChange={e => setApprovalDept(e.target.value)}
                      >
                        <option value="">— Select —</option>
                        {allDepts.map(d => (
                          <option key={d.id} value={d.name}>{d.name}</option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="field-input"
                        type="text"
                        placeholder="Department name"
                        value={approvalDept}
                        onChange={e => setApprovalDept(e.target.value)}
                      />
                    )}
                  </div>

                  <div className="field-group">
                    <label className="field-label">
                      Designation <span style={{ color: "var(--error)" }}>*</span>
                    </label>
                    <input
                      className="field-input"
                      type="text"
                      placeholder="e.g. Software Engineer"
                      value={approvalDesig}
                      onChange={e => setApprovalDesig(e.target.value)}
                    />
                  </div>

                  <div className="field-group">
                    <label className="field-label">
                      Reporting Manager <span style={{ color: "var(--error)" }}>*</span>
                    </label>
                    {allManagers.length > 0 ? (
                      <select
                        className="field-input field-select"
                        value={approvalManagerId}
                        onChange={e => setApprovalManagerId(e.target.value)}
                      >
                        <option value="">— Select —</option>
                        {allManagers.map(m => (
                          <option key={m.id} value={m.id}>
                            {m.full_name}{m.employee_id ? ` (${m.employee_id})` : ""}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <p style={{ fontSize: ".83rem", color: "var(--text-muted)", marginTop: ".35rem" }}>No active managers found.</p>
                    )}
                  </div>

                  <div className="field-group">
                    <label className="field-label">
                      Annual CTC{" "}
                      <span style={{ color: "var(--text-muted)", fontWeight: 400 }}>(optional)</span>
                    </label>
                    <input
                      className="field-input"
                      type="number"
                      min={0}
                      step={1000}
                      placeholder="e.g. 600000"
                      value={approvalCtc}
                      onChange={e => setApprovalCtc(e.target.value)}
                    />
                    {approvalCtc && (
                      <div style={{ fontSize: ".78rem", color: "var(--text-secondary)", marginTop: ".25rem" }}>
                        Monthly: ₹{Math.round(Number(approvalCtc) / 12).toLocaleString("en-IN")}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Notification settings */}
              <div>
                <div style={{ fontWeight: 700, fontSize: ".8rem", textTransform: "uppercase", letterSpacing: ".05em", color: "var(--text-muted)", marginBottom: "1rem" }}>
                  Notification &amp; Assessment
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
                  <div className="field-group">
                    <label className="field-label">
                      <i className="ti ti-mail mr-4" />Email Template
                    </label>
                    {allTemplates.length === 0 ? (
                      <p style={{ fontSize: ".83rem", color: "var(--text-muted)" }}>No active templates.</p>
                    ) : (
                      <select
                        className="field-input field-select"
                        value={selectedTemplateId}
                        onChange={e => setSelectedTemplateId(e.target.value ? Number(e.target.value) : "")}
                      >
                        <option value="">— No email —</option>
                        {allTemplates.map(t => (
                          <option key={t.id} value={t.id}>{t.display_name || t.name}</option>
                        ))}
                      </select>
                    )}
                  </div>

                  <div className="field-group">
                    <label className="field-label">
                      <i className="ti ti-clipboard-check mr-4" />
                      Assessments{selectedAssessmentIds.length > 0 ? ` (${selectedAssessmentIds.length} selected)` : ""}
                    </label>
                    {allAssessments.length === 0 ? (
                      <p style={{ fontSize: ".83rem", color: "var(--text-muted)" }}>No active assessments.</p>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 160, overflowY: "auto", border: "1px solid var(--outline-v)", borderRadius: 8, padding: 8 }}>
                        {allAssessments.map(a => {
                          const checked = selectedAssessmentIds.includes(a.id);
                          return (
                            <label key={a.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: ".85rem", cursor: "pointer" }}>
                              <input
                                type="checkbox"
                                checked={checked}
                                onChange={() => setSelectedAssessmentIds(prev =>
                                  checked ? prev.filter(id => id !== a.id) : [...prev, a.id]
                                )}
                              />
                              {a.title}{a.is_default ? " (Default)" : ""}
                            </label>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={closeApprovalModal} disabled={acting}>
                Cancel
              </button>
              <button
                className="btn btn-filled"
                onClick={() => act(selected.id, "approve")}
                disabled={acting || !approvalDept || !approvalDesig || !approvalManagerId}
              >
                {acting
                  ? <><i className="ti ti-loader-2 spin" /> Approving…</>
                  : "Confirm Approval ✓"
                }
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

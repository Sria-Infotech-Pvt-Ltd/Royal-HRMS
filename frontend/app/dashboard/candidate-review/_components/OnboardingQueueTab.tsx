"use client";

import { useCallback, useState } from "react";
import clientApi from "@/lib/clientApi";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import DocPreviewModal from "@/components/DocPreviewModal";

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

interface PageData {
  count: number; page: number; total_pages: number;
  results: ApprovalUser[];
}

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

export default function OnboardingQueueTab() {
  const [page,       setPage]       = useState(1);
  const [selected,   setSelected]   = useState<ApprovalUser | null>(null);
  const [remarks,    setRemarks]    = useState("");
  const [acting,     setActing]     = useState(false);
  const [actionMsg,  setActionMsg]  = useState<string | null>(null);
  const [actionErr,  setActionErr]  = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<OnboardingDocument | null>(null);

  const url = `${API.onboarding.approvals}?page=${page}&page_size=20`;
  const { data, loading, error, refetch } = useFetch<PageData>(url);

  const act = useCallback(async (userId: string, decision: "approve" | "reject") => {
    setActing(true); setActionMsg(null); setActionErr(null);
    try {
      const r = await clientApi.post(API.onboarding.approve(userId), { decision, remarks });
      setActionMsg(r.data?.message ?? "Done.");
      setSelected(null);
      setRemarks("");
      refetch();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Action failed.";
      setActionErr(msg);
    } finally {
      setActing(false);
    }
  }, [remarks, refetch]);

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
      {actionErr && <div className="alert alert-error"  style={{ marginBottom: "1rem" }}>{actionErr}</div>}

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

      {selected && (
        <div className="drawer-overlay open" onClick={() => setSelected(null)}>
          <div className="drawer open" onClick={e => e.stopPropagation()}>
            <div className="drawer-header">
              <span className="drawer-title">Review — {selected.full_name}</span>
              <button className="drawer-close" onClick={() => setSelected(null)}>✕</button>
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
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => setPreviewDoc(d)}
                          title="Preview"
                        >
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
              <button
                className="btn btn-filled"
                onClick={() => act(selected.id, "approve")}
                disabled={acting}
              >
                {acting ? "…" : "Approve & Activate ✓"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

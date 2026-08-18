"use client";

import { useEffect, useState } from "react";
import Modal from "@/components/Modal";
import { API } from "@/lib/api/endpoints";
import { buildEmailPreview, CompanyInfo, renderTemplateVars } from "@/lib/emailPreview";
import { Candidate, EmailTemplate, MODE_LABELS, RECRUITMENT_API } from "./_data";
import clientApi from "@/lib/clientApi";

interface Props {
  candidate:    Candidate;
  targetStatus: "selected" | "rejected";
  onClose:      () => void;
  onConfirmed:  (updated: Candidate) => void;
}

export function MarkCandidateModal({ candidate, targetStatus, onClose, onConfirmed }: Props) {
  const isSelect = targetStatus === "selected";

  const [remarks,          setRemarks]          = useState("");
  const [saving,           setSaving]           = useState(false);
  const [apiError,         setApiError]         = useState("");
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [company,          setCompany]          = useState<CompanyInfo | null>(null);
  const [serverContext,    setServerContext]    = useState<Record<string, string>>({});

  // The template is fixed by status — "selected" always sends candidate_selected,
  // "rejected" always sends candidate_rejected. No manual override.
  const defaultSlug = isSelect ? "candidate_selected" : "candidate_rejected";

  // Fetch templates and company info in parallel on open
  useEffect(() => {
    Promise.all([
      clientApi.get<{ data: { results: Record<string, EmailTemplate[]> } }>(API.settings.emailTemplates),
      clientApi.get<{ data: CompanyInfo }>(API.settings.company),
    ])
      .then(([tplRes, coRes]) => {
        const grouped: Record<string, EmailTemplate[]> = tplRes.data?.data?.results ?? {} as Record<string, EmailTemplate[]>;
        const all = Object.values(grouped).flat().filter(t => t.is_active);
        const found = all.find(t => t.name === defaultSlug) ?? null;
        setSelectedTemplate(found);
        if (!found) {
          setApiError(`No active "${defaultSlug}" email template found. Create one in Settings → Email Templates first.`);
        }

        setCompany(coRes.data?.data ?? null);
      })
      .catch(() => setApiError("Could not load templates or company info."))
      .finally(() => setLoadingTemplates(false));
  }, [defaultSlug]);

  // Resolve every real variable the backend knows for this candidate — the
  // source of truth, so any template variable matching a real field
  // auto-fills instead of relying on a hardcoded local list.
  useEffect(() => {
    clientApi
      .post<{ data: { context: Record<string, string> } }>(API.settings.resolveTemplateContext, {
        entity_type: "candidate",
        entity_id:   candidate.id,
      })
      .then(res => setServerContext(res.data?.data?.context ?? {}))
      .catch(() => setServerContext({}));
  }, [candidate.id]);

  function candidateVars(): Record<string, string> {
    const parts      = candidate.name.trim().split(/\s+/);
    const firstName  = parts[0] ?? candidate.name;
    const lastName   = parts.length > 1 ? parts[parts.length - 1] : "";
    const companyName = company?.company_name ?? "[Company]";
    return {
      // Client-side fallback while serverContext is still loading.
      candidate_name:   candidate.name,
      full_name:        candidate.name,
      first_name:       firstName,
      last_name:        lastName,
      email:            candidate.email,
      position_applied:      candidate.position_applied,
      position:              candidate.position_applied,
      branch:                candidate.branch_name ?? "",
      branch_name:           candidate.branch_name ?? "",
      interview_date:        candidate.interview_date ?? "",
      interview_mode:        candidate.interview_mode ?? "",
      interview_mode_display: MODE_LABELS[candidate.interview_mode] ?? candidate.interview_mode ?? "",
      company_name:     companyName,
      FULL_NAME:        candidate.name,
      FNAME:            firstName,
      LNAME:            lastName,
      EMAIL:            candidate.email,
      POSITION:         candidate.position_applied,
      COMPANY:          companyName,
      // Server-resolved values win — they're the source of truth.
      ...serverContext,
    };
  }

  function previewSubject(): string {
    if (!selectedTemplate) return "";
    return renderTemplateVars(selectedTemplate.subject, candidateVars());
  }

  function previewHtml(): string {
    if (!selectedTemplate) return "";
    const body = renderTemplateVars(selectedTemplate.body, candidateVars());
    return buildEmailPreview(body, company);
  }

  async function handleConfirm() {
    setSaving(true);
    setApiError("");
    try {
      // CandidateStatusView.patch already sends the candidate_selected/candidate_rejected
      // email as a side effect of the status change — a separate sendEmail() call here
      // used to fire a second, duplicate copy of the same email to the candidate.
      const res = await RECRUITMENT_API.setStatus(candidate.id, {
        status:  targetStatus,
        remarks,
      });

      onConfirmed(res.data.data);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiError(msg || "Action failed.");
    } finally {
      setSaving(false);
    }
  }

  const vars = candidateVars();
  const hasManualVars = (selectedTemplate?.available_variables ?? [])
    .some(v => vars[v] === undefined && vars[v.toUpperCase()] === undefined && vars[v.toLowerCase()] === undefined);

  return (
    <Modal
      title={<>{isSelect ? "Select" : "Reject"} Candidate — {candidate.name}</>}
      onClose={onClose}
      maxWidth={640}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className={`btn ${isSelect ? "btn-success" : "btn-danger"}`}
            onClick={handleConfirm}
            disabled={saving || loadingTemplates || !selectedTemplate}
          >
            {saving
              ? <><i className="ti ti-loader-2 spin" /> Sending…</>
              : <><i className={`ti ${isSelect ? "ti-check" : "ti-x"}`} /> Confirm & Send Email</>
            }
          </button>
        </>
      }
    >
      {apiError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /><div>{apiError}</div>
        </div>
      )}

      <div className={`alert ${isSelect ? "alert-success" : "alert-error"} mb-16`}>
        <i className={`ti ${isSelect ? "ti-check" : "ti-x"}`} />
        <div>
          You are marking <strong>{candidate.name}</strong> as <strong>{targetStatus}</strong>.
          An email will be sent using the selected template below.
        </div>
      </div>

      {/* Email template — fixed by status, not manually chosen */}
      <div className="field-group mb-16">
        <label className="field-label">Email Template</label>
        {loadingTemplates ? (
          <div className="text-sm text-[var(--on-variant)]">
            <i className="ti ti-loader-2 spin" /> Loading…
          </div>
        ) : selectedTemplate ? (
          <div
            className="field-input"
            style={{ display: "flex", alignItems: "center", gap: 8, background: "var(--bg-low)", cursor: "not-allowed" }}
            title="This template is fixed for this status and cannot be changed here"
          >
            <i className="ti ti-lock" style={{ color: "var(--on-variant)", fontSize: 14 }} />
            {selectedTemplate.display_name}
          </div>
        ) : null}
      </div>

      {/* Remarks */}
      <div className="field-group mb-16">
        <label className="field-label">Interview feedback / remarks</label>
        <textarea
          className="field-input"
          rows={2}
          placeholder="Add interview notes…"
          value={remarks}
          onChange={e => setRemarks(e.target.value)}
        />
      </div>

      {/* Full email preview with company branding */}
      {selectedTemplate && (
        <div className="settings-card">
          <div className="settings-card-title flex items-center gap-2 mb-8">
            <i className="ti ti-mail" /> Email Preview
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 2 }}>
            <strong>To:</strong> {candidate.email}
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 10 }}>
            <strong>Subject:</strong> {previewSubject()}
          </div>
          <iframe
            srcDoc={previewHtml()}
            sandbox="allow-same-origin"
            style={{
              width: "100%",
              height: 340,
              border: "1px solid var(--outline-v)",
              borderRadius: 6,
              display: "block",
            }}
            title="Email body preview"
          />
          {hasManualVars && (
            <div className="alert alert-warn mt-8" style={{ padding: "6px 10px", fontSize: 12 }}>
              <i className="ti ti-alert-triangle" />
              <div>This template has extra variables that will be sent unfilled.</div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

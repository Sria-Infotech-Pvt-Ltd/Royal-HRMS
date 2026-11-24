"use client";

import { useEffect, useState } from "react";
import Modal from "@/components/Modal";
import { API } from "@/lib/api/endpoints";
import { buildEmailPreview, CompanyInfo, renderTemplateVars } from "@/lib/emailPreview";
import { Candidate, EmailTemplate, MODE_LABELS, RECRUITMENT_API } from "./_data";
import clientApi from "@/lib/clientApi";
import { useT } from "@/hooks/useI18n";

interface Props {
  candidate:    Candidate;
  targetStatus: "selected" | "rejected";
  onClose:      () => void;
  onConfirmed:  (updated: Candidate) => void;
}

export function MarkCandidateModal({ candidate, targetStatus, onClose, onConfirmed }: Props) {
  const t = useT();
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
        const all = Object.values(grouped).flat().filter(template => template.is_active);
        const found = all.find(template => template.name === defaultSlug) ?? null;
        setSelectedTemplate(found);
        if (!found) {
          setApiError(t("No active \"{slug}\" email template found. Create one in Settings → Email Templates first.", { slug: defaultSlug }));
        }

        setCompany(coRes.data?.data ?? null);
      })
      .catch(() => setApiError(t("Could not load templates or company info.")))
      .finally(() => setLoadingTemplates(false));
  }, [defaultSlug, t]);

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
      setApiError(msg || t("Action failed."));
    } finally {
      setSaving(false);
    }
  }

  const vars = candidateVars();
  const hasManualVars = (selectedTemplate?.available_variables ?? [])
    .some(v => vars[v] === undefined && vars[v.toUpperCase()] === undefined && vars[v.toLowerCase()] === undefined);

  return (
    <Modal
      title={isSelect ? t("Select Candidate — {name}", { name: candidate.name }) : t("Reject Candidate — {name}", { name: candidate.name })}
      onClose={onClose}
      maxWidth={640}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>{t("Cancel")}</button>
          <button
            className={`btn ${isSelect ? "btn-success" : "btn-danger"}`}
            onClick={handleConfirm}
            disabled={saving || loadingTemplates || !selectedTemplate}
          >
            {saving
              ? <><i className="ti ti-loader-2 spin" /> {t("Sending…")}</>
              : <><i className={`ti ${isSelect ? "ti-check" : "ti-x"}`} /> {t("Confirm & Send Email")}</>
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
          {t("You are marking")} <strong>{candidate.name}</strong> {t("as")} <strong>{isSelect ? t("selected") : t("rejected")}</strong>.{" "}
          {t("An email will be sent using the selected template below.")}
        </div>
      </div>

      {/* Email template — fixed by status, not manually chosen */}
      <div className="field-group mb-16">
        <label className="field-label">{t("Email Template")}</label>
        {loadingTemplates ? (
          <div className="text-sm text-[var(--on-variant)]">
            <i className="ti ti-loader-2 spin" /> {t("Loading…")}
          </div>
        ) : selectedTemplate ? (
          <div
            className="field-input"
            style={{ display: "flex", alignItems: "center", gap: 8, background: "var(--bg-low)", cursor: "not-allowed" }}
            title={t("This template is fixed for this status and cannot be changed here")}
          >
            <i className="ti ti-lock" style={{ color: "var(--on-variant)", fontSize: 14 }} />
            {selectedTemplate.display_name}
          </div>
        ) : null}
      </div>

      {/* Remarks */}
      <div className="field-group mb-16">
        <label className="field-label">{t("Interview feedback / remarks")}</label>
        <textarea
          className="field-input"
          rows={2}
          placeholder={t("Add interview notes…")}
          value={remarks}
          onChange={e => setRemarks(e.target.value)}
        />
      </div>

      {/* Full email preview with company branding */}
      {selectedTemplate && (
        <div className="settings-card">
          <div className="settings-card-title flex items-center gap-2 mb-8">
            <i className="ti ti-mail" /> {t("Email Preview")}
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 2 }}>
            <strong>{t("To:")}</strong> {candidate.email}
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 10 }}>
            <strong>{t("Subject:")}</strong> {previewSubject()}
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
            title={t("Email body preview")}
          />
          {hasManualVars && (
            <div className="alert alert-warn mt-8" style={{ padding: "6px 10px", fontSize: 12 }}>
              <i className="ti ti-alert-triangle" />
              <div>{t("This template has extra variables that will be sent unfilled.")}</div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

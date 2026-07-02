"use client";

import { useEffect, useState } from "react";
import { API } from "@/lib/api/endpoints";
import { buildEmailPreview, CompanyInfo, renderTemplateVars } from "@/lib/emailPreview";
import { Candidate, EmailTemplate, RECRUITMENT_API } from "./_data";
import clientApi from "@/lib/clientApi";

interface Props {
  candidate:    Candidate;
  targetStatus: "selected" | "rejected";
  onClose:      () => void;
  onConfirmed:  (updated: Candidate) => void;
}

const AUTO_KEYS = new Set(["FULL_NAME", "FNAME", "LNAME", "EMAIL", "POSITION", "COMPANY"]);

export function MarkCandidateModal({ candidate, targetStatus, onClose, onConfirmed }: Props) {
  const isSelect = targetStatus === "selected";

  const [remarks,          setRemarks]          = useState("");
  const [saving,           setSaving]           = useState(false);
  const [apiError,         setApiError]         = useState("");
  const [templateGroups,   setTemplateGroups]   = useState<{ category: string; templates: EmailTemplate[] }[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [company,          setCompany]          = useState<CompanyInfo | null>(null);

  // Fetch templates and company info in parallel on open
  useEffect(() => {
    Promise.all([
      clientApi.get<{ data: { results: Record<string, EmailTemplate[]> } }>(API.settings.emailTemplates),
      clientApi.get<{ data: CompanyInfo }>(API.settings.company),
    ])
      .then(([tplRes, coRes]) => {
        const grouped: Record<string, EmailTemplate[]> = tplRes.data?.data?.results ?? {} as Record<string, EmailTemplate[]>;
        const groups = Object.entries(grouped)
          .map(([category, items]) => ({
            category,
            templates: items.filter(t => t.is_active),
          }))
          .filter(g => g.templates.length > 0);
        setTemplateGroups(groups);

        const all = groups.flatMap(g => g.templates);
        const defaultSlug = isSelect ? "candidate_selected" : "candidate_rejected";
        const preferred   = all.find(t => t.name === defaultSlug) ?? all[0] ?? null;
        setSelectedTemplate(preferred);

        setCompany(coRes.data?.data ?? null);
      })
      .catch(() => setApiError("Could not load templates or company info."))
      .finally(() => setLoadingTemplates(false));
  }, [isSelect]);

  function previewVars(): Record<string, string> {
    const parts = candidate.name.trim().split(/\s+/);
    return {
      FULL_NAME: candidate.name,
      FNAME:     parts[0] ?? candidate.name,
      LNAME:     parts.length > 1 ? parts[parts.length - 1] : "",
      EMAIL:     candidate.email,
      POSITION:  candidate.position_applied,
      COMPANY:   company?.company_name ?? "[Company]",
    };
  }

  function previewSubject(): string {
    if (!selectedTemplate) return "";
    return renderTemplateVars(selectedTemplate.subject, previewVars());
  }

  function previewHtml(): string {
    if (!selectedTemplate) return "";
    const body = renderTemplateVars(selectedTemplate.body, previewVars());
    return buildEmailPreview(body, company);
  }

  async function handleConfirm() {
    setSaving(true);
    setApiError("");
    try {
      const res = await RECRUITMENT_API.setStatus(candidate.id, {
        status:        targetStatus,
        remarks,
        template_name: selectedTemplate?.name,
      });
      onConfirmed(res.data.data);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiError(msg || "Action failed.");
    } finally {
      setSaving(false);
    }
  }

  const hasManualVars = (selectedTemplate?.available_variables ?? [])
    .some(v => !AUTO_KEYS.has(v.toUpperCase()));

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: 640 }}>
        <div className="modal-header">
          <div className="modal-title">
            {isSelect ? "Select" : "Reject"} Candidate — {candidate.name}
          </div>
          <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="modal-body">
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

          {/* Template picker */}
          <div className="field-group mb-16">
            <label className="field-label">Email Template *</label>
            {loadingTemplates ? (
              <div className="text-sm text-[var(--on-variant)]">
                <i className="ti ti-loader-2 spin" /> Loading…
              </div>
            ) : (
              <select
                className="field-input field-select"
                value={selectedTemplate?.name ?? ""}
                onChange={e => {
                  const found = templateGroups
                    .flatMap(g => g.templates)
                    .find(t => t.name === e.target.value) ?? null;
                  setSelectedTemplate(found);
                }}
              >
                {templateGroups.length === 0 && (
                  <option value="">No active templates — create one in Settings → Email Templates</option>
                )}
                {templateGroups.map(g => (
                  <optgroup
                    key={g.category}
                    label={g.category.charAt(0).toUpperCase() + g.category.slice(1)}
                  >
                    {g.templates.map(t => (
                      <option key={t.name} value={t.name}>{t.display_name}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            )}
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
        </div>

        <div className="modal-footer">
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
        </div>
      </div>
    </div>
  );
}

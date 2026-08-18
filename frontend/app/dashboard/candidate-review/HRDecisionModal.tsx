"use client";

import { useEffect, useState } from "react";
import { API } from "@/lib/api/endpoints";
import { buildEmailPreview, CompanyInfo, renderTemplateVars } from "@/lib/emailPreview";
import { Candidate, EmailTemplate, RECRUITMENT_API } from "../interview-list/_data";
import clientApi from "@/lib/clientApi";
import Modal from "@/components/Modal";

interface Props {
  candidate: Candidate;
  decision:  "approve" | "reject";
  onClose:   () => void;
  onDone:    (updated: Candidate) => void;
}

export function HRDecisionModal({ candidate, decision, onClose, onDone }: Props) {
  const isApprove = decision === "approve";

  const [remarks,          setRemarks]          = useState("");
  const [saving,           setSaving]           = useState(false);
  const [apiError,         setApiError]         = useState("");
  const [templateGroups,   setTemplateGroups]   = useState<{ category: string; templates: EmailTemplate[] }[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [extraVars,        setExtraVars]        = useState<Record<string, string>>({});
  const [company,          setCompany]          = useState<CompanyInfo | null>(null);
  const [serverContext,    setServerContext]    = useState<Record<string, string>>({});

  // Load templates + company info for both approve and reject
  useEffect(() => {
    setLoadingTemplates(true);
    Promise.all([
      RECRUITMENT_API.emailTemplates(),
      clientApi.get<{ data: CompanyInfo }>(API.settings.company),
    ])
      .then(([tplRes, coRes]) => {
        const grouped: Record<string, EmailTemplate[]> = tplRes.data?.data?.results ?? {} as Record<string, EmailTemplate[]>;
        // Restrict to categories actually meant for a candidate decision —
        // showing every category let people pick e.g. "Pay Slip" or a leave
        // template here, whose variables can never resolve for a candidate.
        const RELEVANT_CATEGORIES = new Set(["recruitment", "onboarding"]);
        const groups = Object.entries(grouped)
          .filter(([category]) => RELEVANT_CATEGORIES.has(category))
          .map(([category, items]) => ({ category, templates: items.filter(t => t.is_active) }))
          .filter(g => g.templates.length > 0);
        setTemplateGroups(groups);

        const all = groups.flatMap(g => g.templates);
        const preferred = isApprove
          ? (all.find(t => t.name === "assessment_invitation") ??
             all.find(t => t.name === "onboarding_approved")   ??
             all[0] ?? null)
          : (all.find(t => t.name === "onboarding_rejected")   ??
             all.find(t => t.name === "revision_request")      ??
             all[0] ?? null);
        setSelectedTemplate(preferred);
        setCompany(coRes.data?.data ?? null);
      })
      .catch(() => setApiError("Could not load email templates."))
      .finally(() => setLoadingTemplates(false));
  }, [isApprove]);

  // Resolve every real variable the backend knows for this candidate — the
  // source of truth, so any template variable matching a real field
  // auto-fills instead of needing this modal to know about it in advance.
  useEffect(() => {
    clientApi
      .post<{ data: { context: Record<string, string> } }>(API.settings.resolveTemplateContext, {
        entity_type: "candidate",
        entity_id:   candidate.id,
      })
      .then(res => setServerContext(res.data?.data?.context ?? {}))
      .catch(() => setServerContext({}));
  }, [candidate.id]);

  // Reset manual variable inputs when template changes — only variables NOT
  // resolvable from serverContext (case-insensitively) become manual fields.
  useEffect(() => {
    if (!selectedTemplate) { setExtraVars({}); return; }
    const manual: Record<string, string> = {};
    for (const v of (selectedTemplate.available_variables ?? [])) {
      const resolved = serverContext[v] ?? serverContext[v.toUpperCase()] ?? serverContext[v.toLowerCase()];
      if (resolved === undefined) manual[v] = "";
    }
    setExtraVars(manual);
  }, [selectedTemplate, serverContext]);

  function previewVars(): Record<string, string> {
    const parts = candidate.name.trim().split(/\s+/);
    return {
      // Client-side fallback while serverContext is still loading.
      FULL_NAME: candidate.name,
      FNAME:     parts[0] ?? candidate.name,
      LNAME:     parts.length > 1 ? parts[parts.length - 1] : "",
      EMAIL:     candidate.email,
      POSITION:  candidate.position_applied,
      COMPANY:   company?.company_name ?? "[Company]",
      ...serverContext,
      ...extraVars,
    };
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
      const body: {
        decision:       "approve" | "reject";
        remarks?:       string;
        template_name?: string;
        extra_context?: Record<string, string>;
      } = { decision, remarks };

      if (selectedTemplate) {
        body.template_name = selectedTemplate.name;
        // Send the full resolved context, not just the manually-typed
        // leftovers — otherwise the preview looks right but the actual
        // email (built server-side from a much smaller base context) would
        // still be missing everything auto-filled from serverContext.
        body.extra_context = { ...serverContext, ...extraVars };
      }

      const res = await RECRUITMENT_API.hrDecision(candidate.id, body);
      onDone(res.data.data);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiError(msg || "Action failed.");
    } finally {
      setSaving(false);
    }
  }

  const hasUnfilledVars = Object.values(extraVars).some(v => !v.trim());

  return (
    <Modal
      title={<>{isApprove ? "Approve & Send Assessment Invite" : "Request Revision"} — {candidate.name}</>}
      onClose={onClose}
      maxWidth={700}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button
            className={`btn ${isApprove ? "btn-success" : "btn-danger"}`}
            onClick={handleConfirm}
            disabled={
              saving ||
              loadingTemplates ||
              !selectedTemplate ||
              (!isApprove && !remarks.trim()) ||
              hasUnfilledVars
            }
          >
            {saving ? (
              <><i className="ti ti-loader-2 spin" /> Processing…</>
            ) : (
              <><i className={`ti ${isApprove ? "ti-check" : "ti-alert-triangle"}`} /> Confirm & Send Email</>
            )}
          </button>
        </>
      }
    >
          {apiError && (
            <div className="alert alert-error mb-16">
              <i className="ti ti-alert-circle" /><div>{apiError}</div>
            </div>
          )}

          {/* Status alert */}
          <div className={`alert ${isApprove ? "alert-success" : "alert-warn"} mb-16`}>
            <i className={`ti ${isApprove ? "ti-check" : "ti-alert-triangle"}`} />
            <div>
              You are <strong>{isApprove ? "approving" : "requesting revision for"}</strong>{" "}
              <strong>{candidate.name}</strong>.
              An email will be sent using the selected template below.
            </div>
          </div>

          {/* Template picker */}
          <div className="field-group mb-16">
            <label className="field-label">Email Template *</label>
            {loadingTemplates ? (
              <div className="text-sm text-[var(--on-variant)]">
                <i className="ti ti-loader-2 spin" /> Loading templates…
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

          {/* Manual inputs for non-auto variables */}
          {Object.keys(extraVars).length > 0 && (
            <div className="settings-card mb-16">
              <div className="settings-card-title mb-8">Fill in template variables</div>
              <div className="form-row cols-2">
                {Object.keys(extraVars).map(key => (
                  <div key={key} className="field-group">
                    <label className="field-label">
                      {key.replace(/_/g, " ")} <span style={{ color: "var(--error)" }}>*</span>
                    </label>
                    <input
                      className="field-input"
                      placeholder={`Enter ${key.replace(/_/g, " ")}`}
                      value={extraVars[key]}
                      onChange={e => setExtraVars(prev => ({ ...prev, [key]: e.target.value }))}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Remarks */}
          <div className="field-group mb-16">
            <label className="field-label">
              {isApprove ? "HR Remarks (optional)" : "Revision notes (required)"}
            </label>
            <textarea
              className="field-input"
              rows={2}
              placeholder={isApprove ? "Any onboarding notes…" : "Specify what needs to be corrected…"}
              value={remarks}
              onChange={e => setRemarks(e.target.value)}
              style={{ resize: "vertical" }}
            />
          </div>

          {/* Email preview */}
          {selectedTemplate && (
            <div className="settings-card">
              <div className="settings-card-title flex items-center gap-2 mb-8">
                <i className="ti ti-mail" /> Email Preview
              </div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 2 }}>
                <strong>To:</strong> {candidate.email}
              </div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 10 }}>
                <strong>Subject:</strong>{" "}
                {renderTemplateVars(selectedTemplate.subject, previewVars())}
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
            </div>
          )}
    </Modal>
  );
}

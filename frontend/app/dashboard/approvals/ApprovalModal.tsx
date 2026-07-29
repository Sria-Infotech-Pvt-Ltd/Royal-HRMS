"use client";

import { useEffect, useMemo, useState } from "react";
import { API } from "@/lib/api/endpoints";
import { buildEmailPreview, CompanyInfo, renderTemplateVars } from "@/lib/emailPreview";
import { EmailTemplate, RECRUITMENT_API } from "../interview-list/_data";
import clientApi from "@/lib/clientApi";
import { useCurrentUser } from "@/hooks/useCurrentUser";

interface Props {
  action:        "approve" | "reject";
  itemLabel:     string;
  employeeName:  string;
  employeeEmail?: string;
  kind?:         "leave" | "expense";
  /** The LeaveRequest id / expense_number this modal is acting on — passed
   *  through to the backend so it can resolve every real template variable
   *  for this specific record (see lib/api/endpoints.ts settings.resolveTemplateContext). */
  entityId?:     string | number;
  autoVars?:     Record<string, string>;
  onConfirm:     (remarks: string, templateName?: string, extraContext?: Record<string, string>) => void;
  onClose:       () => void;
  saving:        boolean;
}

export function ApprovalModal({
  action, itemLabel, employeeName, employeeEmail, kind, entityId, autoVars, onConfirm, onClose, saving,
}: Props) {
  const isApprove  = action === "approve";
  const currentUser = useCurrentUser();

  const [remarks,          setRemarks]          = useState("");
  const [templateGroups,   setTemplateGroups]   = useState<{ category: string; templates: EmailTemplate[] }[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<EmailTemplate | null>(null);
  const [extraVars,        setExtraVars]        = useState<Record<string, string>>({});
  const [company,          setCompany]          = useState<CompanyInfo | null>(null);
  const [templateErr,      setTemplateErr]      = useState("");
  const [serverContext,    setServerContext]    = useState<Record<string, string>>({});

  // Resolve every real variable the backend knows for this record (leave
  // request / expense) — the single source of truth, so any template
  // variable matching a real field auto-fills without needing this modal
  // to know about it in advance.
  useEffect(() => {
    if (!isApprove || !entityId || !kind) return;
    clientApi
      .post<{ data: { context: Record<string, string> } }>(API.settings.resolveTemplateContext, {
        entity_type: kind === "leave" ? "leave_request" : "expense",
        entity_id:   entityId,
      })
      .then(res => setServerContext(res.data?.data?.context ?? {}))
      .catch(() => setServerContext({}));
  }, [isApprove, entityId, kind]);

  // Full context of all auto-derivable variables (both cases). Server-resolved
  // values win where they overlap — they're the source of truth; the
  // hardcoded fallbacks below only cover things the server can't know
  // (who's approving right now) or fill in before the request resolves.
  const autoContext = useMemo<Record<string, string>>(() => {
    const parts        = employeeName.trim().split(/\s+/);
    const fname        = parts[0] ?? employeeName;
    const lname        = parts.length > 1 ? parts[parts.length - 1] : "";
    const companyName  = company?.company_name ?? "";
    const approverName = currentUser?.name ?? "";
    const approverRole = (currentUser?.role ?? "").replace(/_/g, " ");

    const ctx: Record<string, string> = {
      // Name — all common aliases in both cases
      FULL_NAME: employeeName,     full_name: employeeName,
      EMPLOYEE_NAME: employeeName, employee_name: employeeName,
      FNAME: fname,                fname: fname,
      LNAME: lname,                lname: lname,
      // Contact
      EMAIL: employeeEmail ?? "",  email: employeeEmail ?? "",
      // Company
      COMPANY: companyName, COMPANY_NAME: companyName, company_name: companyName, company: companyName,
      // Approver
      APPROVER_NAME: approverName, approver_name: approverName,
      APPROVER_ROLE: approverRole, approver_role: approverRole,
    };

    // Merge request-specific autoVars in all three casings
    for (const [k, v] of Object.entries(autoVars ?? {})) {
      ctx[k]               = v;
      ctx[k.toUpperCase()] = v;
      ctx[k.toLowerCase()] = v;
    }

    // Server-resolved values take priority — they're computed from the
    // actual record, not guessed client-side.
    return { ...ctx, ...serverContext };
  }, [employeeName, employeeEmail, company, currentUser, autoVars, serverContext]);

  useEffect(() => {
    if (!isApprove) return;
    setLoadingTemplates(true);
    setTemplateErr("");
    Promise.all([
      RECRUITMENT_API.emailTemplates(),
      clientApi.get<{ data: CompanyInfo }>(API.settings.company),
    ])
      .then(([tplRes, coRes]) => {
        const grouped: Record<string, EmailTemplate[]> = tplRes.data?.data?.results ?? {} as Record<string, EmailTemplate[]>;
        // Restrict to templates actually meant for this record type (naming
        // convention: "leave_*" / "expense_*") — showing every template
        // regardless of category let people pick e.g. "Pay Slip" or "Leave
        // Request Approved" while approving an expense, whose variables
        // (MONTH/YEAR, leave_type/start_date/...) can never resolve for an
        // expense record no matter how much context this modal has.
        const isRelevant = (t: EmailTemplate) => !kind || t.name.startsWith(`${kind}_`);
        const groups = Object.entries(grouped)
          .map(([category, items]) => ({ category, templates: items.filter(t => t.is_active && isRelevant(t)) }))
          .filter(g => g.templates.length > 0);
        setTemplateGroups(groups);
        setSelectedTemplate(_pickDefaultTemplate(groups, kind, action));
        setCompany(coRes.data?.data ?? null);
      })
      .catch(() => setTemplateErr("Could not load email templates."))
      .finally(() => setLoadingTemplates(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isApprove]);

  // Pre-fill extraVars from autoContext; only variables NOT resolvable from context become manual fields.
  useEffect(() => {
    if (!selectedTemplate) { setExtraVars({}); return; }
    const manual: Record<string, string> = {};
    for (const v of (selectedTemplate.available_variables ?? [])) {
      const resolved = autoContext[v] ?? autoContext[v.toUpperCase()] ?? autoContext[v.toLowerCase()];
      if (resolved === undefined) {
        manual[v] = "";
      }
    }
    setExtraVars(manual);
  }, [selectedTemplate, autoContext]);

  function previewVars(): Record<string, string> {
    return { ...autoContext, ...extraVars };
  }

  function previewHtml(): string {
    if (!selectedTemplate) return "";
    return buildEmailPreview(renderTemplateVars(selectedTemplate.body, previewVars()), company);
  }

  const hasUnfilledVars = Object.values(extraVars).some(v => !v.trim());

  function handleConfirm() {
    if (isApprove) {
      onConfirm(remarks, selectedTemplate?.name, { ...autoContext, ...extraVars });
    } else {
      onConfirm(remarks);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={{ maxWidth: isApprove ? 700 : 480 }}>
        <div className="modal-header">
          <div className="modal-title">
            {isApprove ? "Approve" : "Reject"} — {itemLabel}
          </div>
          <button className="modal-close" suppressHydrationWarning onClick={onClose}>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          {templateErr && (
            <div className="alert alert-error mb-16">
              <i className="ti ti-alert-circle" /><div>{templateErr}</div>
            </div>
          )}

          {/* ── Approve: template selection + preview ── */}
          {isApprove && (
            <>
              <div className="field-group mb-16">
                <label className="field-label">Notification Email Template</label>
                {loadingTemplates ? (
                  <div style={{ fontSize: 13, color: "var(--on-variant)" }}>
                    <i className="ti ti-loader-2 spin" /> Loading templates…
                  </div>
                ) : (
                  <select
                    className="field-input field-select"
                    value={selectedTemplate?.name ?? ""}
                    onChange={e => {
                      const found = templateGroups.flatMap(g => g.templates).find(t => t.name === e.target.value) ?? null;
                      setSelectedTemplate(found);
                    }}
                  >
                    <option value="">— No email —</option>
                    {templateGroups.map(g => (
                      <optgroup key={g.category} label={g.category.charAt(0).toUpperCase() + g.category.slice(1)}>
                        {g.templates.map(t => (
                          <option key={t.name} value={t.name}>{t.display_name}</option>
                        ))}
                      </optgroup>
                    ))}
                  </select>
                )}
              </div>

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

              {selectedTemplate && (
                <div className="settings-card mb-16">
                  <div className="settings-card-title mb-8">
                    <i className="ti ti-mail" /> Email Preview
                  </div>
                  <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 2 }}>
                    <strong>To:</strong> {employeeEmail ?? employeeName}
                  </div>
                  <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 10 }}>
                    <strong>Subject:</strong>{" "}
                    {renderTemplateVars(selectedTemplate.subject, previewVars())}
                  </div>
                  <iframe
                    srcDoc={previewHtml()}
                    sandbox="allow-same-origin"
                    style={{ width: "100%", height: 320, border: "1px solid var(--outline-v)", borderRadius: 6, display: "block" }}
                    title="Email preview"
                  />
                </div>
              )}
            </>
          )}

          {/* ── Reject: confirmation alert ── */}
          {!isApprove && (
            <div className="alert alert-warn mb-16">
              <i className="ti ti-alert-triangle" />
              <div>This request will be rejected. The employee will be notified.</div>
            </div>
          )}

          <div className="field-group">
            <label className="field-label">
              Remarks {!isApprove && <span style={{ color: "var(--error)" }}>*</span>}
            </label>
            <textarea
              className="field-input"
              rows={3}
              placeholder={isApprove ? "Optional notes for the record…" : "Reason for rejection (required)"}
              value={remarks}
              onChange={e => setRemarks(e.target.value)}
              style={{ resize: "vertical" }}
            />
          </div>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" suppressHydrationWarning onClick={onClose} disabled={saving}>
            Cancel
          </button>
          <button
            className={`btn ${isApprove ? "btn-success" : "btn-danger"}`}
            suppressHydrationWarning
            disabled={saving || (!isApprove && !remarks.trim()) || (isApprove && hasUnfilledVars)}
            onClick={handleConfirm}
          >
            {saving ? (
              <><i className="ti ti-loader-2 spin" /> Saving…</>
            ) : isApprove ? (
              <><i className="ti ti-check" /> {selectedTemplate ? "Approve & Send Email" : "Approve"}</>
            ) : (
              <><i className="ti ti-x" /> Reject</>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

function _pickDefaultTemplate(
  groups: { category: string; templates: EmailTemplate[] }[],
  kind: "leave" | "expense" | undefined,
  action: "approve" | "reject",
): EmailTemplate | null {
  const all = groups.flatMap(g => g.templates);
  if (!kind) return all[0] ?? null;

  const actionWords = action === "approve"
    ? ["approv", "grant", "accept"]
    : ["reject", "decline", "deny"];

  const kindGroups   = groups.filter(g => g.category.toLowerCase().includes(kind));
  const kindAll      = kindGroups.flatMap(g => g.templates);

  const exact = kindAll.find(t =>
    actionWords.some(w => t.name.toLowerCase().includes(w) || t.display_name.toLowerCase().includes(w))
  );
  if (exact) return exact;
  if (kindAll.length > 0) return kindAll[0];

  const byName = all.find(t =>
    t.name.toLowerCase().includes(kind) || t.display_name.toLowerCase().includes(kind)
  );
  return byName ?? all[0] ?? null;
}

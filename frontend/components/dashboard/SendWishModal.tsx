"use client";

import { useEffect, useState } from "react";
import { useT } from "@/hooks/useI18n";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { buildEmailPreview, CompanyInfo, normalizeExtraContext, renderTemplateVars } from "@/lib/emailPreview";
import Modal from "@/components/Modal";

interface WishTemplate {
  name:         string;
  display_name: string;
  subject:      string;
  body:         string;
  is_active:    boolean;
}

interface TemplateGroup {
  category:  string;
  templates: WishTemplate[];
}

export interface SendWishTarget {
  employeeId:   string;
  employeeName: string;
  employeeEmail?: string;
  department?:   string;
  designation?:  string;
  /** Keyword used to pre-select a matching template (e.g. "birthday", "anniversary") */
  preferredKey?: string;
}

interface Props extends SendWishTarget {
  onClose: () => void;
  onSent:  () => void;
}

export function SendWishModal({
  employeeId, employeeName, employeeEmail,
  department, designation, preferredKey,
  onClose, onSent,
}: Props) {
  const t = useT();
  const [templateGroups,   setTemplateGroups]   = useState<TemplateGroup[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<WishTemplate | null>(null);
  const [company,          setCompany]          = useState<CompanyInfo | null>(null);
  const [saving,           setSaving]           = useState(false);
  const [apiError,         setApiError]         = useState("");

  useEffect(() => {
    Promise.all([
      clientApi.get<{ data: { results: Record<string, WishTemplate[]> } }>(API.settings.emailTemplates),
      clientApi.get<{ data: CompanyInfo }>(API.settings.company),
    ])
      .then(([tplRes, coRes]) => {
        const grouped = tplRes.data?.data?.results ?? {};
        const groups: TemplateGroup[] = Object.entries(grouped)
          .map(([category, items]) => ({
            category,
            templates: (items as WishTemplate[]).filter(template => template.is_active),
          }))
          .filter(g => g.templates.length > 0);
        setTemplateGroups(groups);

        const all = groups.flatMap(g => g.templates);
        const preferred = preferredKey
          ? (all.find(template => template.name.includes(preferredKey)) ?? all[0] ?? null)
          : (all[0] ?? null);
        setSelectedTemplate(preferred);
        setCompany(coRes.data?.data ?? null);
      })
      .catch(() => setApiError(t("Could not load templates or company info.")))
      .finally(() => setLoadingTemplates(false));
  }, [preferredKey, t]);

  function employeeVars(): Record<string, string> {
    const parts       = employeeName.trim().split(/\s+/);
    const firstName   = parts[0] ?? employeeName;
    const lastName    = parts.length > 1 ? parts[parts.length - 1] : "";
    const companyName = company?.company_name ?? "[Company]";
    return {
      // All common aliases the backend template might use
      employee_name:  employeeName,
      full_name:      employeeName,
      name:           employeeName,
      recipient_name: employeeName,
      first_name:     firstName,
      last_name:      lastName,
      fname:          firstName,
      lname:          lastName,
      email:          employeeEmail ?? "",
      department:     department   ?? "",
      designation:    designation  ?? "",
      company_name:   companyName,
      company:        companyName,
      // Uppercase variants (some templates use these)
      EMPLOYEE_NAME:  employeeName,
      FULL_NAME:      employeeName,
      FIRST_NAME:     firstName,
      LAST_NAME:      lastName,
      EMAIL:          employeeEmail ?? "",
      COMPANY:        companyName,
      COMPANY_NAME:   companyName,
    };
  }

  function previewSubject(): string {
    if (!selectedTemplate) return "";
    return renderTemplateVars(selectedTemplate.subject, employeeVars());
  }

  function previewHtml(): string {
    if (!selectedTemplate) return "";
    return buildEmailPreview(renderTemplateVars(selectedTemplate.body, employeeVars()), company);
  }

  async function handleConfirm() {
    if (!selectedTemplate) return;
    setSaving(true);
    setApiError("");
    try {
      // Pass extra_context so the backend substitutes all {variable} placeholders
      await clientApi.post(API.recruitment.sendEmail(employeeId), {
        template_name: selectedTemplate.name,
        extra_context: normalizeExtraContext(employeeVars()),
      });
      onSent();
      onClose();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setApiError(msg ?? t("Failed to send wish email."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title={
        <>
          <i className="ti ti-confetti" style={{ marginRight: 6 }} />
          {t("Send Wish — {name}", { name: employeeName })}
        </>
      }
      onClose={onClose}
      maxWidth={640}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>{t("Cancel")}</button>
          <button
            className="btn btn-filled"
            onClick={handleConfirm}
            disabled={saving || loadingTemplates || !selectedTemplate}
            suppressHydrationWarning
          >
            {saving
              ? <><i className="ti ti-loader-2 spin" /> {t("Sending…")}</>
              : <><i className="ti ti-confetti" /> {t("Confirm & Send Wish")}</>
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

          {/* Recipient info */}
          <div className="alert alert-info mb-16">
            <i className="ti ti-send" />
            <div>
              {t("Sending a wish email to")} <strong>{employeeName}</strong>
              {employeeEmail && <> {t("at")} <strong>{employeeEmail}</strong></>}
              {department && <> · {designation ?? ""} · {department}</>}
            </div>
          </div>

          {/* Template selector */}
          <div className="field-group mb-16">
            <label className="field-label">{t("Wish Template *")}</label>
            {loadingTemplates ? (
              <div style={{ fontSize: 13, color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 6 }}>
                <i className="ti ti-loader-2 spin" /> {t("Loading templates…")}
              </div>
            ) : (
              <select
                className="field-input field-select"
                value={selectedTemplate?.name ?? ""}
                onChange={e => {
                  const found = templateGroups.flatMap(g => g.templates).find(template => template.name === e.target.value) ?? null;
                  setSelectedTemplate(found);
                }}
                suppressHydrationWarning
              >
                {templateGroups.length === 0 && (
                  <option value="">{t("No active templates — create one in Settings → Email Templates")}</option>
                )}
                {templateGroups.map(g => (
                  <optgroup key={g.category} label={g.category.charAt(0).toUpperCase() + g.category.slice(1)}>
                    {g.templates.map(template => (
                      <option key={template.name} value={template.name}>{template.display_name}</option>
                    ))}
                  </optgroup>
                ))}
              </select>
            )}
          </div>

          {/* Email preview */}
          {selectedTemplate && (
            <div className="settings-card">
              <div className="settings-card-title flex items-center gap-2 mb-8">
                <i className="ti ti-mail" /> {t("Email Preview")}
              </div>
              {employeeEmail && (
                <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 2 }}>
                  <strong>{t("To:")}</strong> {employeeEmail}
                </div>
              )}
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 10 }}>
                <strong>{t("Subject:")}</strong> {previewSubject()}
              </div>
              <iframe
                srcDoc={previewHtml()}
                sandbox="allow-same-origin"
                style={{
                  width: "100%", height: 340,
                  border: "1px solid var(--outline-v)",
                  borderRadius: 6, display: "block",
                }}
                title={t("Email body preview")}
              />
            </div>
          )}
    </Modal>
  );
}

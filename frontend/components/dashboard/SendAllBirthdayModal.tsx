"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { CompanyInfo, normalizeExtraContext } from "@/lib/emailPreview";
import type { BirthdayEntry } from "./BirthdayWidget";

interface WishTemplate {
  name:         string;
  display_name: string;
  is_active:    boolean;
}

interface TemplateGroup {
  category:  string;
  templates: WishTemplate[];
}

interface Props {
  entries:   BirthdayEntry[];
  onClose:   () => void;
  onAllSent: (ids: string[]) => void;
}

export function SendAllBirthdayModal({ entries, onClose, onAllSent }: Props) {
  const [templateGroups,   setTemplateGroups]   = useState<TemplateGroup[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState<WishTemplate | null>(null);
  const [company,          setCompany]          = useState<CompanyInfo | null>(null);
  const [sending,          setSending]          = useState(false);
  const [progress,         setProgress]         = useState<{ done: number; total: number; errors: string[] } | null>(null);
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
            templates: (items as WishTemplate[]).filter(t => t.is_active),
          }))
          .filter(g => g.templates.length > 0);
        setTemplateGroups(groups);
        const all = groups.flatMap(g => g.templates);
        setSelectedTemplate(all.find(t => t.name.includes("birthday")) ?? all[0] ?? null);
        setCompany(coRes.data?.data ?? null);
      })
      .catch(() => setApiError("Could not load templates or company info."))
      .finally(() => setLoadingTemplates(false));
  }, []);

  function buildVars(entry: BirthdayEntry): Record<string, string> {
    const parts       = entry.name.trim().split(/\s+/);
    const firstName   = parts[0] ?? entry.name;
    const lastName    = parts.length > 1 ? parts[parts.length - 1] : "";
    const companyName = company?.company_name ?? "[Company]";
    return {
      employee_name:  entry.name,
      full_name:      entry.name,
      name:           entry.name,
      recipient_name: entry.name,
      first_name:     firstName,
      last_name:      lastName,
      fname:          firstName,
      lname:          lastName,
      department:     entry.department,
      designation:    entry.designation,
      company_name:   companyName,
      company:        companyName,
      EMPLOYEE_NAME:  entry.name,
      FULL_NAME:      entry.name,
      FIRST_NAME:     firstName,
      LAST_NAME:      lastName,
      COMPANY:        companyName,
      COMPANY_NAME:   companyName,
    };
  }

  async function handleSendAll() {
    if (!selectedTemplate) return;
    setSending(true);
    const errors: string[] = [];
    const sentIds: string[] = [];
    setProgress({ done: 0, total: entries.length, errors: [] });

    for (let i = 0; i < entries.length; i++) {
      const entry = entries[i];
      try {
        await clientApi.post(API.recruitment.sendEmail(entry.employee_id), {
          template_name: selectedTemplate.name,
          extra_context: normalizeExtraContext(buildVars(entry)),
        });
        sentIds.push(entry.employee_id);
      } catch {
        errors.push(entry.name);
      }
      setProgress({ done: i + 1, total: entries.length, errors: [...errors] });
    }

    setSending(false);
    if (sentIds.length > 0) onAllSent(sentIds);
  }

  const isDone = progress !== null && !sending;

  return (
    <div className="modal-overlay open" onClick={e => e.target === e.currentTarget && !sending && onClose()}>
      <div className="modal" style={{ maxWidth: 520 }}>

        <div className="modal-header">
          <div className="modal-title">
            <i className="ti ti-confetti" style={{ marginRight: 6 }} />
            Send Birthday Wishes — All ({entries.length})
          </div>
          {!sending && <button className="modal-close" onClick={onClose}><i className="ti ti-x" /></button>}
        </div>

        <div className="modal-body">
          {apiError && (
            <div className="alert alert-error mb-16">
              <i className="ti ti-alert-circle" /><div>{apiError}</div>
            </div>
          )}

          {/* Recipients */}
          <div className="alert alert-info mb-16">
            <i className="ti ti-users" />
            <div>
              Sending to <strong>{entries.length} employee{entries.length !== 1 ? "s" : ""}</strong>:{" "}
              {entries.map(e => e.name).join(", ")}
            </div>
          </div>

          {/* Template picker — only visible before sending */}
          {!isDone && (
            <div className="field-group mb-16">
              <label className="field-label">Wish Template *</label>
              {loadingTemplates ? (
                <div style={{ fontSize: 13, color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 6 }}>
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
                  disabled={sending}
                  suppressHydrationWarning
                >
                  {templateGroups.length === 0 && (
                    <option value="">No active templates — create one in Settings → Email Templates</option>
                  )}
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
          )}

          {/* Progress bar */}
          {progress && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 6, color: "var(--on-variant)" }}>
                <span>{sending ? "Sending wishes…" : "Done"}</span>
                <span>{progress.done} / {progress.total}</span>
              </div>
              <div style={{ height: 6, background: "var(--bg-high)", borderRadius: 3, overflow: "hidden" }}>
                <div style={{
                  height: "100%",
                  width: `${(progress.done / progress.total) * 100}%`,
                  background: "var(--primary)",
                  transition: "width 0.3s ease",
                  borderRadius: 3,
                }} />
              </div>

              {isDone && progress.errors.length === 0 && (
                <div className="alert alert-info" style={{ marginTop: 12 }}>
                  <i className="ti ti-circle-check" style={{ color: "#38a169" }} />
                  <div>All birthday wishes sent successfully!</div>
                </div>
              )}
              {isDone && progress.errors.length > 0 && (
                <div className="alert alert-error" style={{ marginTop: 12 }}>
                  <i className="ti ti-alert-circle" />
                  <div>
                    {progress.done - progress.errors.length} sent.
                    Failed: {progress.errors.join(", ")}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="modal-footer">
          {isDone ? (
            <button className="btn btn-filled" onClick={onClose} suppressHydrationWarning>
              <i className="ti ti-check" /> Close
            </button>
          ) : (
            <>
              <button className="btn btn-ghost" onClick={onClose} disabled={sending} suppressHydrationWarning>
                Cancel
              </button>
              <button
                className="btn btn-filled"
                onClick={handleSendAll}
                disabled={sending || loadingTemplates || !selectedTemplate}
                suppressHydrationWarning
              >
                {sending
                  ? <><i className="ti ti-loader-2 spin" /> Sending…</>
                  : <><i className="ti ti-confetti" /> Send to All {entries.length}</>
                }
              </button>
            </>
          )}
        </div>

      </div>
    </div>
  );
}

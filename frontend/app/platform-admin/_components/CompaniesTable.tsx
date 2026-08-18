"use client";

import { useState } from "react";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { MODULE_LABELS } from "@/types/platformAdmin";
import type { Company } from "@/types/platformAdmin";

interface Props {
  companies: Company[];
  onChanged: () => void;
}

const STATUS_BADGE: Record<Company["provisioning_status"], { className: string; label: string }> = {
  pending: { className: "badge-warn",    label: "Provisioning…" },
  active:  { className: "badge-success", label: "Active" },
  failed:  { className: "badge-error",   label: "Failed" },
};

export default function CompaniesTable({ companies, onChanged }: Props) {
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState("");
  const [editingDomainId, setEditingDomainId] = useState<string | null>(null);
  const [domainDraft, setDomainDraft] = useState("");
  const [savingDomain, setSavingDomain] = useState(false);
  const [domainError, setDomainError] = useState("");
  const [revealingId, setRevealingId] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<{ id: string; password: string } | null>(null);
  const [revealError, setRevealError] = useState("");
  const [copied, setCopied] = useState(false);

  async function toggleActive(company: Company) {
    setTogglingId(company.id);
    setToggleError("");
    try {
      await platformAdminApi.patch(API.platformAdmin.companies.detail(company.id), {
        is_active: !company.is_active,
      });
      onChanged();
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      const message = status === 403 || status === 401
        ? "Your session has expired — sign in again and retry."
        : ((err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Failed to update company status.");
      setToggleError(message);
    } finally {
      setTogglingId(null);
    }
  }

  function startEditDomain(company: Company) {
    setEditingDomainId(company.id);
    setDomainDraft(company.custom_domain);
    setDomainError("");
  }

  async function saveDomain(company: Company) {
    setSavingDomain(true);
    setDomainError("");
    try {
      await platformAdminApi.patch(API.platformAdmin.companies.detail(company.id), {
        custom_domain: domainDraft.trim().toLowerCase(),
      });
      setEditingDomainId(null);
      onChanged();
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to save domain.";
      setDomainError(message);
    } finally {
      setSavingDomain(false);
    }
  }

  async function revealPassword(company: Company) {
    setRevealingId(company.id);
    setRevealError("");
    try {
      const { data } = await platformAdminApi.post<{ data: { password: string } }>(
        API.platformAdmin.companies.revealPassword(company.id),
      );
      setRevealed({ id: company.id, password: data.data.password });
      onChanged(); // has_pending_password is now false — refresh so the button disappears
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to retrieve password.";
      setRevealError(message);
    } finally {
      setRevealingId(null);
    }
  }

  function copyRevealedPassword() {
    if (!revealed) return;
    navigator.clipboard.writeText(revealed.password).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  if (companies.length === 0) {
    return <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>No companies yet.</div>;
  }

  return (
    <div>
      {toggleError && (
        <div className="alert alert-warn" style={{ margin: 16 }}>
          <i className="ti ti-alert-triangle" />
          <div>{toggleError}</div>
        </div>
      )}
      {revealError && (
        <div className="alert alert-warn" style={{ margin: 16 }}>
          <i className="ti ti-alert-triangle" />
          <div>{revealError}</div>
        </div>
      )}
      {revealed && (
        <div className="alert alert-success" style={{ margin: 16, alignItems: "center" }}>
          <i className="ti ti-key" />
          <div style={{ flex: 1 }}>
            Admin password (shown once): <strong style={{ fontFamily: "monospace" }}>{revealed.password}</strong>
          </div>
          <button type="button" className="btn btn-ghost btn-sm" onClick={copyRevealedPassword} suppressHydrationWarning>
            <i className={`ti ${copied ? "ti-check" : "ti-copy"}`} /> {copied ? "Copied" : "Copy"}
          </button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => setRevealed(null)} suppressHydrationWarning>
            <i className="ti ti-x" />
          </button>
        </div>
      )}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Company</th>
              <th>Code</th>
              <th>Modules</th>
              <th>Domain</th>
              <th>Provisioning</th>
              <th>Status</th>
              <th>Created</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {companies.map(c => (
              <tr key={c.id}>
                <td>{c.company_name}</td>
                <td><span className="badge badge-neutral">{c.company_code}</span></td>
                <td style={{ maxWidth: 280 }}>
                  {c.enabled_modules.length === 0
                    ? <span className="text-muted">None</span>
                    : c.enabled_modules.map(m => MODULE_LABELS[m] ?? m).join(", ")}
                </td>
                <td style={{ minWidth: 200 }}>
                  {editingDomainId === c.id ? (
                    <div>
                      <div style={{ display: "flex", gap: 6 }}>
                        <input
                          className="field-input"
                          style={{ fontSize: 12, padding: "5px 8px" }}
                          placeholder="www.demo.com"
                          value={domainDraft}
                          onChange={e => setDomainDraft(e.target.value)}
                          disabled={savingDomain}
                          suppressHydrationWarning
                        />
                        <button className="btn btn-filled btn-sm" onClick={() => saveDomain(c)} disabled={savingDomain} suppressHydrationWarning>
                          {savingDomain ? "…" : "Save"}
                        </button>
                        <button className="btn btn-ghost btn-sm" onClick={() => setEditingDomainId(null)} disabled={savingDomain} suppressHydrationWarning>
                          Cancel
                        </button>
                      </div>
                      {domainError && <div className="field-error-msg">{domainError}</div>}
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => startEditDomain(c)}
                      suppressHydrationWarning
                    >
                      {c.custom_domain || <span className="text-muted">Not set</span>}
                      <i className="ti ti-pencil" style={{ marginLeft: 6 }} />
                    </button>
                  )}
                </td>
                <td>
                  <span className={`badge ${STATUS_BADGE[c.provisioning_status].className}`}>
                    {c.provisioning_status === "pending" && <i className="ti ti-loader-2 spin" style={{ marginRight: 4 }} />}
                    {STATUS_BADGE[c.provisioning_status].label}
                  </span>
                </td>
                <td>
                  <span className={`badge ${c.is_active ? "badge-success" : "badge-neutral"}`}>
                    {c.is_active ? "Active" : "Disabled"}
                  </span>
                </td>
                <td>{new Date(c.created_at).toLocaleDateString()}</td>
                <td style={{ display: "flex", gap: 6 }}>
                  {c.has_pending_password && (
                    <button
                      type="button"
                      className="btn btn-filled btn-sm"
                      disabled={revealingId === c.id}
                      onClick={() => revealPassword(c)}
                      suppressHydrationWarning
                    >
                      {revealingId === c.id ? "…" : (<><i className="ti ti-key" /> View credentials</>)}
                    </button>
                  )}
                  <button
                    type="button"
                    className={`btn btn-sm ${c.is_active ? "btn-ghost" : "btn-outline"}`}
                    disabled={togglingId === c.id || c.provisioning_status === "pending"}
                    onClick={() => toggleActive(c)}
                    suppressHydrationWarning
                  >
                    {togglingId === c.id ? "…" : c.is_active ? "Disable" : "Enable"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

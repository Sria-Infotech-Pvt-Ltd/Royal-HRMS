"use client";

import { useMemo, useState } from "react";
import Modal from "@/components/Modal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { MODULE_LABELS } from "@/types/platformAdmin";
import type { Company } from "@/types/platformAdmin";
import EditModulesModal from "./EditModulesModal";

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
  const [search, setSearch] = useState("");
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState("");
  const [editingModulesFor, setEditingModulesFor] = useState<Company | null>(null);
  const [revealingId, setRevealingId] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<{ company: Company; password: string } | null>(null);
  const [revealError, setRevealError] = useState("");
  const [copied, setCopied] = useState(false);

  const visibleCompanies = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return companies;
    return companies.filter(c =>
      c.company_name.toLowerCase().includes(q) || c.company_code.toLowerCase().includes(q),
    );
  }, [companies, search]);

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

  async function revealPassword(company: Company) {
    setRevealingId(company.id);
    setRevealError("");
    try {
      const { data } = await platformAdminApi.post<{ data: { password: string } }>(
        API.platformAdmin.companies.revealPassword(company.id),
      );
      setRevealed({ company, password: data.data.password });
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

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px", borderBottom: "1px solid var(--outline-v)" }}>
        <div className="relative" style={{ flex: 1, maxWidth: 320 }}>
          <i className="ti ti-search" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", color: "var(--on-variant)", fontSize: 15 }} />
          <input
            type="text"
            className="field-input"
            style={{ paddingLeft: 32, fontSize: 13 }}
            placeholder="Search by company name or code…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            suppressHydrationWarning
          />
        </div>
        <span style={{ fontSize: 12, color: "var(--on-variant)", whiteSpace: "nowrap" }}>
          {visibleCompanies.length} of {companies.length} {companies.length === 1 ? "company" : "companies"}
        </span>
      </div>

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

      {visibleCompanies.length === 0 ? (
        <div style={{ padding: 40, textAlign: "center", color: "var(--on-variant)" }}>
          <i className="ti ti-building-skyscraper" style={{ fontSize: 28, display: "block", marginBottom: 8, opacity: 0.5 }} />
          {companies.length === 0 ? "No companies yet." : `No companies match "${search}".`}
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Company</th>
                <th>Code</th>
                <th>Modules</th>
                <th>Provisioning</th>
                <th>Status</th>
                <th>Created</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visibleCompanies.map(c => (
                <tr key={c.id}>
                  <td>{c.company_name}</td>
                  <td><span className="badge badge-neutral">{c.company_code}</span></td>
                  <td style={{ maxWidth: 300 }}>
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 4 }}>
                      {c.enabled_modules.length === 0 ? (
                        <span className="text-muted" style={{ fontSize: 12 }}>None</span>
                      ) : (
                        c.enabled_modules.map(m => (
                          <span key={m} className="badge badge-neutral" style={{ fontSize: 11 }}>
                            {MODULE_LABELS[m] ?? m}
                          </span>
                        ))
                      )}
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        style={{ padding: "2px 6px" }}
                        onClick={() => setEditingModulesFor(c)}
                        aria-label={`Edit modules for ${c.company_name}`}
                        suppressHydrationWarning
                      >
                        <i className="ti ti-pencil" />
                      </button>
                    </div>
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
                  <td>
                    {/* Flex lives on this inner wrapper, not the <td> itself —
                        `display: flex` directly on a table cell breaks the
                        table's default `vertical-align: middle` (that
                        property only applies to table-cell boxes), which
                        left these buttons stuck at the top of the row once
                        the Modules column above grew tall enough to wrap
                        across multiple lines. */}
                    <div style={{ display: "flex", gap: 6 }}>
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
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editingModulesFor && (
        <EditModulesModal
          company={editingModulesFor}
          onClose={() => setEditingModulesFor(null)}
          onSaved={onChanged}
        />
      )}

      {revealed && (
        <Modal
          title="Admin credentials"
          onClose={() => { setRevealed(null); setCopied(false); }}
          maxWidth={420}
          footer={
            <button className="btn btn-filled" onClick={() => { setRevealed(null); setCopied(false); }} suppressHydrationWarning>
              Done
            </button>
          }
        >
          <div className="alert alert-warn mb-16">
            <i className="ti ti-alert-triangle" />
            <div>This password is shown once and cannot be retrieved again after closing this dialog.</div>
          </div>
          <div className="field-group">
            <span className="field-label">{revealed.company.company_name} — admin login</span>
            <div
              style={{
                display: "flex", alignItems: "center", gap: 8, padding: "10px 12px",
                background: "var(--bg-low)", borderRadius: 8, marginTop: 4,
              }}
            >
              <span style={{ fontFamily: "monospace", fontSize: 14, flex: 1, wordBreak: "break-all" }}>
                {revealed.password}
              </span>
              <button type="button" className="btn btn-ghost btn-sm" onClick={copyRevealedPassword} suppressHydrationWarning>
                <i className={`ti ${copied ? "ti-check" : "ti-copy"}`} /> {copied ? "Copied" : "Copy"}
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}

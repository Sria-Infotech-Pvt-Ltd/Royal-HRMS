"use client";

import { useMemo, useState } from "react";
import Modal from "@/components/Modal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
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
  const [search, setSearch] = useState("");
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState("");
  const [revealingId, setRevealingId] = useState<string | null>(null);
  const [revealed, setRevealed] = useState<{ company: Company; password: string } | null>(null);
  const [revealError, setRevealError] = useState("");
  const [copied, setCopied] = useState(false);

  // System Admin view/change-email — the single official place to do this
  // (see backend CompanySystemAdminView); the previous Employee Profile
  // page attempt was removed since a provisioned System Admin has no
  // employee_id and never reliably shows up in that company's own
  // Employees list.
  const [sysAdminFor,     setSysAdminFor]     = useState<Company | null>(null);
  const [sysAdminInfo,    setSysAdminInfo]    = useState<{ full_name: string; email: string } | null>(null);
  const [sysAdminLoading, setSysAdminLoading] = useState(false);
  const [sysAdminError,   setSysAdminError]   = useState("");
  const [newAdminEmail,   setNewAdminEmail]   = useState("");
  const [confirmingEmail, setConfirmingEmail] = useState(false);
  const [changingEmail,   setChangingEmail]   = useState(false);
  const [changeResult,    setChangeResult]    = useState<{ message: string; ok: boolean } | null>(null);

  // Reset System Admin password — a separate sub-flow within the same
  // modal, requiring the ACTING Platform Admin's own current password
  // (never the System Admin's) before anything changes.
  const [pwStep,               setPwStep]               = useState<"idle" | "verify" | "confirm">("idle");
  const [platformAdminPassword, setPlatformAdminPassword] = useState("");
  const [resettingPassword,    setResettingPassword]    = useState(false);
  const [resetResult,          setResetResult]          = useState<{ message: string; ok: boolean } | null>(null);

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

  const EMAIL_RE = /^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$/;

  async function openSystemAdmin(company: Company) {
    setSysAdminFor(company);
    setSysAdminInfo(null);
    setSysAdminError("");
    setNewAdminEmail("");
    setConfirmingEmail(false);
    setChangeResult(null);
    setPwStep("idle");
    setPlatformAdminPassword("");
    setResetResult(null);
    setSysAdminLoading(true);
    try {
      const { data } = await platformAdminApi.get<{ data: { full_name: string; email: string } }>(
        API.platformAdmin.companies.systemAdmin(company.id),
      );
      setSysAdminInfo(data.data);
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to load System Admin details.";
      setSysAdminError(message);
    } finally {
      setSysAdminLoading(false);
    }
  }

  function closeSystemAdmin() {
    setSysAdminFor(null);
  }

  function continueToConfirm() {
    setSysAdminError("");
    const trimmed = newAdminEmail.trim();
    if (!trimmed) { setSysAdminError("Enter the new System Admin email."); return; }
    if (!EMAIL_RE.test(trimmed)) { setSysAdminError("Enter a valid email address."); return; }
    if (sysAdminInfo && trimmed.toLowerCase() === sysAdminInfo.email.toLowerCase()) {
      setSysAdminError("That is already the current System Admin email.");
      return;
    }
    setConfirmingEmail(true);
  }

  async function confirmChangeSystemAdminEmail() {
    if (!sysAdminFor) return;
    setChangingEmail(true);
    setSysAdminError("");
    try {
      const { data } = await platformAdminApi.post<{
        message: string;
        data?: { email: string; full_name: string; new_email_sent?: boolean; old_email_sent?: boolean };
      }>(API.platformAdmin.companies.systemAdmin(sysAdminFor.id), { new_email: newAdminEmail.trim() });

      setSysAdminInfo({
        full_name: data.data?.full_name ?? sysAdminInfo?.full_name ?? "",
        email:     data.data?.email ?? newAdminEmail.trim(),
      });
      setChangeResult({
        message: data.message,
        ok: !(data.data && (data.data.new_email_sent === false || data.data.old_email_sent === false)),
      });
      setConfirmingEmail(false);
      setNewAdminEmail("");
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to change System Admin email.";
      setSysAdminError(message);
      setConfirmingEmail(false);
    } finally {
      setChangingEmail(false);
    }
  }

  function startPasswordReset() {
    setResetResult(null);
    setSysAdminError("");
    setPlatformAdminPassword("");
    setPwStep("verify");
  }

  function continueToResetConfirm() {
    setSysAdminError("");
    if (!platformAdminPassword) {
      setSysAdminError("Enter your Platform Admin password.");
      return;
    }
    setPwStep("confirm");
  }

  async function confirmResetPassword() {
    if (!sysAdminFor) return;
    setResettingPassword(true);
    setSysAdminError("");
    try {
      const { data } = await platformAdminApi.post<{ message: string; data?: { email_sent?: boolean } }>(
        API.platformAdmin.companies.systemAdminResetPassword(sysAdminFor.id),
        { platform_admin_password: platformAdminPassword },
      );
      setResetResult({ message: data.message, ok: data.data?.email_sent !== false });
      setPwStep("idle");
      setPlatformAdminPassword("");
    } catch (err) {
      // A wrong Platform Admin password (or any other rejection) sends
      // them back to re-enter it — step 2 has no password field to fix on.
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to reset System Admin password.";
      setSysAdminError(message);
      setPwStep("verify");
    } finally {
      setResettingPassword(false);
    }
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
                        property only applies to table-cell boxes). */}
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
                      {c.provisioning_status === "active" && (
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => openSystemAdmin(c)}
                          suppressHydrationWarning
                        >
                          <i className="ti ti-user-shield" /> System Admin
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

      {sysAdminFor && (
        <Modal
          title={
            pwStep === "verify" ? "Reset System Admin Password" :
            pwStep === "confirm" ? "Confirm Password Reset?" :
            confirmingEmail ? "Confirm Email Change?" : "System Admin"
          }
          onClose={closeSystemAdmin}
          closeDisabled={changingEmail || resettingPassword}
          maxWidth={440}
          footer={
            pwStep === "verify" ? (
              <>
                <button className="btn btn-ghost" onClick={() => setPwStep("idle")} suppressHydrationWarning>
                  Cancel
                </button>
                <button className="btn btn-filled" onClick={continueToResetConfirm} suppressHydrationWarning>
                  Verify &amp; Continue
                </button>
              </>
            ) : pwStep === "confirm" ? (
              <>
                <button className="btn btn-ghost" onClick={() => setPwStep("verify")} disabled={resettingPassword} suppressHydrationWarning>
                  Back
                </button>
                <button className="btn btn-filled" onClick={confirmResetPassword} disabled={resettingPassword} suppressHydrationWarning>
                  {resettingPassword ? "Resetting…" : "Reset Password"}
                </button>
              </>
            ) : confirmingEmail ? (
              <>
                <button className="btn btn-ghost" onClick={() => setConfirmingEmail(false)} disabled={changingEmail} suppressHydrationWarning>
                  Back
                </button>
                <button className="btn btn-filled" onClick={confirmChangeSystemAdminEmail} disabled={changingEmail} suppressHydrationWarning>
                  {changingEmail ? "Changing…" : "Yes, Change Email"}
                </button>
              </>
            ) : (
              <button className="btn btn-filled" onClick={closeSystemAdmin} suppressHydrationWarning>
                Done
              </button>
            )
          }
        >
          {sysAdminLoading ? (
            <div style={{ textAlign: "center", padding: "24px 0", color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 spin" /> Loading…
            </div>
          ) : (
            <>
              {sysAdminError && (
                <div className="alert alert-warn mb-16">
                  <i className="ti ti-alert-triangle" />
                  <div>{sysAdminError}</div>
                </div>
              )}
              {changeResult && (
                <div className={`alert ${changeResult.ok ? "alert-success" : "alert-warn"} mb-16`}>
                  <i className={`ti ${changeResult.ok ? "ti-check" : "ti-alert-triangle"}`} />
                  <div>{changeResult.message}</div>
                </div>
              )}
              {resetResult && (
                <div className={`alert ${resetResult.ok ? "alert-success" : "alert-warn"} mb-16`}>
                  <i className={`ti ${resetResult.ok ? "ti-check" : "ti-alert-triangle"}`} />
                  <div>{resetResult.message}</div>
                </div>
              )}

              {sysAdminInfo && pwStep === "idle" && !confirmingEmail && (
                <>
                  <div className="field-group mb-16">
                    <span className="field-label">{sysAdminFor.company_name} — System Admin</span>
                    <div style={{ padding: "10px 12px", background: "var(--bg-low)", borderRadius: 8, marginTop: 4 }}>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{sysAdminInfo.full_name}</div>
                      <div style={{ fontSize: 13, color: "var(--on-variant)", marginTop: 2 }}>{sysAdminInfo.email}</div>
                    </div>
                  </div>
                  <div className="field-group mb-16">
                    <label className="field-label">Change Login Email</label>
                    <input
                      type="email"
                      className="field-input"
                      placeholder="new.email@company.com"
                      value={newAdminEmail}
                      onChange={e => { setNewAdminEmail(e.target.value); setSysAdminError(""); }}
                      suppressHydrationWarning
                    />
                    <button
                      type="button"
                      className="btn btn-filled btn-sm"
                      style={{ marginTop: 8 }}
                      onClick={continueToConfirm}
                      suppressHydrationWarning
                    >
                      Continue
                    </button>
                  </div>
                  <div className="field-group" style={{ borderTop: "1px solid var(--outline-v)", paddingTop: 14 }}>
                    <label className="field-label">Password</label>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      style={{ border: "1px solid var(--outline-v)" }}
                      onClick={startPasswordReset}
                      suppressHydrationWarning
                    >
                      <i className="ti ti-key" /> Reset Password
                    </button>
                  </div>
                </>
              )}

              {pwStep === "verify" && (
                <div className="field-group">
                  <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 12 }}>
                    This will generate a new temporary password for {sysAdminFor.company_name}{"'"}s System Admin and
                    email it to them. Enter your own Platform Admin password to continue.
                  </p>
                  <label className="field-label">Your Platform Admin Password</label>
                  <input
                    type="password"
                    className="field-input"
                    placeholder="Your password"
                    value={platformAdminPassword}
                    onChange={e => { setPlatformAdminPassword(e.target.value); setSysAdminError(""); }}
                    autoFocus
                    suppressHydrationWarning
                  />
                </div>
              )}

              {pwStep === "confirm" && sysAdminInfo && (
                <div style={{ fontSize: 14 }}>
                  <div className="field-group mb-16">
                    <span className="field-label">{sysAdminFor.company_name} — System Admin</span>
                    <div style={{ padding: "10px 12px", background: "var(--bg-low)", borderRadius: 8, marginTop: 4 }}>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{sysAdminInfo.full_name}</div>
                      <div style={{ fontSize: 13, color: "var(--on-variant)", marginTop: 2 }}>{sysAdminInfo.email}</div>
                    </div>
                  </div>
                  <p style={{ fontSize: 12.5, color: "var(--on-variant)" }}>
                    A new temporary password will be generated and sent to this email. Their current password will
                    stop working immediately, and they{"'"}ll be asked to set a new one on next login.
                  </p>
                </div>
              )}

              {sysAdminInfo && confirmingEmail && (
                <div style={{ fontSize: 14 }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", borderRadius: 8, background: "var(--bg-low)", marginBottom: 8 }}>
                    <span style={{ fontSize: 12, color: "var(--on-variant)" }}>Current Email</span>
                    <span style={{ fontWeight: 600 }}>{sysAdminInfo.email}</span>
                  </div>
                  <div style={{ textAlign: "center", color: "var(--on-variant)", marginBottom: 8 }}>
                    <i className="ti ti-arrow-down" />
                  </div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 12px", borderRadius: 8, background: "rgba(234,179,8,0.1)", marginBottom: 12 }}>
                    <span style={{ fontSize: 12, color: "var(--on-variant)" }}>New Email</span>
                    <span style={{ fontWeight: 600 }}>{newAdminEmail.trim()}</span>
                  </div>
                  <p style={{ fontSize: 12.5, color: "var(--on-variant)" }}>
                    The System Admin will need to log in with the new email going forward. A confirmation will be
                    sent to the new address, and a security notice to the old one. Their password will not change.
                  </p>
                </div>
              )}
            </>
          )}
        </Modal>
      )}
    </div>
  );
}

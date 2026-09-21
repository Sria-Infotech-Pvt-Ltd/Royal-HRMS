"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { formatDateTime } from "@/lib/formatDate";
import Modal from "@/components/Modal";
import EmptyState from "@/components/EmptyState";
import LoadingState from "@/components/LoadingState";
import SmtpModal from "./_components/SmtpModal";
import {
  SMTP_BASE, smtpDetail, smtpActivate, SMTP_TEST,
  formToPayload,
  type ApiSmtpEntry, type ApiSmtpResponse, type SmtpForm,
} from "./_data";

export default function SmtpSettingsPage() {
  const router = useRouter();

  const [entries,     setEntries]     = useState<ApiSmtpEntry[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState<string | null>(null);

  const [editing,     setEditing]     = useState<ApiSmtpEntry | null | "add">(null);
  const [saving,      setSaving]      = useState(false);
  const [activating,  setActivating]  = useState<number | null>(null);
  const [deleting,    setDeleting]    = useState<number | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<ApiSmtpEntry | null>(null);

  const [testEntry,   setTestEntry]   = useState<ApiSmtpEntry | null>(null);
  const [testEmail,   setTestEmail]   = useState("");
  const [testPassword,setTestPassword]= useState("");
  const [testLoading, setTestLoading] = useState(false);

  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => { loadData(); }, []);

  function showToast(msg: string, ok = true) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  }

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const res = await clientApi.get(SMTP_BASE);
      const envelope = res.data?.data as ApiSmtpResponse;
      setEntries(envelope?.results ?? []);
    } catch (err: unknown) {
      setError((err as { message?: string }).message ?? "Failed to load SMTP configurations");
    } finally {
      setLoading(false);
    }
  }

  // ── Create ──────────────────────────────────────────────────────────────────

  async function handleCreate(form: SmtpForm) {
    setSaving(true);
    try {
      const res = await clientApi.post(SMTP_BASE, formToPayload(form));
      const created = (res.data.data ?? res.data) as ApiSmtpEntry;
      setEntries(prev => [...prev, created]);
      setEditing(null);
      showToast(`"${form.name}" added successfully`);
    } catch (err: unknown) {
      showToast((err as { message?: string }).message ?? "Failed to add configuration", false);
    } finally {
      setSaving(false);
    }
  }

  // ── Update ──────────────────────────────────────────────────────────────────

  async function handleUpdate(form: SmtpForm) {
    if (!editing || editing === "add") return;
    const target = editing as ApiSmtpEntry;
    setSaving(true);
    try {
      const res = await clientApi.put(smtpDetail(target.id), formToPayload(form));
      const updated = (res.data.data ?? res.data) as ApiSmtpEntry;
      setEntries(prev => prev.map(e => e.id === target.id ? { ...e, ...updated } : e));
      setEditing(null);
      showToast(`"${form.name}" updated`);
    } catch (err: unknown) {
      showToast((err as { message?: string }).message ?? "Failed to update", false);
    } finally {
      setSaving(false);
    }
  }

  // ── Activate ─────────────────────────────────────────────────────────────────

  async function handleActivate(entry: ApiSmtpEntry) {
    setActivating(entry.id);
    try {
      await clientApi.post(smtpActivate(entry.id));
      setEntries(prev => prev.map(e => ({ ...e, is_active: e.id === entry.id })));
      showToast(`"${entry.name}" is now active`);
    } catch (err: unknown) {
      showToast((err as { message?: string }).message ?? "Failed to activate", false);
    } finally {
      setActivating(null);
    }
  }

  // ── Delete ───────────────────────────────────────────────────────────────────

  function handleDelete(entry: ApiSmtpEntry) {
    setDeleteTarget(entry);
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    const entry = deleteTarget;
    setDeleting(entry.id);
    try {
      await clientApi.delete(smtpDetail(entry.id));
      setEntries(prev => prev.filter(e => e.id !== entry.id));
      showToast(`"${entry.name}" deleted`);
      setDeleteTarget(null);
    } catch (err: unknown) {
      showToast((err as { message?: string }).message ?? "Failed to delete", false);
    } finally {
      setDeleting(null);
    }
  }

  // ── Test ─────────────────────────────────────────────────────────────────────

  async function handleTest() {
    if (!testEntry || !testEmail.trim()) return;
    setTestLoading(true);
    try {
      await clientApi.post(SMTP_TEST, {
        host:           testEntry.host,
        port:           testEntry.port,
        username:       testEntry.username,
        password:       testPassword,
        from_email:     testEntry.from_email,
        sender_name:    testEntry.sender_name,
        use_tls:        testEntry.use_tls,
        test_recipient: testEmail.trim(),
      });
      showToast(`Test email sent to ${testEmail}`);
      setTestEntry(null);
      setTestEmail("");
      setTestPassword("");
    } catch (err: unknown) {
      showToast((err as { message?: string }).message ?? "Test email failed", false);
    } finally {
      setTestLoading(false);
    }
  }

  const FIELDS = (entry: ApiSmtpEntry) => {
    const isLocal = entry.smtp_type === "local" || !entry.smtp_type;
    return [
      { icon: "ti-toggle-right",  label: "Type",        value: entry.smtp_type_display || "—" },
      ...(isLocal ? [
        { icon: "ti-server-2",    label: "Host",        value: entry.host || "—" },
        { icon: "ti-plug",        label: "Port",        value: `${entry.port}${entry.use_tls ? " · TLS" : ""}` },
        { icon: "ti-at",          label: "Username",    value: entry.username || "—" },
        { icon: "ti-lock",        label: "Password",    value: entry.password_display },
      ] : []),
      { icon: "ti-mail",         label: "From Email",  value: entry.from_email || "—" },
      { icon: "ti-user",         label: "Sender Name", value: entry.sender_name || "—" },
      { icon: "ti-mail-forward", label: "BCC Email",   value: entry.bcc_email || "—" },
      { icon: "ti-flag",         label: "Priority",    value: entry.priority ? entry.priority.charAt(0).toUpperCase() + entry.priority.slice(1) : "—" },
      { icon: "ti-inbox",        label: "Receiver",    value: entry.receiver_email_type === "personal_email_id" ? "Personal Email" : "Email ID" },
    ];
  };

  const isAddMode    = editing === "add";
  const editEntry    = editing && editing !== "add" ? editing as ApiSmtpEntry : null;
  const activeEntry  = entries.find(e => e.is_active);

  return (
    <>
      {/* Toast */}
      {toast && (
        <div style={{ position: "fixed", top: 20, right: 24, zIndex: 9999, display: "flex", alignItems: "center", gap: 10, padding: "12px 18px", background: toast.ok ? "var(--success-c)" : "var(--error-c)", border: `1px solid ${toast.ok ? "var(--success)" : "var(--error)"}`, borderRadius: "var(--radius)", boxShadow: "var(--shadow-md)", fontSize: 13, color: toast.ok ? "var(--success)" : "var(--error)", animation: "slideIn 0.2s ease" }}>
          <i className={`ti ${toast.ok ? "ti-circle-check" : "ti-alert-circle"}`} style={{ fontSize: 16 }} />
          {toast.msg}
        </div>
      )}

      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-title">SMTP Settings</div>
          <div className="page-sub">Configure outgoing mail servers for transactional emails</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")} suppressHydrationWarning>
            <i className="ti ti-arrow-left" /> Back
          </button>
          <button className="btn btn-filled btn-sm" onClick={() => setEditing("add")} style={{ gap: 6 }} suppressHydrationWarning>
            <i className="ti ti-plus" /> Add SMTP
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading && <LoadingState label="Loading SMTP configurations…" fullHeight />}

      {/* Error */}
      {!loading && error && (
        <div className="alert alert-error mb-24">
          <i className="ti ti-alert-circle" />
          <div>
            <strong>Failed to load</strong> — {error}
            <div style={{ marginTop: 8 }}><button className="btn btn-ghost btn-sm" onClick={loadData} suppressHydrationWarning>Retry</button></div>
          </div>
        </div>
      )}

      {/* Active banner */}
      {!loading && !error && activeEntry && (
        <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", marginBottom: 20, background: "rgba(23,144,90,0.07)", border: "1px solid rgba(23,144,90,0.2)", borderRadius: "var(--radius)" }}>
          <i className="ti ti-circle-check-filled" style={{ fontSize: 16, color: "var(--success)" }} />
          <span style={{ fontSize: 13 }}>
            Currently using <strong>{activeEntry.name}</strong> ({activeEntry.from_email}) for sending emails.
          </span>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && entries.length === 0 && (
        <EmptyState icon="ti-mail-off" title="No SMTP configurations yet" description="Click Add SMTP to get started" />
      )}

      {/* Cards grid */}
      {!loading && !error && entries.length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {entries.map(entry => (
            <div key={entry.id} className="card" style={{
              padding: 0, overflow: "hidden", display: "flex", flexDirection: "column",
              border: entry.is_active ? "2px solid var(--primary)" : "1px solid var(--outline-v)",
            }}>
              {/* Card header */}
              <div style={{ padding: "14px 20px", background: "var(--bg-low)", borderBottom: "1px solid var(--outline-v)", display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ width: 36, height: 36, borderRadius: 8, background: "rgba(124,58,237,0.1)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <i className="ti ti-mail-cog" style={{ fontSize: 17, color: "var(--primary)" }} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{entry.name}</div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 1 }}>
                    Updated {formatDateTime(entry.updated_at)}
                  </div>
                </div>
                {entry.is_active
                  ? <span className="badge badge-success" style={{ fontSize: 11, flexShrink: 0 }}><i className="ti ti-star-filled" style={{ fontSize: 9, marginRight: 3 }} />Active</span>
                  : <span className="badge badge-neutral"  style={{ fontSize: 11, flexShrink: 0 }}>Inactive</span>
                }
              </div>

              {/* Fields */}
              <div style={{ flex: 1, padding: "20px" }}>
                <div className="grid grid-cols-1 sm:grid-cols-2" style={{ gap: "14px 24px" }}>
                  {FIELDS(entry).map(row => (
                    <div key={row.label} style={{ display: "flex", gap: 9, alignItems: "flex-start" }}>
                      <i className={`ti ${row.icon}`} style={{ fontSize: 13, color: "var(--outline)", marginTop: 2, flexShrink: 0 }} />
                      <div>
                        <div style={{ fontSize: 10, color: "var(--outline)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 }}>{row.label}</div>
                        <div style={{ fontSize: 12, color: "var(--on-bg)", marginTop: 2, wordBreak: "break-all" }}>{row.value}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Footer actions */}
              <div style={{ padding: "12px 20px", borderTop: "1px solid var(--outline-v)", background: "var(--bg-low)", display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                {!entry.is_active && (
                  <button className="btn btn-ghost btn-sm" onClick={() => handleActivate(entry)} disabled={activating === entry.id} style={{ gap: 6 }} suppressHydrationWarning>
                    {activating === entry.id
                      ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Activating…</>
                      : <><i className="ti ti-star" style={{ color: "var(--secondary)" }} /> Set Active</>
                    }
                  </button>
                )}
                <button className="btn btn-ghost btn-sm" onClick={() => { setTestEntry(entry); setTestEmail(""); setTestPassword(""); }} style={{ gap: 6 }} suppressHydrationWarning>
                  <i className="ti ti-send" style={{ color: "var(--info)" }} /> Test
                </button>
                <button className="btn btn-ghost btn-sm" onClick={() => handleDelete(entry)} disabled={deleting === entry.id} style={{ gap: 6, color: "var(--error)" }} suppressHydrationWarning>
                  {deleting === entry.id
                    ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Deleting…</>
                    : <><i className="ti ti-trash" /> Delete</>
                  }
                </button>
                <button className="btn btn-filled btn-sm" onClick={() => setEditing(entry)} style={{ marginLeft: "auto", gap: 6 }} suppressHydrationWarning>
                  <i className="ti ti-pencil" /> Edit
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Test email modal */}
      {testEntry && (
        <Modal
          title={
            <>
              <div>Send Test Email</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                Via <strong>{testEntry.name}</strong> · from <code style={{ background: "var(--bg-low)", padding: "1px 5px", borderRadius: 3 }}>{testEntry.from_email}</code>
              </div>
            </>
          }
          onClose={() => setTestEntry(null)}
          maxWidth="min(440px, 96vw)"
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setTestEntry(null)} suppressHydrationWarning>Cancel</button>
              <button className="btn btn-filled" onClick={handleTest}
                disabled={!testEmail.trim() || !testPassword.trim() || testLoading}
                suppressHydrationWarning>
                {testLoading
                  ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Sending…</>
                  : <><i className="ti ti-send" /> Send Test</>
                }
              </button>
            </>
          }
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div className="field-group">
              <label className="field-label">Recipient email <span style={{ color: "var(--error)" }}>*</span></label>
              <input className="field-input" type="email" placeholder="recipient@example.com"
                value={testEmail} onChange={e => setTestEmail(e.target.value)}
                autoFocus suppressHydrationWarning />
            </div>
            <div className="field-group">
              <label className="field-label">SMTP Password <span style={{ color: "var(--error)" }}>*</span></label>
              <input className="field-input" type="password" placeholder="Enter SMTP password to authenticate"
                value={testPassword} onChange={e => setTestPassword(e.target.value)}
                onKeyDown={e => e.key === "Enter" && handleTest()}
                suppressHydrationWarning />
            </div>
          </div>
        </Modal>
      )}

      {/* Delete confirm */}
      {deleteTarget && (
        <div className="modal-overlay open" style={{ zIndex: 1010 }}>
          <div className="modal" style={{ maxWidth: "420px" }}>
            <div className="modal-header">
              <div className="modal-title">
                <i className="ti ti-alert-triangle" style={{ marginRight: "8px", color: "var(--error)" }} />
                Delete SMTP Configuration?
              </div>
              <button className="modal-close" onClick={() => setDeleteTarget(null)} disabled={deleting === deleteTarget.id}>
                <i className="ti ti-x" />
              </button>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: "14px", color: "var(--on-variant)", lineHeight: 1.6 }}>
                Are you sure you want to delete <strong>{deleteTarget.name}</strong>? This action cannot be undone.
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setDeleteTarget(null)} disabled={deleting === deleteTarget.id}>Cancel</button>
              <button
                className="btn btn-filled"
                style={{ background: "var(--error)" }}
                onClick={confirmDelete}
                disabled={deleting === deleteTarget.id}
                suppressHydrationWarning
              >
                {deleting === deleteTarget.id
                  ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite", marginRight: "6px" }} />Deleting…</>
                  : "Yes, Delete"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add / Edit modal */}
      {editing !== null && (
        <SmtpModal
          entry={isAddMode ? null : editEntry}
          saving={saving}
          onClose={() => setEditing(null)}
          onSave={isAddMode ? handleCreate : handleUpdate}
        />
      )}

      <style>{`
        @keyframes spin    { to { transform: rotate(360deg); } }
        @keyframes slideIn { from { opacity: 0; transform: translateX(12px); } to { opacity: 1; transform: translateX(0); } }
      `}</style>
    </>
  );
}

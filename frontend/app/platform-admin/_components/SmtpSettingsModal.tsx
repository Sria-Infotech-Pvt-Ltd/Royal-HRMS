"use client";

import { useEffect, useState } from "react";
import Modal from "@/components/Modal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import type { PlatformSMTPSettings } from "@/types/platformAdmin";

interface Props {
  onClose: () => void;
}

export default function SmtpSettingsModal({ onClose }: Props) {
  const { data: current, loading } = useFetch<PlatformSMTPSettings>(API.platformAdmin.smtpSettings, platformAdminApi);
  const [host,       setHost]       = useState("");
  const [port,       setPort]       = useState(587);
  const [username,   setUsername]   = useState("");
  const [password,   setPassword]   = useState("");
  const [useTls,     setUseTls]     = useState(true);
  const [fromEmail,  setFromEmail]  = useState("");
  const [senderName, setSenderName] = useState("Royal HRMS");
  const [initialized, setInitialized] = useState(false);
  const [saving,  setSaving]  = useState(false);
  const [error,   setError]   = useState("");
  const [saved,   setSaved]   = useState(false);

  // Seeds the form from the loaded settings exactly once — after that the
  // fields are user-owned, so a background refetch (e.g. onChanged) never
  // clobbers what they're actively typing.
  useEffect(() => {
    if (!current || initialized) return;
    setInitialized(true);
    setHost(current.host);
    setPort(current.port);
    setUsername(current.username);
    setUseTls(current.use_tls);
    setFromEmail(current.from_email);
    setSenderName(current.sender_name);
  }, [current, initialized]);

  async function handleSave() {
    setError("");
    setSaved(false);
    if (!host.trim() || !username.trim() || !fromEmail.trim()) {
      setError("Host, username, and from-email are required.");
      return;
    }
    setSaving(true);
    try {
      await platformAdminApi.put(API.platformAdmin.smtpSettings, {
        host: host.trim(), port, username: username.trim(),
        ...(password ? { password } : {}),
        use_tls: useTls, from_email: fromEmail.trim(), sender_name: senderName.trim(),
      });
      setPassword("");
      setSaved(true);
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to save SMTP settings.";
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title="Platform email settings"
      onClose={onClose}
      maxWidth={520}
      closeDisabled={saving}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={saving} suppressHydrationWarning>Close</button>
          <button className="btn btn-filled" onClick={handleSave} disabled={saving || loading} suppressHydrationWarning>
            {saving ? (<><i className="ti ti-loader-2 spin" /> Saving…</>) : "Save"}
          </button>
        </>
      }
    >
      <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 16 }}>
        Used only for the platform&apos;s own emails to newly created companies (their login details) —
        separate from any single company&apos;s own SMTP settings.
      </p>

      {current && !current.is_configured && (
        <div className="alert alert-warn mb-16">
          <i className="ti ti-alert-triangle" />
          <div>Not configured yet — new companies won&apos;t receive an automatic welcome email until this is set up.</div>
        </div>
      )}

      {error && (
        <div className="alert alert-warn mb-16">
          <i className="ti ti-alert-triangle" />
          <div>{error}</div>
        </div>
      )}
      {saved && (
        <div className="alert alert-success mb-16">
          <i className="ti ti-check" />
          <div>Saved.</div>
        </div>
      )}

      <div className="form-row cols-2">
        <div className="field-group">
          <label className="field-label" htmlFor="smtp-host">Host</label>
          <input id="smtp-host" className="field-input" placeholder="smtp.gmail.com" value={host}
            onChange={e => setHost(e.target.value)} disabled={saving} suppressHydrationWarning />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="smtp-port">Port</label>
          <input id="smtp-port" type="number" className="field-input" value={port}
            onChange={e => setPort(Number(e.target.value) || 587)} disabled={saving} suppressHydrationWarning />
        </div>
      </div>

      <div className="form-row cols-2">
        <div className="field-group">
          <label className="field-label" htmlFor="smtp-username">Username</label>
          <input id="smtp-username" className="field-input" placeholder="you@gmail.com" value={username}
            onChange={e => setUsername(e.target.value)} disabled={saving} suppressHydrationWarning />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="smtp-password">Password</label>
          <input id="smtp-password" type="password" className="field-input" placeholder={current?.is_configured ? "Unchanged" : ""} value={password}
            onChange={e => setPassword(e.target.value)} disabled={saving} suppressHydrationWarning />
        </div>
      </div>

      <div className="form-row cols-2">
        <div className="field-group">
          <label className="field-label" htmlFor="smtp-from">From email</label>
          <input id="smtp-from" type="email" className="field-input" placeholder="noreply@royalhrms.com" value={fromEmail}
            onChange={e => setFromEmail(e.target.value)} disabled={saving} suppressHydrationWarning />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="smtp-sender">Sender name</label>
          <input id="smtp-sender" className="field-input" value={senderName}
            onChange={e => setSenderName(e.target.value)} disabled={saving} suppressHydrationWarning />
        </div>
      </div>

      <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: saving ? "default" : "pointer" }}>
        <input type="checkbox" checked={useTls} onChange={e => setUseTls(e.target.checked)} disabled={saving} suppressHydrationWarning />
        Use TLS
      </label>
    </Modal>
  );
}

"use client";

import { useEffect, useState } from "react";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import type { PlatformSMTPSettings } from "@/types/platformAdmin";

export default function EmailSettingsPage() {
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
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  // Seeds the form from the loaded settings exactly once — after that the
  // fields are user-owned, so a background refetch never clobbers what
  // they're actively typing.
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

  async function handleSendTest() {
    setTestResult(null);
    setTesting(true);
    try {
      const { data } = await platformAdminApi.post<{ message: string }>(
        API.platformAdmin.smtpSettingsTest,
      );
      setTestResult({ ok: true, message: data.message });
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to send test email.";
      setTestResult({ ok: false, message });
    } finally {
      setTesting(false);
    }
  }

  return (
    <div style={{ padding: "32px 24px" }}>
      <a href="/platform-admin/settings" style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 12.5, marginBottom: 12 }}>
        <i className="ti ti-arrow-left" /> Settings
      </a>
      <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>Email Settings</h1>
      <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 24, maxWidth: 640 }}>
        Used only for the platform&apos;s own emails to newly created companies (their login details)
        and platform-admin password resets — separate from any single company&apos;s own SMTP settings.
      </p>

      {/* The page itself is full-width (no dead gap on either side), but the
          form stays at a readable width instead of stretching every input
          across the whole screen. */}
      <div className="card" style={{ maxWidth: 640 }}>
        <div className="card-body">
          {loading ? (
            <div style={{ padding: 16, textAlign: "center", color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 spin" /> Loading…
            </div>
          ) : (
            <>
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
              {testResult && (
                <div className={`alert ${testResult.ok ? "alert-success" : "alert-warn"} mb-16`}>
                  <i className={`ti ${testResult.ok ? "ti-check" : "ti-alert-triangle"}`} />
                  <div>{testResult.message}</div>
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

              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: saving ? "default" : "pointer", marginBottom: 20 }}>
                <input type="checkbox" checked={useTls} onChange={e => setUseTls(e.target.checked)} disabled={saving} suppressHydrationWarning />
                Use TLS
              </label>

              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-filled" onClick={handleSave} disabled={saving} suppressHydrationWarning>
                  {saving ? (<><i className="ti ti-loader-2 spin" /> Saving…</>) : "Save"}
                </button>
                <button
                  type="button"
                  className="btn btn-outline"
                  onClick={handleSendTest}
                  disabled={testing || saving}
                  title="Sends a real test email to your platform-admin login email, using the SMTP settings currently saved above"
                  suppressHydrationWarning
                >
                  {testing ? (<><i className="ti ti-loader-2 spin" /> Sending…</>) : (<><i className="ti ti-send" /> Send test email</>)}
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

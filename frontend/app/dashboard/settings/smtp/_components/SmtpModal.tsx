"use client";

import { useState } from "react";
import {
  EMPTY_SMTP_FORM, apiEntryToForm, validateSmtpForm,
  PROVIDER_META, PROVIDER_PRESETS,
  type ApiSmtpEntry, type SmtpForm, type SmtpFormErrors, type Provider,
} from "../_data";
import Modal from "@/components/Modal";

interface Props {
  entry:    ApiSmtpEntry | null;  // null = add mode
  /** Add mode only — the provider chosen in ProviderSelectModal just before
   *  this opened. Drives the prefilled/locked host/port/TLS section below. */
  provider?: Exclude<Provider, "">;
  saving:   boolean;
  onClose:  () => void;
  onSave:   (form: SmtpForm) => Promise<void>;
  /** Add mode only — reopens ProviderSelectModal instead of closing outright. */
  onChangeProvider?: () => void;
}

export default function SmtpModal({ entry, provider, saving, onClose, onSave, onChangeProvider }: Props) {
  const isAddMode = entry === null;
  // Undefined only in edit mode (provider isn't passed there); add mode
  // always comes from ProviderSelectModal, so this is always set when needed.
  const preset = provider ? PROVIDER_PRESETS[provider] : null;

  const [form,   setForm]   = useState<SmtpForm>(() => {
    if (!isAddMode) return apiEntryToForm(entry);
    if (!preset) return { ...EMPTY_SMTP_FORM };
    return {
      ...EMPTY_SMTP_FORM,
      provider: provider!,
      smtpType: preset.smtpType,
      host:     preset.host,
      port:     preset.port,
      useTls:   preset.useTls,
    };
  });
  const [errors, setErrors] = useState<SmtpFormErrors>({});

  const isLocal = form.smtpType === "local";

  function patch(p: Partial<SmtpForm>) { setForm(prev => ({ ...prev, ...p })); }
  function clearErr(k: keyof SmtpForm) { setErrors(prev => ({ ...prev, [k]: undefined })); }

  async function handleSave() {
    const errs = validateSmtpForm(form, isAddMode);
    if (Object.keys(errs).length) { setErrors(errs); return; }
    await onSave(form);
  }

  return (
    <Modal
      title={
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div>
              {isAddMode ? "Add SMTP Configuration" : `Edit — ${entry.name}`}
            </div>
            {!isAddMode && entry.is_active && (
              <span className="badge badge-success" style={{ fontSize: 10 }}>
                <i className="ti ti-star-filled" style={{ fontSize: 9, marginRight: 3 }} />Active
              </span>
            )}
          </div>
          {!isAddMode && (
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>
              Last updated: {new Date(entry.updated_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
            </div>
          )}
        </>
      }
      onClose={onClose}
      size="lg"
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={saving} suppressHydrationWarning>Cancel</button>
          <button className="btn btn-filled" onClick={handleSave} disabled={saving} suppressHydrationWarning>
            {saving
              ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
              : <><i className="ti ti-device-floppy" /> {isAddMode ? "Add Configuration" : "Save Changes"}</>
            }
          </button>
        </>
      }
    >

          {/* ── Add mode: provider chosen in the picker — compact header + Change provider ── */}
          {isAddMode && preset && provider && (
            <div style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              paddingBottom: 14, marginBottom: 20, borderBottom: "1px solid var(--outline-v)",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                  background: PROVIDER_META[provider].iconBg, color: PROVIDER_META[provider].iconColor,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <i className={`ti ${PROVIDER_META[provider].icon}`} style={{ fontSize: 16 }} />
                </div>
                <span style={{ fontSize: 14, fontWeight: 600 }}>{PROVIDER_META[provider].label}</span>
              </div>
              {onChangeProvider && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={onChangeProvider} suppressHydrationWarning>
                  <i className="ti ti-arrow-left" /> Change provider
                </button>
              )}
            </div>
          )}

          <div className="smtp-form-grid">

            {/* Configuration Name — full width */}
            <div className="field-group" style={{ gridColumn: "1 / -1" }}>
              <label className="field-label">Configuration Name <span style={{ color: "var(--error)" }}>*</span></label>
              <input className="field-input"
                placeholder={form.smtpType === "local" ? "e.g. Gmail SMTP, Zoho Mail" : "e.g. Corporate Mail Server"}
                value={form.name}
                onChange={e => { patch({ name: e.target.value }); clearErr("name"); }}
                suppressHydrationWarning />
              {errors.name && <span className="field-error">{errors.name}</span>}
            </div>

            {/* ── Local-only fields ── */}
            {isLocal && (
              <>
                {/* Host */}
                <div className="field-group">
                  <label className="field-label">SMTP Host <span style={{ color: "var(--error)" }}>*</span></label>
                  <input className="field-input" placeholder="smtp.gmail.com"
                    value={form.host} disabled={!!preset?.hostLocked}
                    onChange={e => { patch({ host: e.target.value }); clearErr("host"); }}
                    suppressHydrationWarning />
                  {errors.host && <span className="field-error">{errors.host}</span>}
                  {preset?.hostHint && (
                    <p style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 5, lineHeight: 1.4 }}
                      dangerouslySetInnerHTML={{ __html: preset.hostHint }} />
                  )}
                </div>

                {/* Port + TLS */}
                <div className="field-group">
                  <label className="field-label">Port</label>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <input className="field-input" type="number" value={form.port}
                      disabled={!!preset?.hostLocked}
                      onChange={e => patch({ port: Number(e.target.value) })}
                      style={{ flex: 1 }}
                      suppressHydrationWarning />
                    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: preset?.hostLocked ? "default" : "pointer", whiteSpace: "nowrap" }}>
                      <input type="checkbox" checked={form.useTls}
                        disabled={!!preset?.hostLocked}
                        onChange={e => patch({ useTls: e.target.checked })}
                        style={{ accentColor: "var(--primary)" }}
                        suppressHydrationWarning />
                      Use TLS
                    </label>
                  </div>
                </div>

                {/* Username */}
                <div className="field-group">
                  <label className="field-label">Username <span style={{ color: "var(--error)" }}>*</span></label>
                  <input className="field-input" placeholder="login username / email"
                    value={form.username}
                    onChange={e => { patch({ username: e.target.value }); clearErr("username"); }}
                    suppressHydrationWarning />
                  {errors.username && <span className="field-error">{errors.username}</span>}
                  {preset?.usernameHint && (
                    <p style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 5, lineHeight: 1.4 }}>
                      {preset.usernameHint}
                    </p>
                  )}
                </div>

                {/* Password */}
                <div className="field-group">
                  <label className="field-label">
                    Password
                    {isAddMode
                      ? <span style={{ color: "var(--error)", marginLeft: 4 }}>*</span>
                      : <span style={{ fontSize: 11, color: "var(--outline)", marginLeft: 6 }}>leave blank to keep current</span>
                    }
                  </label>
                  <input className="field-input" type="password"
                    placeholder={isAddMode ? "SMTP password / App password" : "New password (optional)"}
                    value={form.password}
                    onChange={e => { patch({ password: e.target.value }); clearErr("password"); }}
                    suppressHydrationWarning />
                  {errors.password && <span className="field-error">{errors.password}</span>}
                </div>
              </>
            )}

            {/* Sender Name */}
            <div className="field-group">
              <label className="field-label">Sender Name</label>
              <input className="field-input" placeholder="Royal HRMS"
                value={form.senderName}
                onChange={e => patch({ senderName: e.target.value })}
                suppressHydrationWarning />
            </div>

            {/* From Email */}
            <div className="field-group">
              <label className="field-label">From Email <span style={{ color: "var(--error)" }}>*</span></label>
              <input className="field-input" type="email" placeholder="you@gmail.com"
                value={form.fromEmail}
                onChange={e => { patch({ fromEmail: e.target.value }); clearErr("fromEmail"); }}
                suppressHydrationWarning />
              {errors.fromEmail && <span className="field-error">{errors.fromEmail}</span>}
            </div>

            {/* BCC */}
            <div className="field-group">
              <label className="field-label">BCC Email</label>
              <input className="field-input" type="email" placeholder="bcc@company.com"
                value={form.bccEmail}
                onChange={e => patch({ bccEmail: e.target.value })}
                suppressHydrationWarning />
            </div>

            {/* Priority */}
            <div className="field-group">
              <label className="field-label">Priority</label>
              <select className="field-input" value={form.priority}
                onChange={e => patch({ priority: e.target.value as typeof form.priority })}
                style={{ cursor: "pointer" }}
                suppressHydrationWarning>
                <option value="">Select</option>
                <option value="high">High</option>
                <option value="normal">Normal</option>
                <option value="low">Low</option>
              </select>
            </div>

            {/* Receiver Email Type */}
            <div className="field-group" style={{ gridColumn: "1 / -1" }}>
              <label className="field-label">Receivers Email</label>
              <div style={{ display: "flex", gap: 24, marginTop: 6 }}>
                {(["email_id", "personal_email_id"] as const).map(val => (
                  <label key={val} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: "pointer" }}>
                    <input type="radio" name="receiverEmailType" value={val}
                      checked={form.receiverEmailType === val}
                      onChange={() => patch({ receiverEmailType: val })}
                      style={{ accentColor: "var(--primary)" }}
                      suppressHydrationWarning />
                    {val === "email_id" ? "Email ID" : "Personal Email ID"}
                  </label>
                ))}
              </div>
            </div>

          </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </Modal>
  );
}

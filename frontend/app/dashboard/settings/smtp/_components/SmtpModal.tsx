"use client";

import { useState } from "react";
import {
  EMPTY_SMTP_FORM, apiEntryToForm, validateSmtpForm,
  PROVIDER_CONFIG, PROVIDER_LIST, inferProviderKey, applyProvider,
  type ApiSmtpEntry, type SmtpForm, type SmtpFormErrors, type ProviderKey,
} from "../_data";
import Modal from "@/components/Modal";

interface Props {
  entry:   ApiSmtpEntry | null;  // null = add mode
  saving:  boolean;
  onClose: () => void;
  onSave:  (form: SmtpForm) => Promise<void>;
}

export default function SmtpModal({ entry, saving, onClose, onSave }: Props) {
  const isAddMode = entry === null;

  const [form, setForm] = useState<SmtpForm>(
    isAddMode ? { ...EMPTY_SMTP_FORM } : apiEntryToForm(entry)
  );
  const [errors, setErrors] = useState<SmtpFormErrors>({});
  const [step, setStep] = useState<"provider" | "details">(isAddMode ? "provider" : "details");
  // "gmail" is just the initial highlight in add mode — nothing is written
  // into `form` until the user actually clicks a card.
  const [providerKey, setProviderKey] = useState<ProviderKey>(
    () => isAddMode ? "gmail" : inferProviderKey(entry)
  );

  const provider = PROVIDER_CONFIG[providerKey];
  const isLocal  = form.smtpType === "local";

  function patch(p: Partial<SmtpForm>) { setForm(prev => ({ ...prev, ...p })); }
  function clearErr(k: keyof SmtpForm) { setErrors(prev => ({ ...prev, [k]: undefined })); }

  function selectProvider(key: ProviderKey) {
    setProviderKey(key);
    setForm(f => applyProvider(f, key));
    setErrors({});
    setStep("details");
  }

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
        step === "provider" ? (
          <button className="btn btn-ghost" onClick={onClose} disabled={saving} suppressHydrationWarning>Cancel</button>
        ) : (
          <>
            <button className="btn btn-ghost" onClick={() => setStep("provider")} disabled={saving} suppressHydrationWarning>
              <i className="ti ti-arrow-left" /> Back
            </button>
            <button className="btn btn-ghost" onClick={onClose} disabled={saving} suppressHydrationWarning>Cancel</button>
            <button className="btn btn-filled" onClick={handleSave} disabled={saving} suppressHydrationWarning>
              {saving
                ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
                : <><i className="ti ti-device-floppy" /> {isAddMode ? "Add Configuration" : "Save Changes"}</>
              }
            </button>
          </>
        )
      }
    >

      {step === "provider" ? (
        /* ── Step 1: pick a mail provider ─────────────────────────────── */
        <div>
          <p style={{ fontSize: 13, color: "var(--on-variant)", marginTop: 0, marginBottom: 16 }}>
            Choose a mail provider — the fields you need will be filled in for you where possible.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {PROVIDER_LIST.map(p => {
              const selected = providerKey === p.key;
              return (
                <button
                  key={p.key}
                  type="button"
                  onClick={() => selectProvider(p.key)}
                  className={[
                    "relative text-left p-3.5 rounded-xl border-2 transition-all",
                    selected ? "shadow-md" : "border-[var(--outline-v)] hover:border-[var(--outline)] bg-[var(--bg-low)] hover:bg-[var(--surface)]",
                  ].join(" ")}
                  style={selected ? { borderColor: p.color, background: p.bg } : {}}
                  suppressHydrationWarning
                >
                  {selected && (
                    <span
                      className="absolute top-2.5 right-2.5 w-4 h-4 rounded-full flex items-center justify-center"
                      style={{ background: p.color }}
                    >
                      <i className="ti ti-check text-white" style={{ fontSize: 9 }} />
                    </span>
                  )}
                  <div className="w-8 h-8 rounded-xl flex items-center justify-center mb-2.5" style={{ background: p.bg }}>
                    <i className={`ti ${p.icon} text-sm`} style={{ color: p.color }} />
                  </div>
                  <div className="text-xs font-bold text-[var(--on-bg)] mb-0.5">{p.label}</div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)", lineHeight: 1.4 }}>{p.note}</div>
                </button>
              );
            })}
          </div>
        </div>
      ) : (
        /* ── Step 2: provider-specific details ────────────────────────── */
        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <div className="w-7 h-7 rounded-lg flex items-center justify-center" style={{ background: provider.bg }}>
                <i className={`ti ${provider.icon}`} style={{ color: provider.color, fontSize: 14 }} />
              </div>
              <span style={{ fontSize: 13, fontWeight: 600 }}>{provider.label}</span>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={() => setStep("provider")} suppressHydrationWarning>
              <i className="ti ti-arrow-left" /> Change provider
            </button>
          </div>

          <div className="smtp-form-grid">

            {/* Configuration Name — full width */}
            <div className="field-group" style={{ gridColumn: "1 / -1" }}>
              <label className="field-label">Configuration Name <span style={{ color: "var(--error)" }}>*</span></label>
              <input className="field-input"
                placeholder={isLocal ? "e.g. Gmail SMTP, Zoho Mail" : "e.g. Corporate Mail Server"}
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
                    value={form.host}
                    disabled={provider.locked}
                    onChange={e => { patch({ host: e.target.value }); clearErr("host"); }}
                    suppressHydrationWarning />
                  {provider.locked && (
                    <span style={{ fontSize: 11, color: "var(--on-variant)" }}>Fixed for {provider.label} — not editable</span>
                  )}
                  {errors.host && <span className="field-error">{errors.host}</span>}
                  {provider.helpText && (
                    <span style={{ fontSize: 11, color: "var(--on-variant)", display: "block", marginTop: 4 }}>{provider.helpText}</span>
                  )}
                </div>

                {/* Port + TLS */}
                <div className="field-group">
                  <label className="field-label">Port</label>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <input className="field-input" type="number" value={form.port}
                      disabled={provider.locked}
                      onChange={e => patch({ port: Number(e.target.value) })}
                      style={{ flex: 1 }}
                      suppressHydrationWarning />
                    <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, cursor: provider.locked ? "default" : "pointer", whiteSpace: "nowrap" }}>
                      <input type="checkbox" checked={form.useTls}
                        disabled={provider.locked}
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
              <input className="field-input" placeholder="Aira HRMS"
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
              <select className="field-input field-select" value={form.priority}
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
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </Modal>
  );
}

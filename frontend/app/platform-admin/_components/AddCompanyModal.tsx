"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { ALL_MODULES, MODULE_LABELS } from "@/types/platformAdmin";
import type { CreateCompanyResult, ModuleKey } from "@/types/platformAdmin";

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export default function AddCompanyModal({ onClose, onCreated }: Props) {
  const [companyCode, setCompanyCode] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [adminEmail,  setAdminEmail]  = useState("");
  const [modules,     setModules]     = useState<ModuleKey[]>(ALL_MODULES);
  const [saving,      setSaving]      = useState(false);
  const [error,       setError]       = useState("");
  const [result,      setResult]      = useState<CreateCompanyResult | null>(null);
  const [copied,      setCopied]      = useState(false);

  function toggleModule(key: ModuleKey) {
    setModules(prev => prev.includes(key) ? prev.filter(m => m !== key) : [...prev, key]);
  }

  async function handleCreate() {
    setError("");
    if (!companyCode.trim() || !companyName.trim() || !adminEmail.trim()) {
      setError("Company code, company name, and admin email are all required.");
      return;
    }
    setSaving(true);
    try {
      const { data } = await platformAdminApi.post<{ data: CreateCompanyResult }>(
        API.platformAdmin.companies.list,
        { company_code: companyCode.trim(), company_name: companyName.trim(), admin_email: adminEmail.trim(), modules },
        // Provisioning a new company runs a full schema + migration replay
        // synchronously (see backend apps/tenants/services.py) — confirmed
        // to take several minutes, not seconds, so this one call needs a
        // much longer timeout than platformAdminApi's 15s instance default.
        { timeout: 360000 },
      );
      setResult(data.data);
      onCreated();
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Company creation failed.";
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  function copyPassword() {
    if (!result) return;
    navigator.clipboard.writeText(result.password).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  if (result) {
    return (
      <Modal title="Company created" onClose={onClose} maxWidth={460}
        footer={<button className="btn btn-filled" onClick={onClose} suppressHydrationWarning>Done</button>}>
        <div className="alert alert-warn mb-16">
          <i className="ti ti-alert-triangle" />
          <div>This password is shown once and is not stored anywhere else. Copy it now and share it with the company&apos;s admin.</div>
        </div>
        <div className="field-group" style={{ marginBottom: 12 }}>
          <span className="field-label">Company code</span>
          <div className="field-static">{result.client.company_code}</div>
        </div>
        <div className="field-group" style={{ marginBottom: 12 }}>
          <span className="field-label">Admin login email</span>
          <div className="field-static">{adminEmail.trim()}</div>
        </div>
        <div className="field-group">
          <span className="field-label">Temporary password</span>
          <div style={{ display: "flex", gap: 8 }}>
            <div className="field-static" style={{ fontFamily: "monospace", flex: 1 }}>{result.password}</div>
            <button type="button" className="btn btn-ghost btn-sm" onClick={copyPassword} suppressHydrationWarning>
              <i className={`ti ${copied ? "ti-check" : "ti-copy"}`} /> {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
      </Modal>
    );
  }

  return (
    <Modal
      title="Add company"
      onClose={onClose}
      maxWidth={520}
      closeDisabled={saving}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={saving} suppressHydrationWarning>Cancel</button>
          <button className="btn btn-filled" onClick={handleCreate} disabled={saving} suppressHydrationWarning>
            {saving ? (<><i className="ti ti-loader-2 spin" /> Creating… (can take a few minutes)</>) : "Create company"}
          </button>
        </>
      }
    >
      {error && (
        <div className="alert alert-warn mb-16">
          <i className="ti ti-alert-triangle" />
          <div>{error}</div>
        </div>
      )}

      <div className="form-row cols-2">
        <div className="field-group">
          <label className="field-label" htmlFor="ac-code">Company code</label>
          <input id="ac-code" className="field-input" placeholder="e.g. ACME2026" value={companyCode}
            onChange={e => setCompanyCode(e.target.value)} disabled={saving} suppressHydrationWarning />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="ac-name">Company name</label>
          <input id="ac-name" className="field-input" placeholder="e.g. Acme Corp" value={companyName}
            onChange={e => setCompanyName(e.target.value)} disabled={saving} suppressHydrationWarning />
        </div>
      </div>

      <div className="field-group" style={{ marginBottom: 16 }}>
        <label className="field-label" htmlFor="ac-email">First admin&apos;s email</label>
        <input id="ac-email" type="email" className="field-input" placeholder="admin@acme.com" value={adminEmail}
          onChange={e => setAdminEmail(e.target.value)} disabled={saving} suppressHydrationWarning />
      </div>

      <div className="field-group">
        <span className="field-label">Modules enabled for this company</span>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 16px", marginTop: 6 }}>
          {ALL_MODULES.map(key => (
            <label key={key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: saving ? "default" : "pointer" }}>
              <input type="checkbox" checked={modules.includes(key)} onChange={() => toggleModule(key)} disabled={saving} suppressHydrationWarning />
              {MODULE_LABELS[key]}
            </label>
          ))}
        </div>
      </div>
    </Modal>
  );
}

"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { ALL_MODULES, MODULE_LABELS } from "@/types/platformAdmin";
import type { ModuleKey } from "@/types/platformAdmin";

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
  const [started,     setStarted]     = useState(false);

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
      // Returns almost immediately — provisioning itself now runs in a
      // detached background process (see backend apps/tenants/services.py),
      // not inline in this request, specifically so a web-server restart
      // can't kill it partway through. The company shows as "Pending" in
      // the table and flips to "Active" (with a "View credentials" button)
      // once the background process finishes, usually within a few minutes.
      await platformAdminApi.post(
        API.platformAdmin.companies.list,
        { company_code: companyCode.trim(), company_name: companyName.trim(), admin_email: adminEmail.trim(), modules },
      );
      setStarted(true);
      onCreated();
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Company creation failed.";
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  if (started) {
    return (
      <Modal title="Company creation started" onClose={onClose} maxWidth={460}
        footer={<button className="btn btn-filled" onClick={onClose} suppressHydrationWarning>Done</button>}>
        <div className="alert alert-success mb-16">
          <i className="ti ti-check" />
          <div>
            <strong>{companyCode.trim()}</strong> is being set up now — this runs in the background
            and takes a few minutes. It will show as <strong>Active</strong> in the companies list once
            ready, with a &quot;View credentials&quot; button to see the admin login password (shown once).
          </div>
        </div>
        <p style={{ fontSize: 13, color: "var(--on-variant)" }}>
          You can safely close this and keep using the dashboard — no need to wait here.
        </p>
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
            {saving ? (<><i className="ti ti-loader-2 spin" /> Starting…</>) : "Create company"}
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

"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { ALL_MODULES, MODULE_LABELS } from "@/types/platformAdmin";
import type { Company, ModuleKey } from "@/types/platformAdmin";

interface Props {
  company: Company;
  onClose: () => void;
  onSaved: () => void;
}

export default function EditModulesModal({ company, onClose, onSaved }: Props) {
  const [modules, setModules] = useState<ModuleKey[]>(company.enabled_modules);
  const [saving,  setSaving]  = useState(false);
  const [error,   setError]   = useState("");

  function toggleModule(key: ModuleKey) {
    setModules(prev => prev.includes(key) ? prev.filter(m => m !== key) : [...prev, key]);
  }

  async function handleSave() {
    setError("");
    setSaving(true);
    try {
      await platformAdminApi.patch(API.platformAdmin.companies.detail(company.id), { enabled_modules: modules });
      onSaved();
      onClose();
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to update modules.";
      setError(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      title={`Edit modules — ${company.company_name}`}
      onClose={onClose}
      maxWidth={480}
      closeDisabled={saving}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={saving} suppressHydrationWarning>Cancel</button>
          <button className="btn btn-filled" onClick={handleSave} disabled={saving} suppressHydrationWarning>
            {saving ? (<><i className="ti ti-loader-2 spin" /> Saving…</>) : "Save changes"}
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

      <p style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 12 }}>
        Changes take effect immediately — the company&apos;s dashboard will show or hide these
        modules the next time each user loads the app.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 16px" }}>
        {ALL_MODULES.map(key => (
          <label key={key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: saving ? "default" : "pointer" }}>
            <input type="checkbox" checked={modules.includes(key)} onChange={() => toggleModule(key)} disabled={saving} suppressHydrationWarning />
            {MODULE_LABELS[key]}
          </label>
        ))}
      </div>
    </Modal>
  );
}

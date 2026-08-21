"use client";

import { useState } from "react";
import Modal from "@/components/Modal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";

interface Props {
  onClose: () => void;
  onCreated: () => void;
}

export default function AddCompanyModal({ onClose, onCreated }: Props) {
  const [companyCode, setCompanyCode] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [adminEmail,  setAdminEmail]  = useState("");
  const [saving,      setSaving]      = useState(false);
  const [error,       setError]       = useState("");
  const [started,     setStarted]     = useState(false);

  // Account-management context, not provisioning input — all optional, so
  // none of it blocks creation, but shown directly rather than collapsed.
  const [contactName,    setContactName]    = useState("");
  const [contactPhone,   setContactPhone]   = useState("");
  const [address,        setAddress]        = useState("");
  const [gstin,          setGstin]          = useState("");
  const [employeeCount,  setEmployeeCount]  = useState("");
  const [contractStart,  setContractStart]  = useState("");

  async function handleCreate() {
    setError("");
    if (!companyCode.trim() || !companyName.trim() || !adminEmail.trim()) {
      setError("Company code, company name, and admin email are all required.");
      return;
    }
    setSaving(true);
    try {
      // Every company gets every module — omitting `modules` entirely lets
      // the backend default to the full set (apps.tenants.services
      // _validate_new_company) instead of asking here. Returns almost
      // immediately — provisioning itself runs as a background Celery task
      // (see backend apps/tenants/tasks.py), not inline in this request, so
      // a web-server restart can't kill it partway through. The company
      // shows as "Pending" in the table and flips to "Active" (with a
      // "View credentials" button) once the task finishes.
      await platformAdminApi.post(
        API.platformAdmin.companies.list,
        {
          company_code: companyCode.trim(), company_name: companyName.trim(), admin_email: adminEmail.trim(),
          contact_name: contactName.trim(), contact_phone: contactPhone.trim(),
          address: address.trim(), gstin: gstin.trim(),
          expected_employee_count: employeeCount.trim() ? Number(employeeCount) : null,
          contract_start_date: contractStart || null,
        },
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
      maxWidth={480}
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

      <div className="field-group">
        <label className="field-label" htmlFor="ac-email">First admin&apos;s email</label>
        <input id="ac-email" type="email" className="field-input" placeholder="admin@acme.com" value={adminEmail}
          onChange={e => setAdminEmail(e.target.value)} disabled={saving} suppressHydrationWarning />
      </div>

      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label" htmlFor="ac-contact-name">Contact name</label>
          <input id="ac-contact-name" className="field-input" placeholder="e.g. Jane Doe" value={contactName}
            onChange={e => setContactName(e.target.value)} disabled={saving} suppressHydrationWarning />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="ac-contact-phone">Contact phone</label>
          <input id="ac-contact-phone" type="tel" className="field-input" placeholder="e.g. +91 98765 43210" value={contactPhone}
            onChange={e => setContactPhone(e.target.value)} disabled={saving} suppressHydrationWarning />
        </div>
      </div>

      <div className="field-group mb-16">
        <label className="field-label" htmlFor="ac-address">Address</label>
        <textarea id="ac-address" className="field-input" rows={2} placeholder="Registered office address" value={address}
          onChange={e => setAddress(e.target.value)} disabled={saving} suppressHydrationWarning />
      </div>

      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label" htmlFor="ac-gstin">GSTIN</label>
          <input id="ac-gstin" className="field-input" placeholder="e.g. 22AAAAA0000A1Z5" value={gstin}
            onChange={e => setGstin(e.target.value.toUpperCase())} disabled={saving} suppressHydrationWarning />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="ac-employee-count">Expected employee count</label>
          <input id="ac-employee-count" type="number" min={1} className="field-input" placeholder="e.g. 50" value={employeeCount}
            onChange={e => setEmployeeCount(e.target.value)} disabled={saving} suppressHydrationWarning />
        </div>
      </div>

      <div className="field-group">
        <label className="field-label" htmlFor="ac-contract-start">Contract start date</label>
        <input id="ac-contract-start" type="date" className="field-input" value={contractStart}
          onChange={e => setContractStart(e.target.value)} disabled={saving} suppressHydrationWarning />
      </div>
    </Modal>
  );
}

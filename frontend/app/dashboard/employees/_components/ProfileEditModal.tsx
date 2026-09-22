"use client";

// Direct self-edit for the fields any employee (or admin editing their own
// record) is allowed to change without HR approval: phone, current/
// permanent address, emergency contact. Replaces the old HR-ticket
// "Request profile correction" flow on the Profile pages themselves —
// that flow still exists separately under My Requests
// (EmployeeRequestModal.tsx -> ProfileCorrectionModal.tsx) for anyone who
// wants a tracked request instead, but the Profile page itself now saves
// straight to the record, same as PATCH API.employees.me always accepted.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { STATES } from "@/app/dashboard/settings/company/_data";

interface ProfileForEdit {
  phone: string | null;
  profile: {
    current_address?: string | null;
    current_address_line2?: string | null;
    current_village?: string | null;
    current_district?: string | null;
    current_state?: string | null;
    current_pin_code?: string | null;
    permanent_address?: string | null;
    permanent_address_line2?: string | null;
    permanent_village?: string | null;
    permanent_district?: string | null;
    permanent_state?: string | null;
    permanent_pin_code?: string | null;
    permanent_same_as_current?: boolean;
    emergency_name?: string | null;
    emergency_relationship?: string | null;
    emergency_phone?: string | null;
    emergency_email?: string | null;
  } | null;
}

interface Props {
  profile: ProfileForEdit;
  onClose: () => void;
  onSaved: () => void;
}

interface FormState {
  phone: string;
  current_address: string;
  current_address_line2: string;
  current_village: string;
  current_district: string;
  current_state: string;
  current_pin_code: string;
  permanent_same_as_current: boolean;
  permanent_address: string;
  permanent_address_line2: string;
  permanent_village: string;
  permanent_district: string;
  permanent_state: string;
  permanent_pin_code: string;
  emergency_name: string;
  emergency_relationship: string;
  emergency_phone: string;
  emergency_email: string;
}

function buildInitialForm(profile: ProfileForEdit): FormState {
  const p = profile.profile;
  return {
    phone: profile.phone ?? "",
    current_address: p?.current_address ?? "",
    current_address_line2: p?.current_address_line2 ?? "",
    current_village: p?.current_village ?? "",
    current_district: p?.current_district ?? "",
    current_state: p?.current_state ?? "",
    current_pin_code: p?.current_pin_code ?? "",
    permanent_same_as_current: Boolean(p?.permanent_same_as_current),
    permanent_address: p?.permanent_address ?? "",
    permanent_address_line2: p?.permanent_address_line2 ?? "",
    permanent_village: p?.permanent_village ?? "",
    permanent_district: p?.permanent_district ?? "",
    permanent_state: p?.permanent_state ?? "",
    permanent_pin_code: p?.permanent_pin_code ?? "",
    emergency_name: p?.emergency_name ?? "",
    emergency_relationship: p?.emergency_relationship ?? "",
    emergency_phone: p?.emergency_phone ?? "",
    emergency_email: p?.emergency_email ?? "",
  };
}

export default function ProfileEditModal({ profile, onClose, onSaved }: Props) {
  const [form, setForm] = useState<FormState>(() => buildInitialForm(profile));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function field<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm(prev => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await clientApi.patch(API.employees.me, {
        phone: form.phone,
        current_address: form.current_address,
        current_address_line2: form.current_address_line2,
        current_village: form.current_village,
        current_district: form.current_district,
        current_state: form.current_state,
        current_pin_code: form.current_pin_code,
        permanent_same_as_current: form.permanent_same_as_current,
        permanent_address: form.permanent_address,
        permanent_address_line2: form.permanent_address_line2,
        permanent_village: form.permanent_village,
        permanent_district: form.permanent_district,
        permanent_state: form.permanent_state,
        permanent_pin_code: form.permanent_pin_code,
        emergency_name: form.emergency_name,
        emergency_relationship: form.emergency_relationship,
        emergency_phone: form.emergency_phone,
        emergency_email: form.emergency_email,
      });
      onSaved();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg ?? "Failed to update profile.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="drawer-overlay open" onClick={onClose}>
      <div className="drawer open" style={{ maxWidth: 560 }} onClick={e => e.stopPropagation()}>
        <div className="drawer-header">
          <div className="drawer-title">Edit my details</div>
          <button className="drawer-close" onClick={onClose}><i className="ti ti-x" /></button>
        </div>

        <div className="drawer-body">
          {error && <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> {error}</div>}

          <div style={{ fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--on-variant)", marginBottom: 10 }}>
            Contact
          </div>
          <div className="field-group">
            <label className="field-label">Mobile number</label>
            <input className="field-input" value={form.phone} onChange={e => field("phone", e.target.value)} placeholder="+91 98765 43210" />
          </div>

          <div style={{ fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--on-variant)", margin: "18px 0 10px" }}>
            Current Address
          </div>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Address Line 1</label>
              <input className="field-input" value={form.current_address} onChange={e => field("current_address", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Address Line 2</label>
              <input className="field-input" value={form.current_address_line2} onChange={e => field("current_address_line2", e.target.value)} />
            </div>
          </div>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Village / Town / Area</label>
              <input className="field-input" value={form.current_village} onChange={e => field("current_village", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">District</label>
              <input className="field-input" value={form.current_district} onChange={e => field("current_district", e.target.value)} />
            </div>
          </div>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">State</label>
              <select className="field-input field-select" value={form.current_state} onChange={e => field("current_state", e.target.value)}>
                <option value="">Select…</option>
                {STATES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">PIN Code</label>
              <input className="field-input" value={form.current_pin_code}
                onChange={e => field("current_pin_code", e.target.value.replace(/\D/g, "").slice(0, 6))}
                maxLength={6} inputMode="numeric" />
            </div>
          </div>

          <label className="module-check" style={{ margin: "4px 0 12px" }}>
            <input type="checkbox" checked={form.permanent_same_as_current}
              onChange={e => field("permanent_same_as_current", e.target.checked)} />
            <span>Permanent address is the same as current address</span>
          </label>

          {!form.permanent_same_as_current && (
            <>
              <div style={{ fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--on-variant)", margin: "8px 0 10px" }}>
                Permanent Address
              </div>
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Address Line 1</label>
                  <input className="field-input" value={form.permanent_address} onChange={e => field("permanent_address", e.target.value)} />
                </div>
                <div className="field-group">
                  <label className="field-label">Address Line 2</label>
                  <input className="field-input" value={form.permanent_address_line2} onChange={e => field("permanent_address_line2", e.target.value)} />
                </div>
              </div>
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Village / Town / Area</label>
                  <input className="field-input" value={form.permanent_village} onChange={e => field("permanent_village", e.target.value)} />
                </div>
                <div className="field-group">
                  <label className="field-label">District</label>
                  <input className="field-input" value={form.permanent_district} onChange={e => field("permanent_district", e.target.value)} />
                </div>
              </div>
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">State</label>
                  <select className="field-input field-select" value={form.permanent_state} onChange={e => field("permanent_state", e.target.value)}>
                    <option value="">Select…</option>
                    {STATES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div className="field-group">
                  <label className="field-label">PIN Code</label>
                  <input className="field-input" value={form.permanent_pin_code}
                    onChange={e => field("permanent_pin_code", e.target.value.replace(/\D/g, "").slice(0, 6))}
                    maxLength={6} inputMode="numeric" />
                </div>
              </div>
            </>
          )}

          <div style={{ fontWeight: 700, fontSize: 12, textTransform: "uppercase", letterSpacing: ".04em", color: "var(--on-variant)", margin: "18px 0 10px" }}>
            Emergency Contact
          </div>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Name</label>
              <input className="field-input" value={form.emergency_name} onChange={e => field("emergency_name", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Relationship</label>
              <input className="field-input" value={form.emergency_relationship} onChange={e => field("emergency_relationship", e.target.value)} />
            </div>
          </div>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Phone</label>
              <input className="field-input" value={form.emergency_phone} onChange={e => field("emergency_phone", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Email</label>
              <input className="field-input" value={form.emergency_email} onChange={e => field("emergency_email", e.target.value)} />
            </div>
          </div>
        </div>

        <div className="drawer-footer">
          <button className="btn btn-ghost" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-filled" onClick={handleSave} disabled={saving}>
            {saving ? <><i className="ti ti-loader-2 spin" /> Saving…</> : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

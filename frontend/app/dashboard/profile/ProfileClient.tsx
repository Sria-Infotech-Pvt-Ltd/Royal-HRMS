"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { SessionPayload } from "@/lib/session";
import ChangePasswordForm from "./ChangePasswordForm";

interface ProfileData {
  full_name:       string;
  email:           string;
  phone:           string | null;
  employee_id:     string;
  department:      string;
  designation:     string;
  branch:          string;
  role_display:    string;
  date_of_joining: string | null;
  profile: {
    current_address:        string | null;
    permanent_address:      string | null;
    account_number:         string | null;
    ifsc_code:              string | null;
    bank_name:              string | null;
    account_holder_name:    string | null;
    emergency_name:         string | null;
    emergency_relationship: string | null;
    emergency_phone:        string | null;
    emergency_email:        string | null;
  } | null;
}

interface DocumentItem {
  id:                    number;
  document_type_display: string;
  file:                  string;
}

interface EditableFields {
  phone:                  string;
  current_address:        string;
  permanent_address:      string;
  emergency_name:         string;
  emergency_relationship: string;
  emergency_phone:        string;
  emergency_email:        string;
}

const EMPTY: EditableFields = {
  phone: "", current_address: "", permanent_address: "",
  emergency_name: "", emergency_relationship: "", emergency_phone: "", emergency_email: "",
};

function initials(name: string) {
  return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
}

export default function ProfileClient({ session }: { session: SessionPayload }) {
  const { data: profile, loading } = useFetch<ProfileData>(API.employees.me);
  const { data: docs }             = useFetch<DocumentItem[]>(API.onboarding.documents);

  const [form,   setForm]   = useState<EditableFields>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [toast,  setToast]  = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => {
    if (!profile) return;
    setForm({
      phone:                  profile.phone ?? "",
      current_address:        profile.profile?.current_address ?? "",
      permanent_address:      profile.profile?.permanent_address ?? "",
      emergency_name:         profile.profile?.emergency_name ?? "",
      emergency_relationship: profile.profile?.emergency_relationship ?? "",
      emergency_phone:        profile.profile?.emergency_phone ?? "",
      emergency_email:        profile.profile?.emergency_email ?? "",
    });
  }, [profile]);

  function field(key: keyof EditableFields, value: string) {
    setForm(prev => ({ ...prev, [key]: value }));
  }

  function showToast(msg: string, ok = true) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  }

  async function handleSave() {
    setSaving(true);
    try {
      await clientApi.patch(API.employees.me, form);
      showToast("Profile updated successfully.");
    } catch {
      showToast("Failed to update profile.", false);
    } finally {
      setSaving(false);
    }
  }

  const ini = initials(session.name);

  return (
    <div>
      {toast && (
        <div style={{ position: "fixed", bottom: 24, right: 24, zIndex: 9999 }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "12px 18px", background: "white", borderRadius: "var(--radius)",
            boxShadow: "var(--shadow-md)", fontSize: 14, fontWeight: 500,
            borderLeft: `3px solid var(--${toast.ok ? "success" : "error"})`,
            color: `var(--${toast.ok ? "success" : "error"})`,
          }}>
            <i className={`ti ${toast.ok ? "ti-circle-check" : "ti-alert-circle"}`} />
            {toast.msg}
          </div>
        </div>
      )}

      <div className="page-header">
        <div>
          <div className="page-title">My Profile</div>
          <div className="page-sub">View and update your personal information</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={handleSave} disabled={saving || loading} suppressHydrationWarning>
            {saving
              ? <><i className="ti ti-loader-2 spin" /> Saving…</>
              : <><i className="ti ti-device-floppy" /> Save Changes</>
            }
          </button>
        </div>
      </div>

      <div className="grid-2">

        {/* ─── LEFT COLUMN ─── */}
        <div>
          <div className="card mb-16">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-user-circle" />Personal Information</span>
            </div>
            <div className="card-body">
              <div style={{ display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
                <div style={{
                  width: 64, height: 64, borderRadius: "50%", flexShrink: 0,
                  background: "var(--primary)", color: "white",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 22, fontWeight: 700,
                }}>{ini}</div>
                <div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "var(--on-bg)" }}>
                    {loading ? "—" : (profile?.full_name ?? session.name)}
                  </div>
                  <div style={{ fontSize: 13, color: "var(--on-variant)", marginTop: 2 }}>
                    {profile?.role_display ?? session.role}
                  </div>
                  {profile?.employee_id && (
                    <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                      {profile.employee_id}
                    </div>
                  )}
                </div>
              </div>

              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Full Name</label>
                  <input className="field-input" value={loading ? "" : (profile?.full_name ?? "")} disabled suppressHydrationWarning />
                </div>
                <div className="field-group">
                  <label className="field-label">Email</label>
                  <input className="field-input" value={loading ? "" : (profile?.email ?? session.email)} disabled suppressHydrationWarning />
                </div>
              </div>
              <div className="field-group">
                <label className="field-label">Phone</label>
                <input className="field-input" value={form.phone}
                  onChange={e => field("phone", e.target.value)}
                  placeholder="+91 98765 43210" suppressHydrationWarning />
              </div>
            </div>
          </div>

          <div className="card mb-16">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-map-pin" />Address</span>
            </div>
            <div className="card-body">
              <div className="field-group">
                <label className="field-label">Current Address</label>
                <textarea className="field-input" rows={2} value={form.current_address}
                  onChange={e => field("current_address", e.target.value)}
                  placeholder="Current residential address" style={{ resize: "vertical" }} suppressHydrationWarning />
              </div>
              <div className="field-group">
                <label className="field-label">Permanent Address</label>
                <textarea className="field-input" rows={2} value={form.permanent_address}
                  onChange={e => field("permanent_address", e.target.value)}
                  placeholder="Permanent / home town address" style={{ resize: "vertical" }} suppressHydrationWarning />
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-lock" />Change Password</span>
            </div>
            <div className="card-body">
              <ChangePasswordForm />
            </div>
          </div>
        </div>

        {/* ─── RIGHT COLUMN ─── */}
        <div>
          <div className="card mb-16">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-briefcase" />Work Information</span>
            </div>
            <div className="card-body">
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Employee ID</label>
                  <input className="field-input" value={loading ? "" : (profile?.employee_id ?? "—")} disabled suppressHydrationWarning />
                </div>
                <div className="field-group">
                  <label className="field-label">Department</label>
                  <input className="field-input" value={loading ? "" : (profile?.department ?? "—")} disabled suppressHydrationWarning />
                </div>
              </div>
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Designation</label>
                  <input className="field-input" value={loading ? "" : (profile?.designation ?? "—")} disabled suppressHydrationWarning />
                </div>
                <div className="field-group">
                  <label className="field-label">Branch</label>
                  <input className="field-input" value={loading ? "" : (profile?.branch ?? "—")} disabled suppressHydrationWarning />
                </div>
              </div>
              <div className="field-group">
                <label className="field-label">Date of Joining</label>
                <input className="field-input" value={loading ? "" : (profile?.date_of_joining ?? "—")} disabled suppressHydrationWarning />
              </div>
            </div>
          </div>

          <div className="card mb-16">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-phone" />Emergency Contact</span>
            </div>
            <div className="card-body">
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Name</label>
                  <input className="field-input" value={form.emergency_name}
                    onChange={e => field("emergency_name", e.target.value)}
                    placeholder="Contact name" suppressHydrationWarning />
                </div>
                <div className="field-group">
                  <label className="field-label">Relationship</label>
                  <input className="field-input" value={form.emergency_relationship}
                    onChange={e => field("emergency_relationship", e.target.value)}
                    placeholder="e.g. Spouse, Parent" suppressHydrationWarning />
                </div>
              </div>
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Phone</label>
                  <input className="field-input" value={form.emergency_phone}
                    onChange={e => field("emergency_phone", e.target.value)}
                    placeholder="+91 98765 43210" suppressHydrationWarning />
                </div>
                <div className="field-group">
                  <label className="field-label">Email</label>
                  <input className="field-input" value={form.emergency_email}
                    onChange={e => field("emergency_email", e.target.value)}
                    placeholder="email@example.com" suppressHydrationWarning />
                </div>
              </div>
            </div>
          </div>

          <div className="card mb-16">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-building-bank" />Bank Details</span>
              <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "var(--on-variant)" }}>
                <i className="ti ti-lock" style={{ fontSize: 11 }} /> Contact HR to update
              </div>
            </div>
            <div className="card-body">
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Bank Name</label>
                  <input className="field-input" value={loading ? "" : (profile?.profile?.bank_name ?? "")} disabled placeholder="—" suppressHydrationWarning />
                </div>
                <div className="field-group">
                  <label className="field-label">Account Number</label>
                  <input className="field-input" value={loading ? "" : (profile?.profile?.account_number ?? "")} disabled placeholder="—" suppressHydrationWarning />
                </div>
              </div>
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">IFSC Code</label>
                  <input className="field-input" value={loading ? "" : (profile?.profile?.ifsc_code ?? "")} disabled placeholder="—" suppressHydrationWarning />
                </div>
                <div className="field-group">
                  <label className="field-label">Account Holder</label>
                  <input className="field-input" value={loading ? "" : (profile?.profile?.account_holder_name ?? "")} disabled placeholder="—" suppressHydrationWarning />
                </div>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-file-description" />Documents</span>
            </div>
            <div className="card-body" style={{ padding: 0 }}>
              {(!docs || docs.length === 0) ? (
                <div style={{ padding: "16px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
                  No documents uploaded yet.
                </div>
              ) : docs.map((doc, i) => (
                <div key={doc.id} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "10px 16px",
                  borderBottom: i < docs.length - 1 ? "1px solid var(--bg-high)" : "none",
                }}>
                  <i className="ti ti-file-check" style={{ color: "var(--success)" }} />
                  <span style={{ flex: 1, fontSize: 13, color: "var(--on-bg)" }}>{doc.document_type_display}</span>
                  <a href={doc.file} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm">
                    <i className="ti ti-eye" />
                  </a>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

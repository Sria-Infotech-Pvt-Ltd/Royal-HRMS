"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { SessionPayload } from "@/lib/session";
import ChangePasswordForm from "./ChangePasswordForm";

interface ProfileSub {
  date_of_birth:          string | null;
  gender:                 string | null;
  marital_status:         string | null;
  father_name:            string | null;
  blood_group:            string | null;
  current_address:        string | null;
  permanent_address:      string | null;
  highest_qualification:  string | null;
  institution:            string | null;
  year_of_passing:        number | null;
  specialization:         string | null;
  total_experience_years: string | null;
  previous_employer:      string | null;
  previous_designation:   string | null;
  leaving_reason:         string | null;
  account_number:         string | null;
  ifsc_code:              string | null;
  bank_name:              string | null;
  bank_branch_name:       string | null;
  account_holder_name:    string | null;
  account_type:           string | null;
  emergency_name:         string | null;
  emergency_relationship: string | null;
  emergency_phone:        string | null;
  emergency_email:        string | null;
}

interface ProfileData {
  full_name:         string;
  email:             string;
  phone:             string | null;
  employee_id:       string;
  department:        string;
  designation:       string;
  branch:            string;
  role_display:      string;
  date_of_joining:   string | null;
  date_joined:       string | null;
  onboarding_status: string | null;
  assessment_status: string | null;
  profile:           ProfileSub | null;
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

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

function val(v: string | number | null | undefined): string {
  if (v === null || v === undefined || v === "") return "—";
  return String(v);
}

function ReadField({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="field-group">
      <label className="field-label">{label}</label>
      <input className="field-input" value={val(value)} disabled suppressHydrationWarning />
    </div>
  );
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

  const ini        = initials(session.name);
  const p          = profile?.profile ?? null;
  const joinedDate = fmtDate(profile?.date_of_joining ?? profile?.date_joined);

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

      {/* ── Avatar + name banner ── */}
      <div className="card mb-16" style={{ padding: "20px 24px", display: "flex", alignItems: "center", gap: 20 }}>
        <div style={{
          width: 72, height: 72, borderRadius: "50%", flexShrink: 0,
          background: "var(--primary)", color: "white",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 26, fontWeight: 700,
        }}>{ini}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 20, fontWeight: 700, color: "var(--on-bg)" }}>
            {loading ? "—" : (profile?.full_name ?? session.name)}
          </div>
          <div style={{ fontSize: 13, color: "var(--on-variant)", marginTop: 3 }}>
            {profile?.designation && profile?.department
              ? `${profile.designation} · ${profile.department}`
              : (profile?.role_display ?? session.role)}
          </div>
          <div style={{ display: "flex", gap: 16, marginTop: 8, flexWrap: "wrap" }}>
            {profile?.employee_id && (
              <span style={{ fontSize: 11, background: "rgba(30,78,140,0.1)", color: "var(--primary)", padding: "2px 10px", borderRadius: 20, fontWeight: 600 }}>
                {profile.employee_id}
              </span>
            )}
            {profile?.branch && (
              <span style={{ fontSize: 12, color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 4 }}>
                <i className="ti ti-building" style={{ fontSize: 12 }} />{profile.branch}
              </span>
            )}
            {joinedDate !== "—" && (
              <span style={{ fontSize: 12, color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 4 }}>
                <i className="ti ti-calendar" style={{ fontSize: 12 }} />Joined {joinedDate}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid-2">

        {/* ─── LEFT COLUMN ─── */}
        <div>

          {/* Personal Information */}
          <div className="card mb-16">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-user-circle" />Personal Information</span>
            </div>
            <div className="card-body">
              <div className="form-row cols-2">
                <ReadField label="Full Name"  value={profile?.full_name} />
                <ReadField label="Email"      value={profile?.email ?? session.email} />
              </div>
              <div className="field-group">
                <label className="field-label">Phone</label>
                <input className="field-input" value={form.phone}
                  onChange={e => field("phone", e.target.value)}
                  placeholder="+91 98765 43210" suppressHydrationWarning />
              </div>
              <div className="form-row cols-2">
                <ReadField label="Date of Birth"   value={fmtDate(p?.date_of_birth)} />
                <ReadField label="Gender"          value={p?.gender} />
              </div>
              <div className="form-row cols-2">
                <ReadField label="Marital Status"  value={p?.marital_status} />
                <ReadField label="Blood Group"     value={p?.blood_group} />
              </div>
              <ReadField label="Father's Name"     value={p?.father_name} />
            </div>
          </div>

          {/* Address */}
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

          {/* Education & Experience */}
          <div className="card mb-16">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-school" />Education &amp; Experience</span>
            </div>
            <div className="card-body">
              <div className="form-row cols-2">
                <ReadField label="Qualification"     value={p?.highest_qualification} />
                <ReadField label="Institution"       value={p?.institution} />
              </div>
              <div className="form-row cols-2">
                <ReadField label="Year of Passing"   value={p?.year_of_passing} />
                <ReadField label="Specialization"    value={p?.specialization} />
              </div>
              <div className="form-row cols-2">
                <ReadField label="Experience (yrs)"  value={p?.total_experience_years} />
                <ReadField label="Previous Employer" value={p?.previous_employer} />
              </div>
              <div className="form-row cols-2">
                <ReadField label="Previous Role"     value={p?.previous_designation} />
                <ReadField label="Leaving Reason"    value={p?.leaving_reason} />
              </div>
            </div>
          </div>

          {/* Change Password */}
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

          {/* Work Information */}
          <div className="card mb-16">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-briefcase" />Work Information</span>
            </div>
            <div className="card-body">
              <div className="form-row cols-2">
                <ReadField label="Employee ID"  value={profile?.employee_id} />
                <ReadField label="Role"         value={profile?.role_display} />
              </div>
              <div className="form-row cols-2">
                <ReadField label="Department"   value={profile?.department} />
                <ReadField label="Designation"  value={profile?.designation} />
              </div>
              <div className="form-row cols-2">
                <ReadField label="Branch"         value={profile?.branch} />
                <ReadField label="Date of Joining" value={joinedDate} />
              </div>
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Onboarding Status</label>
                  <div style={{ paddingTop: 6 }}>
                    <span style={{
                      fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 20,
                      background: profile?.onboarding_status === "complete" ? "rgba(22,163,74,0.12)" : "rgba(217,119,6,0.12)",
                      color: profile?.onboarding_status === "complete" ? "var(--success)" : "var(--warn)",
                      textTransform: "capitalize",
                    }}>
                      {val(profile?.onboarding_status)}
                    </span>
                  </div>
                </div>
                <div className="field-group">
                  <label className="field-label">Assessment Status</label>
                  <div style={{ paddingTop: 6 }}>
                    <span style={{
                      fontSize: 11, fontWeight: 600, padding: "3px 10px", borderRadius: 20,
                      background: profile?.assessment_status === "complete" ? "rgba(22,163,74,0.12)" : "rgba(217,119,6,0.12)",
                      color: profile?.assessment_status === "complete" ? "var(--success)" : "var(--warn)",
                      textTransform: "capitalize",
                    }}>
                      {val(profile?.assessment_status)}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Emergency Contact */}
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

          {/* Bank Details */}
          <div className="card mb-16">
            <div className="card-header">
              <span className="card-title"><i className="ti ti-building-bank" />Bank Details</span>
              <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "var(--on-variant)" }}>
                <i className="ti ti-lock" style={{ fontSize: 11 }} /> Contact HR to update
              </div>
            </div>
            <div className="card-body">
              <div className="form-row cols-2">
                <ReadField label="Bank Name"       value={p?.bank_name} />
                <ReadField label="Account Type"    value={p?.account_type} />
              </div>
              <div className="form-row cols-2">
                <ReadField label="Account Holder"  value={p?.account_holder_name} />
                <ReadField label="Account Number"  value={p?.account_number ? `••••${p.account_number.slice(-4)}` : null} />
              </div>
              <div className="form-row cols-2">
                <ReadField label="IFSC Code"       value={p?.ifsc_code} />
                <ReadField label="Bank Branch"     value={p?.bank_branch_name} />
              </div>
            </div>
          </div>

          {/* Documents */}
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

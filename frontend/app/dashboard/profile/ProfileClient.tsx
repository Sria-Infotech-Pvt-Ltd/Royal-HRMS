"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { SessionPayload } from "@/lib/session";
import { PROFILE_SECTIONS, applyDocumentTypeConfig, type DocEntry } from "@/app/dashboard/employees/_data";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import { useFaceRegistrationCard } from "@/hooks/useFaceRegistrationCard";
import Avatar from "@/app/dashboard/employees/_components/Avatar";
import ChangePasswordForm from "./ChangePasswordForm";
import FaceRegistrationModal from "@/components/FaceRegistrationModal";
import ProfilePhotoModal from "@/components/ProfilePhotoModal";
import SeparationCard from "./_components/SeparationCard";
import OnboardingDynamicField from "@/components/OnboardingDynamicField";
import CustomFieldFileUpload from "@/components/CustomFieldFileUpload";
import type { CustomFieldFileValue, OnboardingFieldConfig, OnboardingFieldConfigByStep } from "@/types/onboardingFieldConfig";
import { STATES } from "@/app/dashboard/settings/company/_data";

interface ProfileSub {
  date_of_birth:          string | null;
  gender:                 string | null;
  marital_status:         string | null;
  father_name:            string | null;
  blood_group:            string | null;
  current_address:        string | null;
  current_address_line2:  string | null;
  current_village:        string | null;
  current_district:       string | null;
  current_state:          string | null;
  current_pin_code:       string | null;
  permanent_address:      string | null;
  permanent_address_line2: string | null;
  permanent_village:      string | null;
  permanent_district:     string | null;
  permanent_state:        string | null;
  permanent_pin_code:     string | null;
  permanent_same_as_current: boolean;
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
  custom_field_values:    Record<string, string> | null;
}

interface AssignedPerson {
  id:   string | null;
  name: string | null;
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
  reporting_manager:  AssignedPerson | null;
  reporting_approver: AssignedPerson | null;
  hr:                 AssignedPerson | null;
  profile:           ProfileSub | null;
  profile_photo_url: string | null;
}

interface DocumentItem {
  id:                    number;
  document_type:         string;
  document_type_display: string;
  file_url:              string;
  file_name:             string;
  file_size:             number;
  uploaded_at:           string;
}

const DOC_ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

function buildDocEntries(apiDocs: DocumentItem[], documentTypeConfig: DocumentTypeConfig[] = []): (DocEntry & { docId?: number })[] {
  const docsSection = PROFILE_SECTIONS.find(s => s.id === "documents");
  const configuredSection = docsSection ? applyDocumentTypeConfig(docsSection, documentTypeConfig) : undefined;
  const base = configuredSection?.kind === "docs" ? configuredSection.documents : [];
  return base.map(expected => {
    const uploaded = apiDocs.find(d => d.document_type === expected.documentType);
    if (!uploaded) return expected;
    return {
      ...expected,
      fileUrl:  uploaded.file_url,
      fileName: uploaded.file_name,
      fileSize: uploaded.file_size,
      docId:    uploaded.id,
    };
  });
}

function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface EditableFields {
  phone:                  string;
  current_address:        string;
  current_address_line2:  string;
  current_village:        string;
  current_district:       string;
  current_state:          string;
  current_pin_code:       string;
  permanent_address:      string;
  permanent_address_line2: string;
  permanent_village:      string;
  permanent_district:     string;
  permanent_state:        string;
  permanent_pin_code:     string;
  // Holds "true"/"false" — every EditableFields value is a string so it can
  // go through the same field() setter as everything else.
  permanent_same_as_current: string;
  emergency_name:         string;
  emergency_relationship: string;
  emergency_phone:        string;
  emergency_email:        string;
}

const EMPTY: EditableFields = {
  phone: "",
  current_address: "", current_address_line2: "", current_village: "", current_district: "", current_state: "", current_pin_code: "",
  permanent_address: "", permanent_address_line2: "", permanent_village: "", permanent_district: "", permanent_state: "", permanent_pin_code: "",
  permanent_same_as_current: "false",
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
  const display = val(value);
  return (
    <div className="field-group">
      <label className="field-label">{label}</label>
      <div className={`field-static${display === "—" ? " is-empty" : ""}`}>{display}</div>
    </div>
  );
}

// Blue section header — matches the Employee Profile page's ProfileForm.tsx
// (app/dashboard/employees/[id]/_components/ProfileForm.tsx) so this
// self-service page shares the same visual language as its HR counterpart.
function SectionHeader({ icon, title, action }: { icon: string; title: string; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between px-5 py-3" style={{ background: "var(--primary)" }}>
      <div className="flex items-center gap-2">
        <i className={`ti ${icon} text-[16px] text-white`} />
        <h3 className="text-[14px] font-semibold text-white m-0">{title}</h3>
      </div>
      {action}
    </div>
  );
}

// Built-in field visible unless the settings-driven config explicitly says
// otherwise — while fieldConfig is still loading (empty {}), nothing here
// has an entry yet, so this defaults to "show it" rather than a hide-then-show
// flash for the common case (nothing hidden).
function isBuiltinVisible(fieldConfig: OnboardingFieldConfigByStep, step: number, fieldKey: string): boolean {
  const entry = (fieldConfig[String(step)] ?? []).find(c => c.field_key === fieldKey);
  return entry ? entry.visible : true;
}

function customFieldsFor(fieldConfig: OnboardingFieldConfigByStep, step: number): OnboardingFieldConfig[] {
  return (fieldConfig[String(step)] ?? []).filter(c => c.is_custom && c.visible);
}

// File-type customs never live in custom_field_values (see the backend's
// CustomFieldFileValue model) — every read-only/editable render site below
// needs to route them to CustomFieldFileUpload instead of ReadField/
// OnboardingDynamicField, so these two split customFieldsFor's result by type.
function textCustomFieldsFor(fieldConfig: OnboardingFieldConfigByStep, step: number): OnboardingFieldConfig[] {
  return customFieldsFor(fieldConfig, step).filter(c => c.field_type !== "file");
}
function fileCustomFieldsFor(fieldConfig: OnboardingFieldConfigByStep, step: number): OnboardingFieldConfig[] {
  return customFieldsFor(fieldConfig, step).filter(c => c.field_type === "file");
}

type TabId = "personal" | "work" | "education" | "bank" | "documents" | "face" | "security";

const TABS: { id: TabId; label: string; icon: string }[] = [
  { id: "personal",   label: "Personal",     icon: "ti-user-circle"      },
  { id: "work",       label: "Work Info",    icon: "ti-briefcase"        },
  { id: "education",  label: "Education",    icon: "ti-school"          },
  { id: "bank",        label: "Bank Details", icon: "ti-building-bank"   },
  { id: "documents",  label: "Documents",    icon: "ti-file-description" },
  { id: "face",       label: "Face ID",      icon: "ti-face-id"          },
  { id: "security",   label: "Security",     icon: "ti-lock"             },
];

export default function ProfileClient({ session }: { session: SessionPayload }) {
  const { data: profile, loading, error: profileError } = useFetch<ProfileData>(API.employees.me);
  const { data: docs, refetch: refetchDocs } = useFetch<DocumentItem[]>(API.onboarding.documents);
  const { data: customFileValuesData, refetch: refetchCustomFileValues } =
    useFetch<CustomFieldFileValue[]>(API.onboarding.customFileFields);
  const customFileValues = customFileValuesData ?? [];
  // Per-company field visibility/custom fields (Settings > Onboarding Fields)
  // — same endpoint the onboarding wizard uses. Only Emergency Contact
  // (step 3) custom fields are editable here, matching that section's
  // existing full editability; Personal/Education/Bank customs render
  // read-only below, matching those sections' existing fields.
  const { data: fieldConfigData } = useFetch<OnboardingFieldConfigByStep>(API.onboarding.fieldConfig);
  const fieldConfig = fieldConfigData ?? {};
  const { data: documentTypeConfigData } = useFetch<DocumentTypeConfig[]>(API.onboarding.documentTypeConfig);

  const [active, setActive] = useState<TabId>("personal");

  const [form,   setForm]   = useState<EditableFields>(EMPTY);
  const [customValues, setCustomValues] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [toast,  setToast]  = useState<{ msg: string; ok: boolean } | null>(null);

  const [uploadingDocType, setUploadingDocType] = useState<string | null>(null);
  const docEntries = buildDocEntries(docs ?? [], documentTypeConfigData ?? []);
  const [uploadingFileKey, setUploadingFileKey] = useState<string | null>(null);

  const [showFaceRegistration, setShowFaceRegistration] = useState(false);
  const { state: faceCardState, loading: faceCardLoading, notes: faceRejectionNotes, refetch: refetchFaceStatus } = useFaceRegistrationCard();
  // Hide the whole "Face ID" section once we know the org has the feature
  // switched off entirely — a nav entry whose only content is "this feature
  // is disabled" is just clutter. Kept visible while loading (defaults to
  // showing) so it doesn't flash hidden-then-shown for orgs where it's on.
  const faceTabHidden = !faceCardLoading && faceCardState === "disabled";
  const visibleTabs = TABS.filter(tab => tab.id !== "face" || !faceTabHidden);

  useEffect(() => {
    if (faceTabHidden && active === "face") setActive("personal");
  }, [faceTabHidden, active]);

  const [showPhotoModal, setShowPhotoModal] = useState(false);
  const [photoOverride,  setPhotoOverride]  = useState<string | null | undefined>(undefined);
  // undefined = "no local change yet, trust the fetched profile"; null/string = optimistic
  // override after an upload/remove, shown immediately without waiting for a refetch.
  const photoUrl = photoOverride !== undefined ? photoOverride : (profile?.profile_photo_url ?? null);

  async function handleUploadDocument(documentType: string, file: File) {
    if (!profile?.employee_id) return;
    setUploadingDocType(documentType);
    try {
      const formData = new FormData();
      formData.append("document_type", documentType);
      formData.append("file", file);
      await clientApi.post(API.employees.documents(profile.employee_id), formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      refetchDocs();
      showToast("Document uploaded successfully.");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to upload document.", false);
    } finally {
      setUploadingDocType(null);
    }
  }

  async function handleCustomFileUpload(fieldKey: string, file: File) {
    setUploadingFileKey(fieldKey);
    try {
      const formData = new FormData();
      formData.append("field_key", fieldKey);
      formData.append("file", file);
      await clientApi.post(API.onboarding.customFileFields, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      refetchCustomFileValues();
      showToast("File uploaded successfully.");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to upload file.", false);
    } finally {
      setUploadingFileKey(null);
    }
  }

  async function handleCustomFileDelete(_fieldKey: string, valueId: number) {
    try {
      await clientApi.delete(API.onboarding.customFileFieldDetail(valueId));
      refetchCustomFileValues();
      showToast("File deleted.");
    } catch {
      showToast("Failed to delete file.", false);
    }
  }

  useEffect(() => {
    if (!profile) return;
    setForm({
      phone:                  profile.phone ?? "",
      current_address:        profile.profile?.current_address ?? "",
      current_address_line2:  profile.profile?.current_address_line2 ?? "",
      current_village:        profile.profile?.current_village ?? "",
      current_district:       profile.profile?.current_district ?? "",
      current_state:          profile.profile?.current_state ?? "",
      current_pin_code:       profile.profile?.current_pin_code ?? "",
      permanent_address:      profile.profile?.permanent_address ?? "",
      permanent_address_line2: profile.profile?.permanent_address_line2 ?? "",
      permanent_village:      profile.profile?.permanent_village ?? "",
      permanent_district:     profile.profile?.permanent_district ?? "",
      permanent_state:        profile.profile?.permanent_state ?? "",
      permanent_pin_code:     profile.profile?.permanent_pin_code ?? "",
      permanent_same_as_current: String(Boolean(profile.profile?.permanent_same_as_current)),
      emergency_name:         profile.profile?.emergency_name ?? "",
      emergency_relationship: profile.profile?.emergency_relationship ?? "",
      emergency_phone:        profile.profile?.emergency_phone ?? "",
      emergency_email:        profile.profile?.emergency_email ?? "",
    });
    setCustomValues(profile.profile?.custom_field_values ?? {});
  }, [profile]);

  function field(key: keyof EditableFields, value: string) {
    setForm(prev => ({ ...prev, [key]: value }));
  }

  function customField(fieldKey: string, value: string) {
    setCustomValues(prev => ({ ...prev, [fieldKey]: value }));
  }

  function showToast(msg: string, ok = true) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  }

  async function handleSave() {
    setSaving(true);
    try {
      // Only Emergency-category (step 3) custom fields are ever edited here
      // — the backend independently filters to the same set server-side, but
      // scoping the payload client-side too keeps the request itself honest
      // about what this page actually lets you change.
      const emergencyCustomKeys = new Set(textCustomFieldsFor(fieldConfig, 3).map(c => c.field_key));
      const custom_field_values = Object.fromEntries(
        Object.entries(customValues).filter(([k]) => emergencyCustomKeys.has(k)),
      );
      await clientApi.patch(API.employees.me, { ...form, custom_field_values });
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
        {active === "personal" && (
          <div className="page-actions">
            <button className="btn btn-filled" onClick={handleSave} disabled={saving || loading} suppressHydrationWarning>
              {saving
                ? <><i className="ti ti-loader-2 spin" /> Saving…</>
                : <><i className="ti ti-device-floppy" /> Save Changes</>
              }
            </button>
          </div>
        )}
      </div>

      {profileError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /> {profileError}
        </div>
      )}

      {/* ── Avatar + name banner ── */}
      <div className="card mb-16" style={{ padding: "20px 24px", display: "flex", alignItems: "center", gap: 20 }}>
        <div style={{ position: "relative", width: 72, height: 72, flexShrink: 0 }}>
          <Avatar text={ini} size={72} photoUrl={photoUrl} />
          <button
            type="button"
            onClick={() => setShowPhotoModal(true)}
            suppressHydrationWarning
            title="Change profile photo"
            style={{
              position: "absolute", bottom: -2, right: -2,
              width: 26, height: 26, borderRadius: "50%",
              background: "var(--primary)", color: "#fff",
              display: "flex", alignItems: "center", justifyContent: "center",
              border: "2px solid #fff", cursor: "pointer",
            }}
          >
            <i className="ti ti-camera" style={{ fontSize: 12 }} />
          </button>
        </div>
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

          {!loading && (profile?.reporting_manager?.name || profile?.reporting_approver?.name || profile?.hr?.name) && (
            <div style={{ display: "flex", gap: 16, marginTop: 8, flexWrap: "wrap", paddingTop: 8, borderTop: "1px solid var(--border)" }}>
              {profile?.reporting_manager?.name && (
                <span style={{ fontSize: 12, color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 4 }}>
                  <i className="ti ti-user-check" style={{ fontSize: 12, color: "var(--primary)" }} />
                  Reporting Manager: <strong style={{ color: "var(--on-bg)" }}>{profile.reporting_manager.name}</strong>
                </span>
              )}
              {profile?.reporting_approver?.name && (
                <span style={{ fontSize: 12, color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 4 }}>
                  <i className="ti ti-user-check" style={{ fontSize: 12, color: "var(--primary)" }} />
                  Reporting Approver: <strong style={{ color: "var(--on-bg)" }}>{profile.reporting_approver.name}</strong>
                </span>
              )}
              {profile?.hr?.name && (
                <span style={{ fontSize: 12, color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 4 }}>
                  <i className="ti ti-headset" style={{ fontSize: 12, color: "#7c3aed" }} />
                  Assigned HR: <strong style={{ color: "var(--on-bg)" }}>{profile.hr.name}</strong>
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-start gap-5">

        {/* ── Section sidebar — same visual pattern as the Employee Profile
            page's ProfileSidebar.tsx, so this self-service page matches
            its HR counterpart. ── */}
        <nav
          className="rounded-xl border p-1 sticky top-4 self-start flex-shrink-0 w-[220px]"
          style={{ background: "#fff", borderColor: "var(--outline-v)" }}
        >
          <ul className="flex flex-col gap-0.5">
            {visibleTabs.map(tab => {
              const isActive = active === tab.id;
              return (
                <li key={tab.id}>
                  <button
                    onClick={() => setActive(tab.id)}
                    suppressHydrationWarning
                    className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium text-left whitespace-nowrap transition-all"
                    style={{
                      background: isActive ? "var(--bg-mid)" : "transparent",
                      color: isActive ? "var(--primary)" : "var(--on-variant)",
                      borderLeft: isActive ? "3px solid var(--primary)" : "3px solid transparent",
                    }}
                  >
                    <i
                      className={`ti ${tab.icon} text-[15px] flex-shrink-0`}
                      style={{ color: isActive ? "var(--primary)" : "var(--outline)" }}
                    />
                    {tab.label}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        {/* ── Section content ── */}
        <div className="flex-1 min-w-0">

      {active === "personal" && (
      <div className="grid-2">

        {/* ─── LEFT COLUMN ─── */}
        <div>

          {/* Personal Information */}
          <div className="card mb-16">
            <SectionHeader icon="ti-user-circle" title="Personal Information" />
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
                {isBuiltinVisible(fieldConfig, 0, "date_of_birth") && <ReadField label="Date of Birth"   value={fmtDate(p?.date_of_birth)} />}
                {isBuiltinVisible(fieldConfig, 0, "gender")        && <ReadField label="Gender"          value={p?.gender} />}
              </div>
              <div className="form-row cols-2">
                {isBuiltinVisible(fieldConfig, 0, "marital_status") && <ReadField label="Marital Status" value={p?.marital_status} />}
                {isBuiltinVisible(fieldConfig, 0, "blood_group")    && <ReadField label="Blood Group"    value={p?.blood_group} />}
              </div>
              {isBuiltinVisible(fieldConfig, 0, "father_name") && <ReadField label="Father's Name" value={p?.father_name} />}
              {textCustomFieldsFor(fieldConfig, 0).map(c => (
                <ReadField key={c.field_key} label={c.label} value={p?.custom_field_values?.[c.field_key]} />
              ))}
              {fileCustomFieldsFor(fieldConfig, 0).map(c => (
                <CustomFieldFileUpload
                  key={c.field_key} fieldKey={c.field_key} label={c.label}
                  allowMultiple={c.allow_multiple}
                  value={customFileValues.filter(v => v.field_key === c.field_key)}
                  onUpload={() => {}}
                />
              ))}
            </div>
          </div>

          {/* Address */}
          <div className="card mb-16">
            <SectionHeader icon="ti-map-pin" title="Address" />
            <div className="card-body">
              {(isBuiltinVisible(fieldConfig, 0, "current_address") || isBuiltinVisible(fieldConfig, 0, "current_address_line2")) && (
                <div className="form-row cols-2">
                  {isBuiltinVisible(fieldConfig, 0, "current_address") && (
                    <div className="field-group">
                      <label className="field-label">Address Line 1</label>
                      <input className="field-input" type="text" value={form.current_address}
                        onChange={e => field("current_address", e.target.value)}
                        placeholder="House / Flat no., Street" suppressHydrationWarning />
                    </div>
                  )}
                  {isBuiltinVisible(fieldConfig, 0, "current_address_line2") && (
                    <div className="field-group">
                      <label className="field-label">Address Line 2</label>
                      <input className="field-input" type="text" value={form.current_address_line2}
                        onChange={e => field("current_address_line2", e.target.value)}
                        placeholder="Apartment, floor, landmark" suppressHydrationWarning />
                    </div>
                  )}
                </div>
              )}
              <div className="form-row cols-2">
                {isBuiltinVisible(fieldConfig, 0, "current_village") && (
                  <div className="field-group">
                    <label className="field-label">Village / Town / Area</label>
                    <input className="field-input" value={form.current_village}
                      onChange={e => field("current_village", e.target.value)} suppressHydrationWarning />
                  </div>
                )}
                {isBuiltinVisible(fieldConfig, 0, "current_district") && (
                  <div className="field-group">
                    <label className="field-label">District</label>
                    <input className="field-input" value={form.current_district}
                      onChange={e => field("current_district", e.target.value)} suppressHydrationWarning />
                  </div>
                )}
              </div>
              <div className="form-row cols-2">
                {isBuiltinVisible(fieldConfig, 0, "current_state") && (
                  <div className="field-group">
                    <label className="field-label">State</label>
                    <select className="field-input field-select" value={form.current_state}
                      onChange={e => field("current_state", e.target.value)} suppressHydrationWarning>
                      <option value="">Select…</option>
                      {STATES.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </div>
                )}
                {isBuiltinVisible(fieldConfig, 0, "current_pin_code") && (
                  <div className="field-group">
                    <label className="field-label">PIN Code</label>
                    <input className="field-input" value={form.current_pin_code}
                      onChange={e => field("current_pin_code", e.target.value.replace(/\D/g, "").slice(0, 6))}
                      placeholder="500081" maxLength={6} inputMode="numeric" suppressHydrationWarning />
                  </div>
                )}
              </div>

              {isBuiltinVisible(fieldConfig, 0, "permanent_address") && (
                <label className="module-check" style={{ margin: "4px 0 12px" }}>
                  <input type="checkbox" checked={form.permanent_same_as_current === "true"}
                    onChange={e => field("permanent_same_as_current", e.target.checked ? "true" : "false")}
                    suppressHydrationWarning />
                  <span>Permanent address is the same as current address</span>
                </label>
              )}
              {form.permanent_same_as_current !== "true" && (
                <>
                  {(isBuiltinVisible(fieldConfig, 0, "permanent_address") || isBuiltinVisible(fieldConfig, 0, "permanent_address_line2")) && (
                    <div className="form-row cols-2">
                      {isBuiltinVisible(fieldConfig, 0, "permanent_address") && (
                        <div className="field-group">
                          <label className="field-label">Address Line 1</label>
                          <input className="field-input" type="text" value={form.permanent_address}
                            onChange={e => field("permanent_address", e.target.value)}
                            placeholder="House / Flat no., Street" suppressHydrationWarning />
                        </div>
                      )}
                      {isBuiltinVisible(fieldConfig, 0, "permanent_address_line2") && (
                        <div className="field-group">
                          <label className="field-label">Address Line 2</label>
                          <input className="field-input" type="text" value={form.permanent_address_line2}
                            onChange={e => field("permanent_address_line2", e.target.value)}
                            placeholder="Apartment, floor, landmark" suppressHydrationWarning />
                        </div>
                      )}
                    </div>
                  )}
                  <div className="form-row cols-2">
                    {isBuiltinVisible(fieldConfig, 0, "permanent_village") && (
                      <div className="field-group">
                        <label className="field-label">Village / Town / Area</label>
                        <input className="field-input" value={form.permanent_village}
                          onChange={e => field("permanent_village", e.target.value)} suppressHydrationWarning />
                      </div>
                    )}
                    {isBuiltinVisible(fieldConfig, 0, "permanent_district") && (
                      <div className="field-group">
                        <label className="field-label">District</label>
                        <input className="field-input" value={form.permanent_district}
                          onChange={e => field("permanent_district", e.target.value)} suppressHydrationWarning />
                      </div>
                    )}
                  </div>
                  <div className="form-row cols-2">
                    {isBuiltinVisible(fieldConfig, 0, "permanent_state") && (
                      <div className="field-group">
                        <label className="field-label">State</label>
                        <select className="field-input field-select" value={form.permanent_state}
                          onChange={e => field("permanent_state", e.target.value)} suppressHydrationWarning>
                          <option value="">Select…</option>
                          {STATES.map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </div>
                    )}
                    {isBuiltinVisible(fieldConfig, 0, "permanent_pin_code") && (
                      <div className="field-group">
                        <label className="field-label">PIN Code</label>
                        <input className="field-input" value={form.permanent_pin_code}
                          onChange={e => field("permanent_pin_code", e.target.value.replace(/\D/g, "").slice(0, 6))}
                          placeholder="500081" maxLength={6} inputMode="numeric" suppressHydrationWarning />
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>

        </div>

        {/* ─── RIGHT COLUMN ─── */}
        <div>

          {/* Emergency Contact */}
          <div className="card mb-16">
            <SectionHeader icon="ti-phone" title="Emergency Contact" />
            <div className="card-body">
              <div className="form-row cols-2">
                {isBuiltinVisible(fieldConfig, 3, "emergency_name") && (
                  <div className="field-group">
                    <label className="field-label">Name</label>
                    <input className="field-input" value={form.emergency_name}
                      onChange={e => field("emergency_name", e.target.value)}
                      placeholder="Contact name" suppressHydrationWarning />
                  </div>
                )}
                {isBuiltinVisible(fieldConfig, 3, "emergency_relationship") && (
                  <div className="field-group">
                    <label className="field-label">Relationship</label>
                    <input className="field-input" value={form.emergency_relationship}
                      onChange={e => field("emergency_relationship", e.target.value)}
                      placeholder="e.g. Spouse, Parent" suppressHydrationWarning />
                  </div>
                )}
              </div>
              <div className="form-row cols-2">
                {isBuiltinVisible(fieldConfig, 3, "emergency_phone") && (
                  <div className="field-group">
                    <label className="field-label">Phone</label>
                    <input className="field-input" value={form.emergency_phone}
                      onChange={e => field("emergency_phone", e.target.value)}
                      placeholder="+91 98765 43210" suppressHydrationWarning />
                  </div>
                )}
                {isBuiltinVisible(fieldConfig, 3, "emergency_email") && (
                  <div className="field-group">
                    <label className="field-label">Email</label>
                    <input className="field-input" value={form.emergency_email}
                      onChange={e => field("emergency_email", e.target.value)}
                      placeholder="email@example.com" suppressHydrationWarning />
                  </div>
                )}
              </div>
              {textCustomFieldsFor(fieldConfig, 3).length > 0 && (
                <div className="form-row cols-2">
                  {textCustomFieldsFor(fieldConfig, 3).map(c => (
                    <OnboardingDynamicField
                      key={c.field_key}
                      config={c}
                      value={customValues[c.field_key] ?? ""}
                      onChange={v => customField(c.field_key, v)}
                    />
                  ))}
                </div>
              )}
              {fileCustomFieldsFor(fieldConfig, 3).length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 14, marginTop: 14 }}>
                  {fileCustomFieldsFor(fieldConfig, 3).map(c => (
                    <CustomFieldFileUpload
                      key={c.field_key}
                      fieldKey={c.field_key}
                      label={c.label}
                      required={c.required}
                      allowMultiple={c.allow_multiple}
                      value={customFileValues.filter(v => v.field_key === c.field_key)}
                      uploading={uploadingFileKey === c.field_key}
                      onUpload={handleCustomFileUpload}
                      onDelete={handleCustomFileDelete}
                    />
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      )}

      {active === "work" && (
      <div>
          {/* Work Information */}
          <div className="card mb-16">
            <SectionHeader icon="ti-briefcase" title="Work Information" />
            <div className="card-body">
              <div className="form-row cols-2">
                <ReadField label="Employee ID"  value={profile?.employee_id} />
                <ReadField label="Role"         value={profile?.role_display} />
              </div>
              <div className="form-row cols-2">
                <ReadField label="Org Unit"     value={profile?.department} />
                <ReadField label="Designation"  value={profile?.designation} />
              </div>
              <div className="form-row cols-2">
                <ReadField label="Company Code"   value={profile?.branch} />
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

          <SeparationCard />
      </div>
      )}

      {active === "education" && (
      <div className="card mb-16">
        <SectionHeader icon="ti-school" title="Education & Experience" />
        <div className="card-body">
          <div className="form-row cols-2">
            {isBuiltinVisible(fieldConfig, 1, "highest_qualification") && <ReadField label="Qualification" value={p?.highest_qualification} />}
            {isBuiltinVisible(fieldConfig, 1, "institution")           && <ReadField label="Institution"   value={p?.institution} />}
          </div>
          <div className="form-row cols-2">
            {isBuiltinVisible(fieldConfig, 1, "year_of_passing") && <ReadField label="Year of Passing" value={p?.year_of_passing} />}
            {isBuiltinVisible(fieldConfig, 1, "specialization")  && <ReadField label="Specialization"  value={p?.specialization} />}
          </div>
          <div className="form-row cols-2">
            {isBuiltinVisible(fieldConfig, 1, "total_experience_years") && <ReadField label="Experience (yrs)"  value={p?.total_experience_years} />}
            {isBuiltinVisible(fieldConfig, 1, "previous_employer")      && <ReadField label="Previous Employer" value={p?.previous_employer} />}
          </div>
          <div className="form-row cols-2">
            {isBuiltinVisible(fieldConfig, 1, "previous_designation") && <ReadField label="Previous Role"  value={p?.previous_designation} />}
            {isBuiltinVisible(fieldConfig, 1, "leaving_reason")       && <ReadField label="Leaving Reason" value={p?.leaving_reason} />}
          </div>
          {textCustomFieldsFor(fieldConfig, 1).map(c => (
            <ReadField key={c.field_key} label={c.label} value={p?.custom_field_values?.[c.field_key]} />
          ))}
          {fileCustomFieldsFor(fieldConfig, 1).map(c => (
            <CustomFieldFileUpload
              key={c.field_key} fieldKey={c.field_key} label={c.label}
              allowMultiple={c.allow_multiple}
              value={customFileValues.filter(v => v.field_key === c.field_key)}
              onUpload={() => {}}
            />
          ))}
        </div>
      </div>
      )}

      {active === "bank" && (
      <div className="card mb-16">
        <SectionHeader
          icon="ti-building-bank"
          title="Bank Details"
          action={
            <div style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "rgba(255,255,255,0.85)" }}>
              <i className="ti ti-lock" style={{ fontSize: 11 }} /> Contact HR to update
            </div>
          }
        />
        <div className="card-body">
          <div className="form-row cols-2">
            {isBuiltinVisible(fieldConfig, 2, "bank_name")    && <ReadField label="Bank Name"    value={p?.bank_name} />}
            {isBuiltinVisible(fieldConfig, 2, "account_type") && <ReadField label="Account Type" value={p?.account_type} />}
          </div>
          <div className="form-row cols-2">
            {isBuiltinVisible(fieldConfig, 2, "account_holder_name") && <ReadField label="Account Holder" value={p?.account_holder_name} />}
            {isBuiltinVisible(fieldConfig, 2, "account_number")      && <ReadField label="Account Number" value={p?.account_number ? `••••${p.account_number.slice(-4)}` : null} />}
          </div>
          <div className="form-row cols-2">
            {isBuiltinVisible(fieldConfig, 2, "ifsc_code")        && <ReadField label="IFSC Code"   value={p?.ifsc_code} />}
            {isBuiltinVisible(fieldConfig, 2, "bank_branch_name") && <ReadField label="Bank Branch" value={p?.bank_branch_name} />}
          </div>
          {textCustomFieldsFor(fieldConfig, 2).map(c => (
            <ReadField key={c.field_key} label={c.label} value={p?.custom_field_values?.[c.field_key]} />
          ))}
          {fileCustomFieldsFor(fieldConfig, 2).map(c => (
            <CustomFieldFileUpload
              key={c.field_key} fieldKey={c.field_key} label={c.label}
              allowMultiple={c.allow_multiple}
              value={customFileValues.filter(v => v.field_key === c.field_key)}
              onUpload={() => {}}
            />
          ))}
        </div>
      </div>
      )}

      {active === "documents" && (
      <div className="card">
        <SectionHeader icon="ti-file-description" title="Documents" />
            <div className="card-body" style={{ padding: 0 }}>
              {docEntries.map((doc, i) => {
                const uploaded  = !!doc.fileUrl;
                const uploading = uploadingDocType === doc.documentType;
                return (
                  <div key={doc.documentType} style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "10px 16px",
                    borderBottom: i < docEntries.length - 1 ? "1px solid var(--bg-high)" : "none",
                  }}>
                    <i
                      className={`ti ${uploading ? "ti-loader-2 spin" : uploaded ? "ti-file-check" : "ti-file-off"}`}
                      style={{ color: uploaded ? "var(--success)" : "var(--on-variant)" }}
                    />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 13, color: "var(--on-bg)" }}>{doc.name}</div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                        {uploading ? "Uploading…" : uploaded ? fmtBytes(doc.fileSize ?? 0) : "Not uploaded"}
                      </div>
                    </div>
                    {uploaded ? (
                      <a href={doc.fileUrl} target="_blank" rel="noreferrer" className="btn btn-ghost btn-sm" title="Preview document">
                        <i className="ti ti-eye" />
                      </a>
                    ) : (
                      <button
                        type="button"
                        disabled
                        className="btn btn-ghost btn-sm"
                        title="Not uploaded"
                        style={{ opacity: 0.3, cursor: "not-allowed" }}
                      >
                        <i className="ti ti-eye" />
                      </button>
                    )}
                    <label
                      className="btn btn-ghost btn-sm"
                      title={uploaded ? "Replace document" : "Upload document"}
                      style={{ cursor: uploading ? "not-allowed" : "pointer", opacity: uploading ? 0.5 : 1 }}
                      suppressHydrationWarning
                    >
                      <i className={`ti ${uploaded ? "ti-refresh" : "ti-upload"}`} />
                      <input
                        type="file"
                        accept={DOC_ACCEPT}
                        className="hidden"
                        disabled={uploading}
                        onChange={(e) => {
                          const file = e.target.files?.[0];
                          e.target.value = "";
                          if (file) handleUploadDocument(doc.documentType, file);
                        }}
                      />
                    </label>
                  </div>
                );
              })}
            </div>
      </div>
      )}

      {active === "face" && (
      <div className="card">
        <SectionHeader icon="ti-face-id" title="Face Registration" />
            <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px" }}>
              <i className="ti ti-face-id" style={{ fontSize: 22, color: "var(--on-variant)" }} />
              <div style={{ flex: 1, minWidth: 0 }}>
                {faceCardState === "disabled" && (
                  <>
                    <div style={{ fontSize: 13, color: "var(--on-bg)" }}>Face ID verification is currently disabled</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Contact admin to use this feature.</div>
                  </>
                )}
                {faceCardState === "approved" && (
                  <>
                    <div style={{ fontSize: 13, color: "var(--success)" }}>
                      <i className="ti ti-circle-check" style={{ marginRight: 4 }} />Face ID registered
                    </div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Required for web clock-in/out — already verified.</div>
                  </>
                )}
                {faceCardState === "pending" && (
                  <>
                    <div style={{ fontSize: 13, color: "var(--on-bg)" }}>Face ID pending HR approval</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>You&apos;ll be able to clock in with it once it&apos;s approved.</div>
                  </>
                )}
                {faceCardState === "rejected" && (
                  <>
                    <div style={{ fontSize: 13, color: "var(--error)" }}>Face ID registration was rejected</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{faceRejectionNotes || "Please update and resubmit."}</div>
                  </>
                )}
                {faceCardState === "not_registered" && (
                  <>
                    <div style={{ fontSize: 13, color: "var(--on-bg)" }}>Face ID not yet registered</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                      Usually done during onboarding — register it below if you missed that step.
                    </div>
                  </>
                )}
              </div>
              {(faceCardState === "approved" || faceCardState === "rejected") && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  suppressHydrationWarning
                  onClick={() => setShowFaceRegistration(true)}
                >
                  <i className="ti ti-camera" /> Update My Face
                </button>
              )}
              {faceCardState === "not_registered" && (
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  suppressHydrationWarning
                  onClick={() => setShowFaceRegistration(true)}
                >
                  <i className="ti ti-camera" /> Register My Face
                </button>
              )}
            </div>
      </div>
      )}

      {active === "security" && (
      <div className="card">
        <SectionHeader icon="ti-lock" title="Change Password" />
        <div className="card-body" style={{ maxWidth: 500 }}>
          <ChangePasswordForm />
        </div>
      </div>
      )}

        </div>
      </div>

        {showFaceRegistration && (
          <FaceRegistrationModal
            mode={faceCardState === "not_registered" ? "register" : "update"}
            onClose={() => { setShowFaceRegistration(false); refetchFaceStatus(); }}
          />
        )}

        {showPhotoModal && (
          <ProfilePhotoModal
            hasExistingPhoto={Boolean(photoUrl)}
            onClose={() => setShowPhotoModal(false)}
            onUploaded={url => { setPhotoOverride(url); setShowPhotoModal(false); }}
            onRemoved={() => { setPhotoOverride(null); setShowPhotoModal(false); }}
          />
        )}
    </div>
  );
}

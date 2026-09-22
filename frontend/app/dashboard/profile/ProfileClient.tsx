"use client";

// This account's own "My Profile" page (reached via the top-nav avatar
// chip), rebuilt to match the same gated pattern as the ESS "My Profile"
// tab (see app/dashboard/ess/_components/ProfileSummaryTab.tsx): a compact
// "Profile controls" + "at a glance" summary, with the full record shown
// read-only via the shared EmployeeDrawer, and any personal/contact/
// address/emergency-contact change routed through the same profile-
// correction request instead of inline editing. Password, Documents, Face
// ID, and Separation are true self-service actions with no approval
// concept, so those stay as directly-actionable cards below.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { SessionPayload } from "@/lib/session";
import { formatDate } from "@/lib/formatDate";
import { useFaceRegistrationCard } from "@/hooks/useFaceRegistrationCard";
import Avatar from "@/app/dashboard/employees/_components/Avatar";
import EmployeeDrawer from "@/app/dashboard/employees/_components/EmployeeDrawer";
import type { Employee } from "@/app/dashboard/employees/_data";
import ProfileCorrectionModal from "@/app/dashboard/ess/_components/ProfileCorrectionModal";
import ChangePasswordForm from "./ChangePasswordForm";
import FaceRegistrationModal from "@/components/FaceRegistrationModal";
import ProfilePhotoModal from "@/components/ProfilePhotoModal";
import SeparationCard from "./_components/SeparationCard";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import { PROFILE_SECTIONS, applyDocumentTypeConfig, type DocEntry } from "@/app/dashboard/employees/_data";

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
  work_location:     string | null;
  reporting_manager:  AssignedPerson | null;
  reporting_approver: AssignedPerson | null;
  hr:                 AssignedPerson | null;
  profile:           { date_of_birth: string | null } | null;
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

function initials(name: string) {
  return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return formatDate(d);
}

function toDrawerEmployee(d: ProfileData): Employee {
  const [firstName, ...rest] = (d.full_name || "").split(" ");
  return {
    id: d.employee_id, code: d.employee_id,
    firstName: firstName || "", middleName: "", lastName: rest.join(" "),
    email: d.email, phone: d.phone ?? "",
    department: d.department, designation: d.designation,
    dateOfJoining: d.date_of_joining ?? d.date_joined ?? "", dateOfBirth: "",
    location: d.branch, gender: "male",
    status: "active", employmentStatus: "probation", confirmationDate: null,
    details: {}, tables: {},
  };
}

export default function ProfileClient({ session }: { session: SessionPayload }) {
  const router = useRouter();
  // An admin/HR user editing their OWN record has no one else to approve a
  // correction — they hold employees.edit already, so they get a direct
  // edit link (the same Employee > edit page HR uses for anyone else)
  // instead of the HR-ticket "Request profile correction" flow, which is
  // for employees who genuinely need someone else's approval.
  const canEditDirectly = (session.permissions ?? []).includes("employees.edit");
  const { data: profile, loading, error: profileError } = useFetch<ProfileData>(API.employees.me);
  const { data: docs, refetch: refetchDocs } = useFetch<DocumentItem[]>(API.onboarding.documents);
  const { data: documentTypeConfigData } = useFetch<DocumentTypeConfig[]>(API.onboarding.documentTypeConfig);
  const docEntries = buildDocEntries(docs ?? [], documentTypeConfigData ?? []);
  const [uploadingDocType, setUploadingDocType] = useState<string | null>(null);

  const [showRecord, setShowRecord] = useState(false);
  const [showCorrection, setShowCorrection] = useState(false);
  const [correctionSubmitted, setCorrectionSubmitted] = useState(false);

  const [showFaceRegistration, setShowFaceRegistration] = useState(false);
  const { state: faceCardState, loading: faceCardLoading, notes: faceRejectionNotes, refetch: refetchFaceStatus } = useFaceRegistrationCard();
  const faceTabHidden = !faceCardLoading && faceCardState === "disabled";

  const [showPhotoModal, setShowPhotoModal] = useState(false);
  const [photoOverride,  setPhotoOverride]  = useState<string | null | undefined>(undefined);
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
    } finally {
      setUploadingDocType(null);
    }
  }

  const ini        = initials(session.name);
  const joinedDate = fmtDate(profile?.date_of_joining ?? profile?.date_joined);

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">My Profile</div>
          <div className="page-sub">The same employee record and layout used by Admin, with self-service permissions.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowRecord(true)}>Open full employee profile</button>
        </div>
      </div>

      {profileError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" /> {profileError}
        </div>
      )}

      {correctionSubmitted && (
        <div className="alert alert-success mb-16">
          <i className="ti ti-circle-check" /> Your correction request was submitted and will appear in My Requests.
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
              <span style={{ fontSize: 11, background: "rgba(124,58,237,0.1)", color: "var(--primary)", padding: "2px 10px", borderRadius: 20, fontWeight: 600 }}>
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

      {/* ── Profile controls ── */}
      <div className="card mb-16">
        <div style={{ padding: "18px 20px 4px" }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>Profile controls</div>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>Review your official record or request an approved correction.</div>
        </div>
        <div style={{ padding: "12px 20px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          <button
            type="button"
            onClick={() => setShowRecord(true)}
            style={{ textAlign: "left", background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "14px 16px", cursor: "pointer" }}
          >
            <div style={{ fontWeight: 600, fontSize: 13.5, color: "var(--on-bg)" }}>View employee record</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>Personal, employment, pay, statutory, leave and audit details</div>
          </button>
          {canEditDirectly ? (
            <button
              type="button"
              onClick={() => router.push(`/dashboard/employees/${profile?.employee_id}`)}
              disabled={!profile?.employee_id}
              style={{ textAlign: "left", background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "14px 16px", cursor: "pointer" }}
            >
              <div style={{ fontWeight: 600, fontSize: 13.5, color: "var(--on-bg)" }}>Edit my record</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>Update contact, address or personal information directly</div>
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setShowCorrection(true)}
              style={{ textAlign: "left", background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "14px 16px", cursor: "pointer" }}
            >
              <div style={{ fontWeight: 600, fontSize: 13.5, color: "var(--on-bg)" }}>Request profile correction</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>Submit changes to contact, address or personal information</div>
            </button>
          )}
        </div>
      </div>

      {/* ── My record at a glance ── */}
      <div className="card mb-16">
        <div style={{ padding: "18px 20px 4px" }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>My record at a glance</div>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>Review official fields, then open the full record for all sections.</div>
        </div>
        <div style={{ padding: "4px 20px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>EMPLOYEE ID</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{profile?.employee_id ?? "—"}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>DATE OF BIRTH</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{fmtDate(profile?.profile?.date_of_birth)}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>DATE OF JOINING</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{joinedDate}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>WORK LOCATION</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{profile?.work_location || "—"}</div>
          </div>
        </div>
      </div>

      {/* ── Documents — true self-service, no approval needed ── */}
      <div className="card mb-16">
        <div className="card-header">
          <span className="card-title"><i className="ti ti-file-description" />Documents</span>
        </div>
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
                  <button type="button" disabled className="btn btn-ghost btn-sm" title="Not uploaded" style={{ opacity: 0.3, cursor: "not-allowed" }}>
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

      {/* ── Face ID — true self-service, no approval needed ── */}
      {!faceTabHidden && (
        <div className="card mb-16">
          <div className="card-header">
            <span className="card-title"><i className="ti ti-face-id" />Face Registration</span>
          </div>
          <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12, padding: "14px 16px" }}>
            <i className="ti ti-face-id" style={{ fontSize: 22, color: "var(--on-variant)" }} />
            <div style={{ flex: 1, minWidth: 0 }}>
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
              <button type="button" className="btn btn-primary btn-sm" suppressHydrationWarning onClick={() => setShowFaceRegistration(true)}>
                <i className="ti ti-camera" /> Update My Face
              </button>
            )}
            {faceCardState === "not_registered" && (
              <button type="button" className="btn btn-primary btn-sm" suppressHydrationWarning onClick={() => setShowFaceRegistration(true)}>
                <i className="ti ti-camera" /> Register My Face
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Security — true self-service, no approval needed ── */}
      <div className="card mb-16">
        <div className="card-header">
          <span className="card-title"><i className="ti ti-lock" />Change Password</span>
        </div>
        <div className="card-body" style={{ maxWidth: 500 }}>
          <ChangePasswordForm />
        </div>
      </div>

      <SeparationCard />

      {showRecord && profile && (
        <EmployeeDrawer
          employee={toDrawerEmployee(profile)}
          mode="self"
          onClose={() => setShowRecord(false)}
          onRequestCorrection={canEditDirectly
            ? () => router.push(`/dashboard/employees/${profile.employee_id}`)
            : () => { setShowRecord(false); setShowCorrection(true); }}
          correctionLabel={canEditDirectly ? "Edit my record" : undefined}
        />
      )}

      {showCorrection && (
        <ProfileCorrectionModal
          onClose={() => setShowCorrection(false)}
          onSubmitted={() => { setShowCorrection(false); setCorrectionSubmitted(true); }}
        />
      )}

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

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
import { useFaceRegistrationCard } from "@/hooks/useFaceRegistrationCard";
import Avatar from "@/app/dashboard/employees/_components/Avatar";
import EmployeeDrawer from "@/app/dashboard/employees/_components/EmployeeDrawer";
import ProfileEditModal from "@/app/dashboard/employees/_components/ProfileEditModal";
import ChangePasswordForm from "./ChangePasswordForm";
import FaceRegistrationModal from "@/components/FaceRegistrationModal";
import ProfilePhotoModal from "@/components/ProfilePhotoModal";
import SeparationCard from "./_components/SeparationCard";
import ProfileDocumentsCard from "./ProfileDocumentsCard";
import ProfileFaceIdCard from "./ProfileFaceIdCard";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import {
  type ProfileData, type DocumentItem,
  buildDocEntries, initials, fmtDate, toDrawerEmployee,
} from "./_profileClientData";

export default function ProfileClient({ session }: { session: SessionPayload }) {
  const router = useRouter();
  // An admin/HR user editing their OWN record has no one else to approve a
  // correction — they hold employees.edit already, so they get a direct
  // edit link (the same Employee > edit page HR uses for anyone else)
  // instead of the HR-ticket "Request profile correction" flow, which is
  // for employees who genuinely need someone else's approval.
  const canEditDirectly = (session.permissions ?? []).includes("employees.edit");
  // Gates the camera button below and "Edit my details" — an admin-revocable
  // toggle (default granted) separate from canEditDirectly, so HR can lock
  // down self-service editing for a role without touching the employees.edit
  // permission that governs editing OTHER people's records.
  const canEditOwnProfile = (session.permissions ?? []).includes("employees.edit_own_profile");
  const { data: profile, loading, error: profileError, refetch: refetchProfile } = useFetch<ProfileData>(API.employees.me);
  const { data: docs, refetch: refetchDocs } = useFetch<DocumentItem[]>(API.onboarding.documents);
  const { data: documentTypeConfigData } = useFetch<DocumentTypeConfig[]>(API.onboarding.documentTypeConfig);
  const docEntries = buildDocEntries(docs ?? [], documentTypeConfigData ?? []);
  const [uploadingDocType, setUploadingDocType] = useState<string | null>(null);

  const [showRecord, setShowRecord] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [savedJustNow, setSavedJustNow] = useState(false);

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

      {savedJustNow && (
        <div className="alert alert-success mb-16">
          <i className="ti ti-circle-check" /> Your profile was updated.
        </div>
      )}

      {/* ── Avatar + name banner ── */}
      <div className="card mb-16" style={{ padding: "20px 24px", display: "flex", alignItems: "center", gap: 20 }}>
        <div style={{ position: "relative", width: 72, height: 72, flexShrink: 0 }}>
          <Avatar text={ini} size={72} photoUrl={photoUrl} />
          {canEditOwnProfile && (
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
          )}
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
          ) : canEditOwnProfile ? (
            <button
              type="button"
              onClick={() => setShowEdit(true)}
              style={{ textAlign: "left", background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "14px 16px", cursor: "pointer" }}
            >
              <div style={{ fontWeight: 600, fontSize: 13.5, color: "var(--on-bg)" }}>Edit my details</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>Update your mobile number, address or emergency contact</div>
            </button>
          ) : (
            <div style={{ padding: "14px 16px", color: "var(--on-variant)", fontSize: 12.5 }}>
              Self-service profile editing has been disabled for your role. Contact HR to update your details.
            </div>
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
      <ProfileDocumentsCard
        docEntries={docEntries}
        uploadingDocType={uploadingDocType}
        onUploadDocument={handleUploadDocument}
      />

      {/* ── Face ID — true self-service, no approval needed ── */}
      {!faceTabHidden && (
        <ProfileFaceIdCard
          faceCardState={faceCardState}
          faceRejectionNotes={faceRejectionNotes}
          onRegister={() => setShowFaceRegistration(true)}
        />
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
            : () => { setShowRecord(false); setShowEdit(true); }}
          correctionLabel="Edit my record"
        />
      )}

      {showEdit && profile && (
        <ProfileEditModal
          profile={profile}
          onClose={() => setShowEdit(false)}
          onSaved={() => { setShowEdit(false); setSavedJustNow(true); refetchProfile(); }}
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

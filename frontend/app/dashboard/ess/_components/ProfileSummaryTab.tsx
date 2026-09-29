"use client";

// Landing view for the ESS "My Profile" tab. "Open full employee profile"
// opens the exact same read-only Employee Drawer Admin sees from the
// Employee Directory (self-service mode: no edit/reveal-sensitive controls)
// — matching this page's own subtitle ("The same employee record and
// layout used by Admin"). "Edit my details" opens ProfileEditModal, saving
// straight to the record via PATCH API.employees.me — no HR approval step;
// a separate, still-available "Request a profile correction" entry lives
// under My Requests (EmployeeRequestModal.tsx) for anyone who wants a
// tracked request instead.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import EmployeeDrawer from "@/app/dashboard/employees/_components/EmployeeDrawer";
import ProfileEditModal from "@/app/dashboard/employees/_components/ProfileEditModal";
import ProfileCorrectionModal from "./ProfileCorrectionModal";
import Avatar from "@/app/dashboard/employees/_components/Avatar";
import ProfilePhotoModal from "@/components/ProfilePhotoModal";
import { initials } from "@/app/dashboard/employees/_data";
import type { Employee } from "@/app/dashboard/employees/_data";

interface ProfileSummaryData {
  employee_id:      string;
  full_name:        string;
  email:            string;
  phone:            string | null;
  designation:      string;
  department:       string;
  branch:           string;
  profile_photo_url?: string | null;
  date_of_joining:  string | null;
  date_joined:      string | null;
  work_location:    string | null;
  status:           string | null;
  reporting_manager?: { name: string | null } | null;
  profile:          {
    date_of_birth: string | null;
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

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return formatDate(d);
}

function toDrawerEmployee(d: ProfileSummaryData, photoUrl?: string | null): Employee {
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
    photoUrl: photoUrl ?? d.profile_photo_url ?? undefined,
  };
}

export default function ProfileSummaryTab() {
  const { data, refetch } = useFetch<ProfileSummaryData>(API.employees.me);
  const canEditOwnProfile = usePermission("employees.edit_own_profile");
  const [showRecord, setShowRecord] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [showCorrection, setShowCorrection] = useState(false);
  const [savedJustNow, setSavedJustNow] = useState(false);
  const [correctionSubmitted, setCorrectionSubmitted] = useState(false);
  const [showPhotoModal, setShowPhotoModal] = useState(false);
  const [photoOverride, setPhotoOverride] = useState<string | null | undefined>(undefined);
  const photoUrl = photoOverride !== undefined ? photoOverride : (data?.profile_photo_url ?? null);
  const [firstName, ...restName] = (data?.full_name ?? "").split(" ");

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ position: "relative", width: 48, height: 48, flexShrink: 0 }}>
            <Avatar text={initials(firstName || "", restName.join(" "))} size={48} photoUrl={photoUrl} />
            {canEditOwnProfile && (
              <button
                type="button"
                onClick={() => setShowPhotoModal(true)}
                suppressHydrationWarning
                title="Change profile photo"
                style={{
                  position: "absolute", bottom: -2, right: -2,
                  width: 20, height: 20, borderRadius: "50%",
                  background: "var(--primary)", color: "#fff",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  border: "2px solid var(--surface)", cursor: "pointer",
                }}
              >
                <i className="ti ti-camera" style={{ fontSize: 10 }} />
              </button>
            )}
          </div>
          <div>
            <div className="page-title">My profile</div>
            <div className="page-sub">The same employee record and layout used by Admin, with self-service permissions.</div>
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowRecord(true)}>Open full employee profile</button>
        </div>
      </div>

      {showPhotoModal && (
        <ProfilePhotoModal
          hasExistingPhoto={Boolean(photoUrl)}
          onClose={() => setShowPhotoModal(false)}
          onUploaded={url => { setPhotoOverride(url); setShowPhotoModal(false); }}
          onRemoved={() => { setPhotoOverride(null); setShowPhotoModal(false); }}
        />
      )}

      {savedJustNow && (
        <div className="alert alert-success mb-16">
          <i className="ti ti-circle-check" /> Your profile was updated.
        </div>
      )}

      {correctionSubmitted && (
        <div className="alert alert-success mb-16">
          <i className="ti ti-circle-check" /> Correction request submitted — track it under My Requests.
        </div>
      )}

      <div className="card mb-16">
        <div style={{ padding: "18px 20px 4px" }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>Profile controls</div>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>Review your official record or update your contact details.</div>
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
          {canEditOwnProfile ? (
            <button
              type="button"
              onClick={() => setShowEdit(true)}
              style={{ textAlign: "left", background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "14px 16px", cursor: "pointer" }}
            >
              <div style={{ fontWeight: 600, fontSize: 13.5, color: "var(--on-bg)" }}>Edit my details</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>Update your mobile number, address or emergency contact</div>
            </button>
          ) : (
            <button
              type="button"
              onClick={() => setShowCorrection(true)}
              style={{ textAlign: "left", background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "14px 16px", cursor: "pointer" }}
            >
              <div style={{ fontWeight: 600, fontSize: 13.5, color: "var(--on-bg)" }}>Request profile correction</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3 }}>Submit a change for HR to review and apply</div>
            </button>
          )}
        </div>
      </div>

      <div className="card">
        <div style={{ padding: "18px 20px 4px" }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>My record at a glance</div>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 2 }}>Review official fields, then open the full record for all sections.</div>
        </div>
        <div style={{ padding: "4px 20px 20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>EMPLOYEE ID</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{data?.employee_id ?? "—"}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>DATE OF BIRTH</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{fmtDate(data?.profile?.date_of_birth)}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>DATE OF JOINING</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{fmtDate(data?.date_of_joining ?? data?.date_joined)}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>WORK LOCATION</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{data?.work_location || "—"}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>REPORTING MANAGER</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{data?.reporting_manager?.name || "—"}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>MOBILE NUMBER</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4 }}>{data?.phone || "—"}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>WORK EMAIL</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4, wordBreak: "break-all" }}>{data?.email || "—"}</div>
          </div>
          <div style={{ background: "var(--bg-mid)", borderRadius: "var(--radius)", padding: "12px 16px" }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--on-variant)", letterSpacing: "0.04em" }}>EMPLOYMENT STATUS</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 4, textTransform: "capitalize" }}>{data?.status || "—"}</div>
          </div>
        </div>
      </div>

      {showRecord && data && (
        <EmployeeDrawer
          employee={toDrawerEmployee(data, photoUrl)}
          mode="self"
          onClose={() => setShowRecord(false)}
          onRequestCorrection={() => {
            setShowRecord(false);
            // Direct-edit is only offered when the account actually holds
            // employees.edit_own_profile — otherwise this must go through
            // the real HR-approved request flow (ProfileCorrectionModal),
            // never a silent bypass straight to the editable form.
            if (canEditOwnProfile) setShowEdit(true);
            else setShowCorrection(true);
          }}
          correctionLabel={canEditOwnProfile ? "Edit my details" : "Request profile correction"}
        />
      )}

      {showCorrection && (
        <ProfileCorrectionModal
          onClose={() => setShowCorrection(false)}
          onSubmitted={() => { setShowCorrection(false); setCorrectionSubmitted(true); }}
        />
      )}

      {showEdit && data && (
        <ProfileEditModal
          profile={data}
          onClose={() => setShowEdit(false)}
          onSaved={() => { setShowEdit(false); setSavedJustNow(true); refetch(); }}
        />
      )}
    </div>
  );
}

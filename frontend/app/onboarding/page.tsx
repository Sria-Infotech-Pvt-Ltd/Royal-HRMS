"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import clientApi, { markIntentionalLogout } from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getStoredUser, setOnboardingStatus, clearAuth } from "@/lib/auth";
import DocPreviewModal from "@/components/DocPreviewModal";
import FaceRegistrationModal from "@/components/FaceRegistrationModal";
import type { FaceRegistrationRequest } from "@/types/faceRegistration";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ProfileForm {
  date_of_birth: string; gender: string; marital_status: string;
  father_name: string; blood_group: string;
  current_address: string; permanent_address: string;
  highest_qualification: string; institution: string;
  year_of_passing: string; specialization: string;
  total_experience_years: string; previous_employer: string;
  previous_designation: string; leaving_reason: string;
  account_number: string; ifsc_code: string; bank_name: string;
  bank_branch_name: string; account_holder_name: string; account_type: string;
  emergency_name: string; emergency_relationship: string;
  emergency_phone: string; emergency_email: string;
  pan_number: string;
}

interface UploadedDoc { id: string; document_type: string; document_type_display: string; file?: string; file_name: string; uploaded_at: string; }

const EMPTY: ProfileForm = {
  date_of_birth: "", gender: "", marital_status: "", father_name: "", blood_group: "",
  current_address: "", permanent_address: "",
  highest_qualification: "", institution: "", year_of_passing: "", specialization: "",
  total_experience_years: "", previous_employer: "", previous_designation: "", leaving_reason: "",
  account_number: "", ifsc_code: "", bank_name: "", bank_branch_name: "",
  account_holder_name: "", account_type: "",
  emergency_name: "", emergency_relationship: "", emergency_phone: "", emergency_email: "",
  pan_number: "",
};

const PAN_RE = /^[A-Za-z]{5}[0-9]{4}[A-Za-z]$/;

const STEPS = [
  { label: "Personal",               shortLabel: "Personal",   icon: "ti-user"          },
  { label: "Education & Experience", shortLabel: "Education",  icon: "ti-school"        },
  { label: "Bank Details",           shortLabel: "Bank",       icon: "ti-building-bank" },
  { label: "Emergency Contact",      shortLabel: "Emergency",  icon: "ti-urgent"        },
  { label: "Documents",              shortLabel: "Documents",  icon: "ti-files"         },
];

// Appended only when the admin's org-wide Face ID Verification toggle
// (Attendance Settings) is mandatory — see the faceMandatory fetch below.
// Always the LAST step so steps 0-4's indices (and all the tab === N checks
// throughout this file) never shift.
const FACE_STEP = { label: "Face ID", shortLabel: "Face ID", icon: "ti-face-id" };

const DOC_TYPES = [
  { value: "pan_card",           label: "PAN Card" },
  { value: "aadhaar_card",       label: "Aadhaar Card" },
  { value: "degree_certificate", label: "Degree Certificate" },
  { value: "experience_letter",  label: "Experience Letter" },
];

const INP = "field-input";
const SEL = "field-input";

// ── Component ───────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);
  const [tab,       setTab]       = useState(0);
  const [form,      setForm]      = useState<ProfileForm>(EMPTY);
  const [docs,      setDocs]      = useState<UploadedDoc[]>([]);
  const [saving,    setSaving]    = useState(false);
  const [saveMsg,   setSaveMsg]   = useState<string | null>(null);
  const [saveErr,   setSaveErr]   = useState<string | null>(null);
  const [uploading,    setUploading]    = useState<string | null>(null);
  const [panErr,       setPanErr]       = useState<string | null>(null);
  const [panSaving,    setPanSaving]    = useState(false);
  const [submitted,          setSubmitted]          = useState(false);
  const [isAlreadySubmitted, setIsAlreadySubmitted] = useState(false);
  const [checkingApproval,   setCheckingApproval]   = useState(false);
  const [highestSaved, setHighestSaved] = useState(-1);
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  const [faceMandatory, setFaceMandatory] = useState(false);
  const [faceRegistration, setFaceRegistration] = useState<Partial<FaceRegistrationRequest> | null>(null);
  const [showFaceCapture, setShowFaceCapture] = useState(false);

  const steps = useMemo(() => (faceMandatory ? [...STEPS, FACE_STEP] : STEPS), [faceMandatory]);

  useEffect(() => {
    const user = getStoredUser();
    if (user?.onboarding_status === "submitted") setIsAlreadySubmitted(true);
  }, []);

  const refetchFaceRegistration = useCallback(() => {
    clientApi.get(API.attendance.faceRegistration.me).then(r => {
      setFaceRegistration(r.data?.data ?? null);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    clientApi.get(API.attendance.faceVerification.status).then(r => {
      setFaceMandatory(Boolean(r.data?.data?.is_mandatory));
    }).catch(() => {});
    refetchFaceRegistration();
  }, [refetchFaceRegistration]);

  // When on the "waiting for approval" screen, poll assessments API.
  // If HR has approved and assigned assessments, redirect the candidate there.
  useEffect(() => {
    if (!submitted && !isAlreadySubmitted) return;
    clientApi.get(API.assessments.my).then(r => {
      const assignments = r.data?.data?.assignments ?? [];
      if (assignments.length > 0) router.replace("/onboarding/assessments");
    }).catch(() => {});
  }, [submitted, isAlreadySubmitted, router]);


  useEffect(() => {
    clientApi.get(API.onboarding.profile).then(r => {
      const d = r.data?.data ?? {};
      setForm(prev => ({ ...prev, ...Object.fromEntries(
        Object.keys(EMPTY).map(k => [k, d[k] ?? ""])
      ) }));
    }).catch(() => {});
    clientApi.get(API.onboarding.documents).then(r => {
      setDocs(r.data?.data ?? []);
    }).catch(() => {});
  }, []);

  async function handleLogout() {
    setLoggingOut(true);
    try {
      markIntentionalLogout();
      await clientApi.post(API.auth.logout, {});
    } catch { /* proceed regardless */ } finally {
      clearAuth();
      router.replace("/login");
    }
  }

  function set(field: keyof ProfileForm, value: string) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  const STEP_REQUIRED: Record<number, { key: keyof ProfileForm; label: string }[]> = {
    0: [
      { key: "date_of_birth",  label: "Date of Birth" },
      { key: "gender",         label: "Gender" },
      { key: "marital_status", label: "Marital Status" },
      { key: "father_name",    label: "Father's Name" },
      { key: "current_address",label: "Current Address" },
    ],
    1: [
      { key: "highest_qualification", label: "Highest Qualification" },
      { key: "institution",           label: "Institution / University" },
    ],
    2: [
      { key: "account_holder_name", label: "Account Holder Name" },
      { key: "account_type",        label: "Account Type" },
      { key: "account_number",      label: "Account Number" },
      { key: "ifsc_code",           label: "IFSC Code" },
      { key: "bank_name",           label: "Bank Name" },
      { key: "bank_branch_name",    label: "Bank Branch Name" },
    ],
    3: [
      { key: "emergency_name",         label: "Emergency Contact Name" },
      { key: "emergency_relationship", label: "Relationship" },
      { key: "emergency_phone",        label: "Emergency Contact Phone" },
    ],
  };

  async function saveSection(): Promise<boolean> {
    setSaveMsg(null); setSaveErr(null);

    const required = STEP_REQUIRED[tab] ?? [];
    const missing = required.filter(f => !form[f.key]?.trim()).map(f => f.label);
    if (missing.length > 0) {
      setSaveErr(`Please fill in: ${missing.join(", ")}`);
      return false;
    }

    // Tab 4 (documents) and tab 5 (face ID, when present) have no profile
    // data to save — documents are uploaded via handleUpload, face ID is
    // submitted via the FaceRegistrationModal. Skip the API call and let
    // handleSubmit fire the single submit request.
    if (tab >= 4) return true;

    setSaving(true);
    try {
      const res = await clientApi.patch<{ success: boolean; message: string }>(API.onboarding.profileStep(tab), form);
      if (res.data?.success === false) {
        setSaveErr(res.data.message ?? "Please fill in all required fields.");
        return false;
      }
      setSaveMsg("Saved successfully.");
      setTimeout(() => setSaveMsg(null), 2500);
      return true;
    } catch (err: unknown) {
      setSaveErr((err as { message?: string })?.message ?? "Save failed. Please try again.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function next() {
    const ok = await saveSection();
    if (ok && tab < steps.length - 1) {
      setHighestSaved(prev => Math.max(prev, tab));
      setTab(t => t + 1);
    }
  }

  // PAN's number is captured at the moment its proof document is uploaded,
  // not on a separate form step — matches how real onboarding flows tie the
  // two together. Validates format + global uniqueness server-side before
  // the file itself is ever sent, so a duplicate/invalid PAN blocks the
  // upload with an immediate, specific error instead of silently accepting
  // an unusable document.
  async function handlePanCardUpload(file: File) {
    const value = form.pan_number.trim().toUpperCase();
    if (!value) {
      setPanErr("Enter your PAN number before uploading the PAN card.");
      return;
    }
    if (!PAN_RE.test(value)) {
      setPanErr("Enter a valid PAN (e.g. ABCDE1234F) — 5 letters, 4 digits, 1 letter.");
      return;
    }
    setPanErr(null);
    setPanSaving(true);
    try {
      await clientApi.patch(API.onboarding.profileStep(4), { pan_number: value });
    } catch (err: unknown) {
      setPanErr((err as { message?: string })?.message ?? "Could not save PAN number. Please try again.");
      return;
    } finally {
      setPanSaving(false);
    }
    set("pan_number", value);
    await handleUpload("pan_card", file);
  }

  async function handleUpload(docType: string, file: File) {
    setUploading(docType);
    try {
      // If a document of this type already exists, delete it first
      const existing = docs.find(d => d.document_type === docType);
      if (existing) {
        await clientApi.delete(API.onboarding.documentDetail(existing.id));
      }
      const fd = new FormData();
      fd.append("document_type", docType);
      fd.append("file", file);
      await clientApi.post(API.onboarding.documents, fd);
      const r = await clientApi.get(API.onboarding.documents);
      setDocs(r.data?.data ?? []);
    } catch (err: unknown) {
      setSaveErr((err as { message?: string })?.message ?? "Upload failed. Max 5 MB, PDF/JPG/PNG only.");
    } finally {
      setUploading(null);
    }
  }

  async function handleSubmit() {
    const ok = await saveSection();
    if (!ok) return;
    setSaving(true);
    try {
      await clientApi.post(API.onboarding.submit, {}, { timeout: 60000 });
      setHighestSaved(steps.length - 1);
      setOnboardingStatus("submitted");
      setSubmitted(true);
    } catch (err: unknown) {
      setSaveErr((err as { message?: string })?.message ?? "Submission failed. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const uploadedTypes = new Set(docs.map(d => d.document_type));

  async function handleCheckApproval() {
    setCheckingApproval(true);
    try {
      const r = await clientApi.get(API.assessments.my);
      const assignments = r.data?.data?.assignments ?? [];
      if (assignments.length > 0) {
        router.replace("/onboarding/assessments");
      }
    } catch { /* stay on page */ } finally {
      setCheckingApproval(false);
    }
  }

  // ── Submitted screen ───────────────────────────────────────────────────────
  if (submitted || isAlreadySubmitted) {
    return (
      <div style={ROOT_STYLE}>
        <div style={{ ...CARD_STYLE, textAlign: "center", padding: "3rem 2rem", maxWidth: 480 }}>
          <div style={{ width: 72, height: 72, borderRadius: "50%", background: "var(--success-c)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 1.5rem", fontSize: 32 }}>
            <i className="ti ti-check" style={{ color: "var(--success)", fontSize: 36 }} />
          </div>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--on-bg)", marginBottom: ".75rem" }}>Profile Submitted!</h2>
          <p style={{ color: "var(--on-variant)", lineHeight: 1.6, marginBottom: "1.5rem" }}>
            Your onboarding details have been sent for HR review.<br />
            You will receive access once approved.
          </p>
          <p style={{ fontSize: ".82rem", color: "var(--outline)", background: "var(--bg-low)", padding: ".75rem 1rem", borderRadius: 8, marginBottom: "1.5rem" }}>
            You can close this tab. We will notify you by email when approved.
          </p>
          <button
            onClick={handleCheckApproval}
            disabled={checkingApproval}
            type="button"
            style={{
              display: "inline-flex", alignItems: "center", gap: 7,
              padding: "10px 20px", borderRadius: 10,
              border: "1.5px solid var(--primary)",
              background: "var(--primary)",
              color: "#fff",
              cursor: checkingApproval ? "not-allowed" : "pointer",
              fontSize: ".9rem", fontWeight: 600,
              opacity: checkingApproval ? 0.7 : 1,
            }}
          >
            {checkingApproval
              ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 15 }} /> Checking…</>
              : <><i className="ti ti-refresh" style={{ fontSize: 15 }} /> Check Approval Status</>
            }
          </button>
        </div>

        <button
          onClick={handleLogout}
          disabled={loggingOut}
          type="button"
          style={{
            position: "fixed", bottom: 24, right: 24, zIndex: 100,
            display: "flex", alignItems: "center", gap: 7,
            padding: "10px 18px", borderRadius: 10,
            border: "1.5px solid var(--outline-v)",
            background: "#fff",
            boxShadow: "0 2px 12px rgba(0,0,0,0.10)",
            cursor: loggingOut ? "not-allowed" : "pointer",
            fontSize: ".84rem", fontWeight: 500,
            color: "var(--on-variant)",
          }}
        >
          {loggingOut
            ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 15 }} /> Logging out…</>
            : <><i className="ti ti-logout" style={{ fontSize: 15 }} /> Logout</>
          }
        </button>
      </div>
    );
  }

  // ── Wizard ─────────────────────────────────────────────────────────────────
  return (
    <div style={ROOT_STYLE}>
      <div style={{ width: "100%", maxWidth: 820 }}>

        {/* ── Header ── */}
        <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
          <div style={{
            width: 68, height: 68, borderRadius: "50%",
            background: "linear-gradient(135deg, #1e4e8c 0%, #2563eb 100%)",
            display: "flex", alignItems: "center", justifyContent: "center",
            margin: "0 auto 1.25rem",
            boxShadow: "0 6px 24px rgba(30,78,140,0.28)",
            fontSize: 30,
          }}>
            👑
          </div>
          <h1 style={{ fontSize: "1.75rem", fontWeight: 700, color: "var(--on-bg)", marginBottom: ".5rem", letterSpacing: "-.02em" }}>
            Complete Your Profile
          </h1>
          <p style={{ color: "var(--on-variant)", fontSize: ".95rem" }}>
            Fill in your details to get started. Your information is kept secure.
          </p>
        </div>

        {/* ── Step Indicator ── */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "center", marginBottom: "2.5rem", overflowX: "auto", padding: "0 .5rem" }}>
          {steps.map((step, i) => {
            const isDone   = i <= highestSaved;
            const isActive = i === tab;
            return (
              <div key={step.label} style={{ display: "flex", alignItems: "flex-start", flexShrink: 0 }}>
                <button
                  type="button"
                  onClick={() => { if (i <= highestSaved + 1) setTab(i); }}
                  disabled={i > highestSaved + 1}
                  style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 10, background: "none", border: "none", cursor: i <= highestSaved + 1 ? "pointer" : "default", padding: "0 4px", minWidth: 88, opacity: i > highestSaved + 1 ? 0.45 : 1 }}
                >
                  <div style={{
                    width: 58, height: 58, borderRadius: "50%",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    background: isDone ? "var(--success)" : isActive ? "var(--primary)" : "#fff",
                    border: isDone ? "2.5px solid var(--success)" : isActive ? "2.5px solid var(--primary)" : "2px solid var(--outline-v)",
                    boxShadow: isActive ? "0 0 0 5px rgba(30,78,140,0.12), 0 4px 12px rgba(30,78,140,0.18)" : isDone ? "0 2px 8px rgba(27,138,107,0.18)" : "none",
                    transition: "all 0.25s ease",
                  }}>
                    {isDone
                      ? <i className="ti ti-check" style={{ fontSize: 24, color: "#fff" }} />
                      : <i className={`ti ${step.icon}`} style={{ fontSize: 22, color: isActive ? "#fff" : "var(--outline)" }} />
                    }
                  </div>
                  <div style={{ textAlign: "center" }}>
                    <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: ".07em", textTransform: "uppercase", color: isDone ? "var(--success)" : isActive ? "var(--primary)" : "var(--outline)", marginBottom: 3 }}>
                      {isDone ? "Done" : `Step ${i + 1}`}
                    </div>
                    <div style={{ fontSize: 12, fontWeight: isActive ? 700 : 500, color: isActive ? "var(--on-bg)" : isDone ? "var(--success)" : "var(--on-variant)", maxWidth: 80, lineHeight: 1.3 }}>
                      {step.shortLabel}
                    </div>
                  </div>
                </button>

                {i < steps.length - 1 && (
                  <div style={{ display: "flex", alignItems: "center", paddingTop: 29, margin: "0 -4px" }}>
                    <div style={{ width: 28, height: 2, background: i <= highestSaved ? "var(--success)" : "var(--outline-v)", borderRadius: 2, transition: "background 0.3s" }} />
                    <i className="ti ti-chevron-right" style={{ fontSize: 14, color: i <= highestSaved ? "var(--success)" : "var(--outline-v)", margin: "0 -2px", transition: "color 0.3s" }} />
                    <div style={{ width: 28, height: 2, background: i <= highestSaved ? "var(--success)" : "var(--outline-v)", borderRadius: 2, transition: "background 0.3s" }} />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* ── Form card ── */}
        <div style={CARD_STYLE}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: "1.5rem", paddingBottom: "1rem", borderBottom: "1px solid var(--outline-v)" }}>
            <div style={{ width: 38, height: 38, borderRadius: 10, background: "rgba(30,78,140,0.08)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <i className={`ti ${steps[tab].icon}`} style={{ fontSize: 18, color: "var(--primary)" }} />
            </div>
            <div>
              <div style={{ fontSize: ".7rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--outline)", marginBottom: 2 }}>Step {tab + 1} of {steps.length}</div>
              <div style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--on-bg)" }}>{steps[tab].label}</div>
            </div>
            <div style={{ marginLeft: "auto", textAlign: "right" }}>
              <div style={{ fontSize: ".75rem", color: "var(--on-variant)", marginBottom: 4 }}>{Math.round(((highestSaved + 1) / steps.length) * 100)}% complete</div>
              <div style={{ width: 100, height: 5, borderRadius: 3, background: "var(--outline-v)", overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${((highestSaved + 1) / steps.length) * 100}%`, background: "var(--primary)", borderRadius: 3, transition: "width 0.4s ease" }} />
              </div>
            </div>
          </div>

          {saveErr && <div className="alert alert-error"  style={{ marginBottom: "1.25rem" }}>{saveErr}</div>}
          {saveMsg && <div className="alert alert-success" style={{ marginBottom: "1.25rem" }}>{saveMsg}</div>}

          {tab === 0 && <TabPersonal  form={form} set={set} />}
          {tab === 1 && <TabEducation form={form} set={set} />}
          {tab === 2 && <TabBank      form={form} set={set} />}
          {tab === 3 && <TabEmergency form={form} set={set} />}
          {tab === 4 && (
            <TabDocuments
              docs={docs}
              uploadedTypes={uploadedTypes}
              uploading={uploading}
              fileRefs={fileRefs}
              onUpload={handleUpload}
              panNumber={form.pan_number}
              onPanNumberChange={v => { set("pan_number", v); setPanErr(null); }}
              onPanCardUpload={handlePanCardUpload}
              panErr={panErr}
              panSaving={panSaving}
            />
          )}
          {tab === 5 && faceMandatory && (
            <TabFaceId
              registration={faceRegistration}
              onRegister={() => setShowFaceCapture(true)}
            />
          )}

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "2rem", paddingTop: "1.25rem", borderTop: "1px solid var(--outline-v)" }}>
            <button className="btn btn-ghost" onClick={() => setTab(t => t - 1)} disabled={tab === 0 || saving} type="button">
              <i className="ti ti-arrow-left" style={{ fontSize: 14 }} /> Previous
            </button>
            {tab < steps.length - 1 ? (
              <button className="btn btn-filled" onClick={next} disabled={saving} type="button">
                {saving
                  ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 14 }} /> Saving…</>
                  : <>Save & Continue <i className="ti ti-arrow-right" style={{ fontSize: 14 }} /></>
                }
              </button>
            ) : (
              <div style={{ display: "flex", gap: ".75rem" }}>
                <button className="btn btn-ghost" onClick={saveSection} disabled={saving} type="button">
                  {saving ? "Saving…" : "Save Draft"}
                </button>
                <button className="btn btn-filled" onClick={handleSubmit} disabled={saving} type="button" style={{ background: "var(--success)", borderColor: "var(--success)" }}>
                  {saving
                    ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 14 }} /> Submitting…</>
                    : <><i className="ti ti-check" style={{ fontSize: 14 }} /> Submit for Approval</>
                  }
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Fixed logout button ── */}
      <button
        onClick={handleLogout}
        disabled={loggingOut}
        type="button"
        style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 100,
          display: "flex", alignItems: "center", gap: 7,
          padding: "10px 18px", borderRadius: 10,
          border: "1.5px solid var(--outline-v)",
          background: "#fff",
          boxShadow: "0 2px 12px rgba(0,0,0,0.10)",
          cursor: loggingOut ? "not-allowed" : "pointer",
          fontSize: ".84rem", fontWeight: 500,
          color: "var(--on-variant)",
        }}
      >
        {loggingOut
          ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 15 }} /> Logging out…</>
          : <><i className="ti ti-logout" style={{ fontSize: 15 }} /> Logout</>
        }
      </button>

      {showFaceCapture && (
        <FaceRegistrationModal
          mode="register"
          onClose={() => { setShowFaceCapture(false); refetchFaceRegistration(); }}
        />
      )}
    </div>
  );
}

// ── Layout constants ───────────────────────────────────────────────────────────

const ROOT_STYLE: React.CSSProperties = {
  minHeight: "100vh",
  background: "linear-gradient(140deg, #f0f4ff 0%, #e9effe 45%, #f3f0ff 100%)",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "flex-start",
  padding: "3rem 1rem 4rem",
};

const CARD_STYLE: React.CSSProperties = {
  background: "#fff",
  borderRadius: 16,
  padding: "2rem",
  boxShadow: "0 4px 24px rgba(30,78,140,0.08), 0 1px 4px rgba(0,0,0,0.04)",
  border: "1px solid rgba(30,78,140,0.08)",
};

// ── Shared: required marker ───────────────────────────────────────────────────
const Req = () => <span style={{ color: "var(--error, #dc2626)", marginLeft: 2 }}>*</span>;

// ── Tab: Personal ─────────────────────────────────────────────────────────────

function TabPersonal({ form, set }: { form: ProfileForm; set: (f: keyof ProfileForm, v: string) => void }) {
  return (
    <div>
      <div className="field-group-row">
        <div className="field-group">
          <label className="field-label">Date of Birth<Req /></label>
          <input type="date" className={INP} value={form.date_of_birth} onChange={e => set("date_of_birth", e.target.value)} />
        </div>
        <div className="field-group">
          <label className="field-label">Gender<Req /></label>
          <select className={SEL} value={form.gender} onChange={e => set("gender", e.target.value)}>
            <option value="">Select</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other / Prefer not to say</option>
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Marital Status<Req /></label>
          <select className={SEL} value={form.marital_status} onChange={e => set("marital_status", e.target.value)}>
            <option value="">Select</option>
            <option value="single">Single</option>
            <option value="married">Married</option>
            <option value="divorced">Divorced</option>
            <option value="widowed">Widowed</option>
          </select>
        </div>
      </div>
      <div className="field-group-row">
        <div className="field-group">
          <label className="field-label">Father&apos;s Name<Req /></label>
          <input className={INP} value={form.father_name} onChange={e => set("father_name", e.target.value)} placeholder="Father's full name" />
        </div>
        <div className="field-group">
          <label className="field-label">Blood Group</label>
          <select className={SEL} value={form.blood_group} onChange={e => set("blood_group", e.target.value)}>
            <option value="">Select</option>
            {["A+","A-","B+","B-","O+","O-","AB+","AB-"].map(g => <option key={g} value={g}>{g}</option>)}
          </select>
        </div>
      </div>
      <div className="field-group">
        <label className="field-label">Current Address<Req /></label>
        <textarea className={INP} rows={2} value={form.current_address} onChange={e => set("current_address", e.target.value)} placeholder="House / Flat no., Street, City, State, PIN" />
      </div>
      <div className="field-group">
        <label className="field-label">Permanent Address <span style={{ color: "var(--outline)", fontWeight: 400, fontSize: ".8rem" }}>(if different)</span></label>
        <textarea className={INP} rows={2} value={form.permanent_address} onChange={e => set("permanent_address", e.target.value)} placeholder="Leave blank if same as current" />
      </div>
    </div>
  );
}

// ── Tab: Education & Experience ───────────────────────────────────────────────

function TabEducation({ form, set }: { form: ProfileForm; set: (f: keyof ProfileForm, v: string) => void }) {
  return (
    <div>
      <p style={{ fontWeight: 600, color: "var(--on-variant)", fontSize: ".8rem", textTransform: "uppercase", letterSpacing: ".05em", marginBottom: "1rem" }}>Education</p>
      <div className="field-group-row">
        <div className="field-group">
          <label className="field-label">Highest Qualification<Req /></label>
          <input className={INP} value={form.highest_qualification} onChange={e => set("highest_qualification", e.target.value)} placeholder="e.g. B.Tech, MBA" />
        </div>
        <div className="field-group">
          <label className="field-label">Specialization</label>
          <input className={INP} value={form.specialization} onChange={e => set("specialization", e.target.value)} placeholder="e.g. Computer Science" />
        </div>
      </div>
      <div className="field-group-row">
        <div className="field-group">
          <label className="field-label">Institution / University<Req /></label>
          <input className={INP} value={form.institution} onChange={e => set("institution", e.target.value)} placeholder="College or university name" />
        </div>
        <div className="field-group">
          <label className="field-label">Year of Passing</label>
          <input type="number" className={INP} value={form.year_of_passing} onChange={e => set("year_of_passing", e.target.value)} placeholder="e.g. 2020" min={1950} max={2099} />
        </div>
      </div>
      <p style={{ fontWeight: 600, color: "var(--on-variant)", fontSize: ".8rem", textTransform: "uppercase", letterSpacing: ".05em", margin: "1.5rem 0 1rem" }}>Work Experience</p>
      <div className="field-group-row">
        <div className="field-group">
          <label className="field-label">Total Experience (years)</label>
          <input type="number" className={INP} value={form.total_experience_years} onChange={e => set("total_experience_years", e.target.value)} placeholder="e.g. 3.5" step="0.1" min={0} />
        </div>
        <div className="field-group">
          <label className="field-label">Previous Employer</label>
          <input className={INP} value={form.previous_employer} onChange={e => set("previous_employer", e.target.value)} placeholder="Company name (if any)" />
        </div>
        <div className="field-group">
          <label className="field-label">Previous Designation</label>
          <input className={INP} value={form.previous_designation} onChange={e => set("previous_designation", e.target.value)} placeholder="Job title (if any)" />
        </div>
      </div>
      <div className="field-group">
        <label className="field-label">Reason for Leaving</label>
        <textarea className={INP} rows={2} value={form.leaving_reason} onChange={e => set("leaving_reason", e.target.value)} placeholder="Optional" />
      </div>
    </div>
  );
}

// ── Tab: Bank Details ─────────────────────────────────────────────────────────

function TabBank({ form, set }: { form: ProfileForm; set: (f: keyof ProfileForm, v: string) => void }) {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, background: "#fffbea", border: "1px solid #f0c040", borderRadius: 10, padding: ".75rem 1rem", marginBottom: "1.5rem" }}>
        <i className="ti ti-alert-triangle" style={{ color: "#b07c00", fontSize: 18, flexShrink: 0 }} />
        <span style={{ fontSize: ".85rem", color: "#7c5800" }}>Bank details are used for payroll. Ensure all information matches your passbook exactly.</span>
      </div>
      <div className="field-group-row">
        <div className="field-group">
          <label className="field-label">Account Holder Name<Req /></label>
          <input className={INP} value={form.account_holder_name} onChange={e => set("account_holder_name", e.target.value)} placeholder="As printed on passbook" />
        </div>
        <div className="field-group">
          <label className="field-label">Account Type<Req /></label>
          <select className={SEL} value={form.account_type} onChange={e => set("account_type", e.target.value)}>
            <option value="">Select</option>
            <option value="savings">Savings</option>
            <option value="current">Current</option>
          </select>
        </div>
      </div>
      <div className="field-group-row">
        <div className="field-group">
          <label className="field-label">Account Number<Req /></label>
          <input className={INP} value={form.account_number} onChange={e => set("account_number", e.target.value)} placeholder="Bank account number" />
        </div>
        <div className="field-group">
          <label className="field-label">IFSC Code<Req /></label>
          <input className={INP} value={form.ifsc_code} onChange={e => set("ifsc_code", e.target.value.toUpperCase())} placeholder="e.g. SBIN0001234" maxLength={11} />
        </div>
      </div>
      <div className="field-group-row">
        <div className="field-group">
          <label className="field-label">Bank Name<Req /></label>
          <input className={INP} value={form.bank_name} onChange={e => set("bank_name", e.target.value)} placeholder="e.g. State Bank of India" />
        </div>
        <div className="field-group">
          <label className="field-label">Branch Name<Req /></label>
          <input className={INP} value={form.bank_branch_name} onChange={e => set("bank_branch_name", e.target.value)} placeholder="Branch city / locality" />
        </div>
      </div>
    </div>
  );
}

// ── Tab: Emergency Contact ────────────────────────────────────────────────────

function TabEmergency({ form, set }: { form: ProfileForm; set: (f: keyof ProfileForm, v: string) => void }) {
  return (
    <div>
      <p style={{ color: "var(--on-variant)", marginBottom: "1.25rem", fontSize: ".9rem", lineHeight: 1.6 }}>
        This person will be contacted in case of an emergency at the workplace.
      </p>
      <div className="field-group-row">
        <div className="field-group">
          <label className="field-label">Contact Name<Req /></label>
          <input className={INP} value={form.emergency_name} onChange={e => set("emergency_name", e.target.value)} placeholder="Full name" />
        </div>
        <div className="field-group">
          <label className="field-label">Relationship<Req /></label>
          <input className={INP} value={form.emergency_relationship} onChange={e => set("emergency_relationship", e.target.value)} placeholder="e.g. Spouse, Parent, Sibling" />
        </div>
      </div>
      <div className="field-group-row">
        <div className="field-group">
          <label className="field-label">Phone Number<Req /></label>
          <input className={INP} value={form.emergency_phone} onChange={e => set("emergency_phone", e.target.value)} placeholder="Mobile number" />
        </div>
        <div className="field-group">
          <label className="field-label">Email <span style={{ color: "var(--outline)", fontWeight: 400, fontSize: ".8rem" }}>(optional)</span></label>
          <input type="email" className={INP} value={form.emergency_email} onChange={e => set("emergency_email", e.target.value)} placeholder="email@example.com" />
        </div>
      </div>
    </div>
  );
}

// ── Tab: Documents ────────────────────────────────────────────────────────────

function TabDocuments({
  docs, uploadedTypes, uploading, fileRefs, onUpload,
  panNumber, onPanNumberChange, onPanCardUpload, panErr, panSaving,
}: {
  docs: UploadedDoc[];
  uploadedTypes: Set<string>;
  uploading: string | null;
  fileRefs: React.RefObject<Record<string, HTMLInputElement | null>>;
  onUpload: (docType: string, file: File) => void;
  panNumber: string;
  onPanNumberChange: (v: string) => void;
  onPanCardUpload: (file: File) => void;
  panErr: string | null;
  panSaving: boolean;
}) {
  const [preview, setPreview] = useState<UploadedDoc | null>(null);

  return (
    <>
      {preview && preview.file && (
        <DocPreviewModal
          name={preview.document_type_display}
          fileName={preview.file_name}
          fileUrl={preview.file}
          onClose={() => setPreview(null)}
        />
      )}
      <div>
        <p style={{ color: "var(--on-variant)", marginBottom: "1.25rem", fontSize: ".9rem", lineHeight: 1.6 }}>
          Upload clear scans or photos. Accepted: PDF, JPG, PNG · Max 5 MB each.
        </p>
        <div style={{ display: "flex", flexDirection: "column", gap: ".875rem" }}>
          {DOC_TYPES.map(dt => {
            const uploaded     = uploadedTypes.has(dt.value);
            const uploaded_doc = docs.find(d => d.document_type === dt.value);
            const isPan        = dt.value === "pan_card";
            const isUploading  = uploading === dt.value || (isPan && panSaving);
            const panBlocked   = isPan && !PAN_RE.test(panNumber.trim());
            return (
              <div key={dt.value} style={{
                padding: "1rem 1.25rem", borderRadius: 12,
                border: `1.5px solid ${uploaded ? "var(--success)" : "var(--outline-v)"}`,
                background: uploaded ? "var(--success-c)" : "#fff",
                transition: "all 0.2s",
              }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ width: 36, height: 36, borderRadius: 9, background: uploaded ? "var(--success)" : "var(--bg-high)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                      <i className={uploaded ? "ti ti-file-check" : "ti ti-file-upload"} style={{ color: uploaded ? "#fff" : "var(--on-variant)", fontSize: 18 }} />
                    </div>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: ".9rem", color: "var(--on-bg)" }}>{dt.label}</div>
                      {uploaded && uploaded_doc && (
                        <div style={{ fontSize: ".78rem", color: "var(--success)", marginTop: 2 }}>
                          <i className="ti ti-check" style={{ fontSize: 11 }} /> {uploaded_doc.file_name}
                        </div>
                      )}
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: ".5rem", alignItems: "center", flexShrink: 0 }}>
                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png"
                      style={{ display: "none" }}
                      ref={el => { fileRefs.current[dt.value] = el; }}
                      onChange={e => {
                        const file = e.target.files?.[0];
                        if (file) {
                          if (isPan) onPanCardUpload(file);
                          else onUpload(dt.value, file);
                        }
                        e.target.value = "";
                      }}
                    />
                    {uploaded && uploaded_doc?.file && (
                      <button
                        className="btn btn-ghost"
                        style={{ fontSize: ".83rem" }}
                        onClick={() => setPreview(uploaded_doc)}
                        type="button"
                      >
                        <i className="ti ti-eye" style={{ fontSize: 13 }} /> View
                      </button>
                    )}
                    <button
                      className="btn btn-ghost"
                      style={{ fontSize: ".83rem", borderColor: uploaded ? "var(--success)" : undefined, color: uploaded ? "var(--success)" : undefined }}
                      onClick={() => fileRefs.current[dt.value]?.click()}
                      disabled={isUploading || panBlocked}
                      title={panBlocked ? "Enter a valid PAN number first" : undefined}
                      type="button"
                    >
                      {isUploading
                        ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 13 }} /> Uploading…</>
                        : uploaded ? "Replace" : "Upload"
                      }
                    </button>
                  </div>
                </div>
                {isPan && (
                  <div style={{ marginTop: ".75rem", paddingTop: ".75rem", borderTop: "1px solid var(--outline-v)" }}>
                    <label className="field-label">PAN Number<Req /></label>
                    <input
                      className={INP}
                      style={{ maxWidth: 220 }}
                      maxLength={10}
                      value={panNumber}
                      onChange={e => onPanNumberChange(e.target.value.toUpperCase())}
                      placeholder="e.g. ABCDE1234F"
                    />
                    {panErr ? (
                      <div style={{ fontSize: ".78rem", color: "var(--error, #dc2626)", marginTop: 4 }}>{panErr}</div>
                    ) : (
                      <div style={{ fontSize: ".72rem", color: "var(--on-variant)", marginTop: 4 }}>
                        Checked against every other employee before the upload goes through — enter it first.
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

// ── Tab: Face ID ──────────────────────────────────────────────────────────────
// Only rendered when the admin's org-wide Face ID Verification toggle
// (Attendance Settings) is mandatory — see faceMandatory above. Capture goes
// through the same FaceRegistrationModal/useFaceRegistrationCapture flow used
// on the Profile page; "registered" here just means submitted — HR approval
// happens afterwards, same bar as the Documents step above.

function TabFaceId({
  registration, onRegister,
}: {
  registration: Partial<FaceRegistrationRequest> | null;
  onRegister: () => void;
}) {
  const status = registration?.status;

  return (
    <div>
      <p style={{ color: "var(--on-variant)", marginBottom: "1.25rem", fontSize: ".9rem", lineHeight: 1.6 }}>
        Your organisation requires a registered face ID for web clock-in/out. Register once here —
        we run a quick liveness check to confirm it&apos;s really you, then send it to HR for approval.
      </p>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: "1rem",
        padding: "1rem 1.25rem", borderRadius: 12,
        border: `1.5px solid ${status ? "var(--success)" : "var(--outline-v)"}`,
        background: status ? "var(--success-c)" : "#fff",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 9, background: status ? "var(--success)" : "var(--bg-high)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
            <i className="ti ti-face-id" style={{ color: status ? "#fff" : "var(--on-variant)", fontSize: 18 }} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: ".9rem", color: "var(--on-bg)" }}>
              {status === "approved" && "Face ID approved"}
              {status === "pending" && "Face ID submitted — pending HR approval"}
              {status === "rejected" && "Face ID rejected — please register again"}
              {!status && "Face ID not yet registered"}
            </div>
          </div>
        </div>
        <button
          className="btn btn-ghost"
          style={{ fontSize: ".83rem", borderColor: status ? "var(--success)" : undefined, color: status ? "var(--success)" : undefined }}
          onClick={onRegister}
          type="button"
        >
          {status === "approved" ? "Update" : status ? "Register Again" : "Register Face ID"}
        </button>
      </div>
    </div>
  );
}

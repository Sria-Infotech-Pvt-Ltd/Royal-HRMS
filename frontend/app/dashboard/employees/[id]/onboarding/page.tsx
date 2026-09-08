"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import type { OnboardingFieldConfigByStep, CustomFieldFileValue } from "@/types/onboardingFieldConfig";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import type { ProfileForm } from "@/app/onboarding/_types";
import DynamicStepFields from "@/app/onboarding/_components/DynamicStepFields";
import TabDocuments, { type UploadedDoc } from "@/app/onboarding/_components/TabDocuments";

// HR/Admin-side onboarding wizard — fills in an employee's onboarding profile
// on their behalf (walk-in hires, or anyone who can't complete it themselves).
// Reuses the exact same step-field components as the self-service wizard
// (app/onboarding/page.tsx); the container logic here is deliberately
// simpler — no step-locking (HR can jump freely), no login/logout chrome,
// and Face ID is handled by pointing at the existing Face ID Registrations
// admin page rather than an inline capture flow (that's an in-person capture
// UX, not something to half-build here).

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
  { label: "Personal",               icon: "ti-user"          },
  { label: "Education & Experience", icon: "ti-school"        },
  { label: "Bank Details",           icon: "ti-building-bank" },
  { label: "Emergency Contact",      icon: "ti-urgent"        },
  { label: "Documents",              icon: "ti-files"         },
];

export default function HREmployeeOnboardingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const canEdit    = usePermission("onboarding.edit");
  const canApprove = usePermission("onboarding.approve");

  const [employeeUuid, setEmployeeUuid] = useState<string>("");
  const [employeeName, setEmployeeName] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [tab, setTab] = useState(0);
  const [form, setForm] = useState<ProfileForm>(EMPTY);
  const [customValues, setCustomValues] = useState<Record<string, string>>({});
  const [docs, setDocs] = useState<UploadedDoc[]>([]);
  const [customFileValues, setCustomFileValues] = useState<CustomFieldFileValue[]>([]);
  const [fieldConfig, setFieldConfig] = useState<OnboardingFieldConfigByStep>({});
  const [docTypeConfig, setDocTypeConfig] = useState<DocumentTypeConfig[]>([]);
  const docTypes = docTypeConfig.filter(t => t.visible).sort((a, b) => a.order - b.order);
  const uploadedTypes = new Set(docs.map(d => d.document_type));

  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [uploadingFileKey, setUploadingFileKey] = useState<string | null>(null);
  const [fileUploadError, setFileUploadError] = useState<string | null>(null);
  const [panErr, setPanErr] = useState<string | null>(null);
  const [panSaving, setPanSaving] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [approving, setApproving] = useState(false);
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // ── Load employee + onboarding data ─────────────────────────────────────
  useEffect(() => {
    clientApi.get(API.employees.detail(id)).then(r => {
      const raw = r.data?.data;
      if (!raw) { setNotFound(true); return; }
      setEmployeeUuid(raw.uuid);
      setEmployeeName(raw.full_name || raw.email || id);
    }).catch(() => setNotFound(true)).finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    if (!employeeUuid) return;
    clientApi.get(API.onboarding.employees.summary(employeeUuid)).then(r => {
      const d = r.data?.data ?? {};
      setForm(prev => ({ ...prev, ...Object.fromEntries(Object.keys(EMPTY).map(k => [k, d[k] ?? ""])) }));
      setCustomValues(Object.fromEntries(
        Object.entries(d.custom_field_values ?? {}).map(([k, v]) => [k, v == null ? "" : String(v)]),
      ));
    }).catch(() => {});
    clientApi.get(API.onboarding.employees.documents(employeeUuid)).then(r => {
      setDocs(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get(API.onboarding.employees.customFileFields(employeeUuid)).then(r => {
      setCustomFileValues(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get(API.onboarding.fieldConfig).then(r => setFieldConfig(r.data?.data ?? {})).catch(() => {});
    clientApi.get(API.onboarding.documentTypeConfig).then(r => setDocTypeConfig(r.data?.data ?? [])).catch(() => {});
  }, [employeeUuid]);

  function set(field: keyof ProfileForm, value: string) {
    setForm(prev => ({ ...prev, [field]: value }));
  }
  function setCustom(fieldKey: string, value: string) {
    setCustomValues(prev => ({ ...prev, [fieldKey]: value }));
  }

  const saveSection = useCallback(async (): Promise<boolean> => {
    setSaveMsg(null); setSaveErr(null);
    if (tab >= 4) return true;

    const stepConfigs = fieldConfig[String(tab)] ?? [];
    const customForStep = Object.fromEntries(
      stepConfigs.filter(c => c.is_custom && c.field_type !== "file").map(c => [c.field_key, customValues[c.field_key] ?? ""]),
    );

    setSaving(true);
    try {
      const res = await clientApi.patch<{ success: boolean; message: string }>(
        API.onboarding.employees.step(employeeUuid, tab), { ...form, ...customForStep },
      );
      if (res.data?.success === false) {
        setSaveErr(res.data.message ?? "Please fill in all required fields.");
        return false;
      }
      setSaveMsg("Saved.");
      setTimeout(() => setSaveMsg(null), 2000);
      return true;
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveErr(msg ?? "Save failed. Please try again.");
      return false;
    } finally {
      setSaving(false);
    }
  }, [tab, fieldConfig, customValues, form, employeeUuid]);

  async function handlePanCardUpload(file: File) {
    const value = form.pan_number.trim().toUpperCase();
    if (!value) { setPanErr("Enter the PAN number before uploading the PAN card."); return; }
    if (!PAN_RE.test(value)) { setPanErr("Enter a valid PAN (e.g. ABCDE1234F) — 5 letters, 4 digits, 1 letter."); return; }
    setPanErr(null);
    setPanSaving(true);
    try {
      await clientApi.patch(API.onboarding.employees.step(employeeUuid, 4), { pan_number: value });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setPanErr(msg ?? "Could not save PAN number. Please try again.");
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
      const existing = docs.find(d => d.document_type === docType);
      if (existing) await clientApi.delete(API.onboarding.documentDetail(existing.id));
      const fd = new FormData();
      fd.append("document_type", docType);
      fd.append("file", file);
      await clientApi.post(API.onboarding.employees.documents(employeeUuid), fd);
      const r = await clientApi.get(API.onboarding.employees.documents(employeeUuid));
      setDocs(r.data?.data ?? []);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveErr(msg ?? "Upload failed. Max 5 MB, PDF/JPG/PNG only.");
    } finally {
      setUploading(null);
    }
  }

  async function handleCustomFileUpload(fieldKey: string, file: File) {
    setFileUploadError(null);
    setUploadingFileKey(fieldKey);
    try {
      const formData = new FormData();
      formData.append("field_key", fieldKey);
      formData.append("file", file);
      await clientApi.post(API.onboarding.employees.customFileFields(employeeUuid), formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const { data } = await clientApi.get(API.onboarding.employees.customFileFields(employeeUuid));
      setCustomFileValues(data?.data ?? []);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setFileUploadError(msg ?? "Failed to upload file. Please try again.");
    } finally {
      setUploadingFileKey(null);
    }
  }

  async function handleCustomFileDelete(fieldKey: string, valueId: number) {
    setFileUploadError(null);
    try {
      await clientApi.delete(API.onboarding.customFileFieldDetail(valueId));
      setCustomFileValues(prev => prev.filter(v => v.id !== valueId));
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setFileUploadError(msg ?? "Failed to delete file. Please try again.");
    }
  }

  async function next() {
    const ok = await saveSection();
    if (ok && tab < STEPS.length - 1) setTab(t => t + 1);
  }

  async function handleSubmit() {
    const ok = await saveSection();
    if (!ok) return;
    setSaving(true);
    try {
      await clientApi.post(API.onboarding.employees.submit(employeeUuid), {}, { timeout: 60000 });
      setSubmitted(true);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveErr(msg ?? "Submission failed. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleApproveNow() {
    setApproving(true);
    try {
      await clientApi.post(API.onboarding.approve(employeeUuid), { decision: "approve" });
      router.push(`/dashboard/employees/${id}`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveErr(msg ?? "Approval failed — approve it from the Onboarding Approvals screen instead.");
    } finally {
      setApproving(false);
    }
  }

  const stepConfigsForTab = useMemo(() => (fieldConfig[String(tab)] ?? []).filter(c => c.visible), [fieldConfig, tab]);

  if (loading) return <div style={{ padding: 40, textAlign: "center", color: "var(--on-variant)" }}>Loading…</div>;
  if (notFound) return <div className="alert alert-error">Employee not found.</div>;
  if (!canEdit) return <div className="alert alert-error">You do not have permission to complete onboarding for this employee.</div>;

  if (submitted) {
    return (
      <div className="card" style={{ maxWidth: 560, margin: "40px auto", padding: "2.5rem", textAlign: "center" }}>
        <div style={{ width: 64, height: 64, borderRadius: "50%", background: "var(--success-c)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 1.25rem" }}>
          <i className="ti ti-check" style={{ color: "var(--success)", fontSize: 30 }} />
        </div>
        <h2 style={{ fontSize: "1.25rem", fontWeight: 700, marginBottom: ".5rem" }}>Onboarding submitted for {employeeName}</h2>
        <p style={{ color: "var(--on-variant)", marginBottom: "1.5rem" }}>
          {canApprove
            ? "You can approve it now, or leave it for review in Onboarding Approvals."
            : "It's now awaiting HR approval."}
        </p>
        {saveErr && <div className="alert alert-error" style={{ marginBottom: 16, textAlign: "left" }}>{saveErr}</div>}
        <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
          <button className="btn btn-ghost" onClick={() => router.push(`/dashboard/employees/${id}`)}>
            Back to Profile
          </button>
          {canApprove && (
            <button className="btn btn-filled" onClick={handleApproveNow} disabled={approving}>
              {approving ? "Approving…" : "Approve Now"}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Complete Onboarding — {employeeName}</div>
          <div className="page-sub">Fill in the employee&apos;s onboarding profile on their behalf.</div>
        </div>
        <button className="btn btn-ghost" onClick={() => router.push(`/dashboard/employees/${id}`)}>
          <i className="ti ti-arrow-left" /> Back
        </button>
      </div>

      <div className="tabs" style={{ marginBottom: 20 }}>
        {STEPS.map((step, i) => (
          <button
            key={step.label}
            onClick={() => setTab(i)}
            className={`tab flex items-center gap-[7px] ${tab === i ? "active" : ""}`}
            type="button"
          >
            <i className={`ti ${step.icon} text-[15px]`} />
            {step.label}
          </button>
        ))}
      </div>

      <div className="card" style={{ padding: "1.75rem" }}>
        {saveErr && <div className="alert alert-error" style={{ marginBottom: "1.25rem" }}>{saveErr}</div>}
        {saveMsg && <div className="alert alert-success" style={{ marginBottom: "1.25rem" }}>{saveMsg}</div>}

        {tab <= 3 && (
          <DynamicStepFields
            configs={stepConfigsForTab}
            form={form}
            customValues={customValues}
            onBuiltinChange={set}
            onCustomChange={setCustom}
            customFileValues={customFileValues}
            uploadingFileKey={uploadingFileKey}
            fileUploadError={fileUploadError}
            onCustomFileUpload={handleCustomFileUpload}
            onCustomFileDelete={handleCustomFileDelete}
          />
        )}
        {tab === 4 && (
          <TabDocuments
            docTypes={docTypes}
            docs={docs}
            uploadedTypes={uploadedTypes}
            uploading={uploading}
            fileRefs={fileRefs}
            onUpload={handleUpload}
            panNumber={form.pan_number}
            onPanNumberChange={v => { set("pan_number", v); setPanErr(null); }}
            onPanCardUpload={handlePanCardUpload}
            onPanValidationError={setPanErr}
            panErr={panErr}
            panSaving={panSaving}
          />
        )}

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "2rem", paddingTop: "1.25rem", borderTop: "1px solid var(--outline-v)" }}>
          <button className="btn btn-ghost" onClick={() => setTab(t => Math.max(0, t - 1))} disabled={tab === 0 || saving} type="button">
            <i className="ti ti-arrow-left" /> Previous
          </button>
          {tab < STEPS.length - 1 ? (
            <button className="btn btn-filled" onClick={next} disabled={saving} type="button">
              {saving ? "Saving…" : <>Save & Continue <i className="ti ti-arrow-right" /></>}
            </button>
          ) : (
            <div style={{ display: "flex", gap: ".75rem" }}>
              <button className="btn btn-ghost" onClick={saveSection} disabled={saving} type="button">
                {saving ? "Saving…" : "Save"}
              </button>
              <button
                className="btn btn-filled"
                onClick={handleSubmit}
                disabled={saving}
                type="button"
                style={{ background: "var(--success)", borderColor: "var(--success)" }}
              >
                {saving ? "Submitting…" : <><i className="ti ti-check" /> Submit for Approval</>}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="alert alert-info" style={{ marginTop: 20 }}>
        <i className="ti ti-info-circle" />
        <div>
          Face ID registration (if required by your organisation) isn&apos;t part of this wizard — register it
          in person from{" "}
          <a href="/dashboard/face-id-registrations" style={{ color: "var(--primary)", fontWeight: 600 }}>
            Face ID Registrations
          </a>{" "}
          before submitting, if your Attendance Settings require it.
        </div>
      </div>
    </>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import type { CompanyData } from "@/types/company";
import EntityIdentityCard from "./_components/EntityIdentityCard";
import OtherRegistrationsCard from "./_components/OtherRegistrationsCard";
import GSTRegistrationsSection from "./_components/GSTRegistrationsSection";
import DirectorsSection from "./_components/DirectorsSection";
import SignatoryCard from "./_components/SignatoryCard";
import BankDetailsCard from "./_components/BankDetailsCard";
import BusinessProfileCard from "./_components/BusinessProfileCard";
import RegionalFormatsCard from "./_components/RegionalFormatsCard";
import AddressCard from "./_components/AddressCard";
import ContactBrandingCard from "./_components/ContactBrandingCard";
import {
  EMPTY_COMPANY, ENTITY_TYPE_OPTIONS_FOREIGN, ENTITY_TYPE_OPTIONS_INDIA,
  profileCompletionPercent, validateCompany,
} from "./_data";

export default function CompanyInfoPage() {
  const router  = useRouter();
  const canEdit = usePermission("settings.edit");

  const [form,        setForm]        = useState<CompanyData>(EMPTY_COMPANY);
  const [errors,      setErrors]      = useState<ReturnType<typeof validateCompany>>({});
  const [apiError,    setApiError]    = useState<string | null>(null);
  const [loading,     setLoading]     = useState(true);
  const [saving,      setSaving]      = useState<"draft" | "validate" | null>(null);
  const [savedAt,     setSavedAt]     = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);

  // Logo state
  const [logoFile,    setLogoFile]    = useState<File | null>(null);
  const [logoPreview, setLogoPreview] = useState<string | null>(null);
  const [logoRemoved, setLogoRemoved] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // ─── Load ──────────────────────────────────────────────────────────────────

  useEffect(() => {
    (async () => {
      try {
        const res = await clientApi.get(API.settings.company);
        const d: CompanyData & { id?: number } = res.data?.data ?? {};
        if (d.id) {
          setForm({ ...EMPTY_COMPANY, ...d });
          if (d.updated_at) setSavedAt(d.updated_at);
        }
      } catch {
        // first-time setup — form stays empty
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // ─── Handlers ─────────────────────────────────────────────────────────────

  function handleField(key: keyof CompanyData, value: string | boolean) {
    setForm(prev => ({ ...prev, [key]: value }));
    setErrors(prev => ({ ...prev, [key]: undefined }));
    setSaveSuccess(false);
  }

  function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp", "image/svg+xml"].includes(file.type)) {
      setApiError("Only JPEG, PNG, WebP, or SVG files are allowed.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setApiError("Logo must be under 5 MB.");
      return;
    }
    setApiError(null);
    setLogoFile(file);
    setLogoRemoved(false);
    const reader = new FileReader();
    reader.onload = ev => setLogoPreview(ev.target?.result as string);
    reader.readAsDataURL(file);
    e.target.value = "";
  }

  function handleLogoRemove() {
    setLogoFile(null);
    setLogoPreview(null);
    setLogoRemoved(true);
  }

  async function handleSave(mode: "draft" | "validate") {
    const isDraft = mode === "draft";
    const errs = validateCompany(form, isDraft);
    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }
    setApiError(null);
    setSaveSuccess(false);
    setSaving(mode);

    try {
      const fd = new FormData();
      Object.entries(form).forEach(([key, value]) => {
        if (key === "id" || key === "logo_url" || key === "updated_at") return;
        if (typeof value === "boolean") { fd.append(key, value ? "true" : "false"); return; }
        fd.append(key, (value ?? "").toString().trim());
      });
      fd.append("is_draft", isDraft ? "true" : "false");

      if (logoFile) {
        fd.append("logo", logoFile);
      } else if (logoRemoved) {
        fd.append("remove_logo", "true");
      }

      const res = await clientApi.put(API.settings.company, fd, {
        headers: { "Content-Type": undefined },
      });
      const saved: CompanyData = res.data?.data ?? {};
      setForm(prev => ({ ...prev, ...saved }));
      if (saved.updated_at) setSavedAt(saved.updated_at);
      setLogoFile(null);
      setLogoPreview(null);
      setLogoRemoved(false);
      setSaveSuccess(true);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setApiError(e.message ?? "Failed to save company info. Please try again.");
    } finally {
      setSaving(null);
    }
  }

  // ─── Derived ──────────────────────────────────────────────────────────────

  const displayLogo = logoPreview ?? (logoRemoved ? null : (form.logo_url ?? null));
  const isIndia = form.jurisdiction === "india";
  const entityOptions = isIndia ? ENTITY_TYPE_OPTIONS_INDIA : ENTITY_TYPE_OPTIONS_FOREIGN;
  const completion = profileCompletionPercent(form);

  // ─── Loading ──────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, gap: 10, color: "var(--on-variant)" }}>
        <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "spin 1s linear infinite" }} />
        Loading company info…
      </div>
    );
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  const sectionProps = { form, errors, canEdit, onFieldChange: handleField };
  const dinLabel = isIndia ? "DIN" : "Director ID";

  return (
    <>
      {/* ── Page header ─────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <div className="page-title">Company Profile</div>
          <div className="page-sub">Statutory and business details. The form adapts to your entity type, so you only see what applies to you.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
        </div>
      </div>

      {/* ── Feedback ────────────────────────────────────────────────────── */}
      {apiError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" />
          <div>{apiError}</div>
        </div>
      )}
      {saveSuccess && (
        <div className="alert alert-success mb-16">
          <i className="ti ti-circle-check" />
          <div>Company info saved successfully.</div>
        </div>
      )}

      {savedAt && !saveSuccess && (
        <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 20, display: "flex", alignItems: "center", gap: 6 }}>
          <i className="ti ti-clock" style={{ fontSize: 14 }} />
          Last saved: {new Date(savedAt).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
        </div>
      )}

      {/* ── Jurisdiction + entity type — page-level, drives the whole form ── */}
      <div className="field-group mb-16">
        <label className="field-label"><i className="ti ti-world" style={{ marginRight: 4 }} /> Jurisdiction — where is this company registered?</label>
        <div style={{ display: "flex", gap: 8 }}>
          {(["india", "foreign"] as const).map(j => (
            <button
              key={j}
              type="button"
              className={`btn btn-sm ${form.jurisdiction === j ? "btn-filled" : "btn-ghost"}`}
              disabled={!canEdit}
              onClick={() => {
                handleField("jurisdiction", j);
                handleField("entity_type", "");
              }}
            >
              {j === "india" ? "India" : "Foreign (outside India)"}
            </button>
          ))}
        </div>
      </div>
      <div className="field-group mb-24">
        <label className="field-label"><i className="ti ti-lock" style={{ marginRight: 4 }} /> Entity type — this drives the rest of the form</label>
        <select
          className="field-input"
          value={form.entity_type}
          disabled={!canEdit}
          onChange={e => handleField("entity_type", e.target.value)}
        >
          <option value="">Select…</option>
          {entityOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      <EntityIdentityCard {...sectionProps} />
      {isIndia && <GSTRegistrationsSection canEdit={canEdit} companyPan={form.pan} />}
      {isIndia && <OtherRegistrationsCard {...sectionProps} />}
      <AddressCard {...sectionProps} />
      <DirectorsSection canEdit={canEdit} dinLabel={dinLabel} />
      <SignatoryCard {...sectionProps} />
      <BankDetailsCard {...sectionProps} />
      <BusinessProfileCard {...sectionProps} />
      <RegionalFormatsCard {...sectionProps} />
      <ContactBrandingCard
        {...sectionProps}
        displayLogo={displayLogo}
        fileRef={fileRef}
        onLogoChange={handleLogoChange}
        onLogoRemove={handleLogoRemove}
      />

      {/* ── Bottom save bar ──────────────────────────────────────────────── */}
      <div style={{
        position: "sticky", bottom: 0, display: "flex", justifyContent: "space-between",
        alignItems: "center", gap: 10, padding: "14px 0", marginTop: 8,
        background: "var(--surface)", borderTop: "1px solid var(--outline-v)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--on-variant)" }}>
          <div style={{ position: "relative", width: 22, height: 22 }}>
            <svg width="22" height="22" viewBox="0 0 22 22">
              <circle cx="11" cy="11" r="9" fill="none" stroke="var(--outline-v)" strokeWidth="3" />
              <circle
                cx="11" cy="11" r="9" fill="none" stroke="var(--primary)" strokeWidth="3"
                strokeDasharray={`${(completion / 100) * 56.5} 56.5`}
                strokeLinecap="round" transform="rotate(-90 11 11)"
              />
            </svg>
          </div>
          Profile {completion}% complete
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")} disabled={saving !== null}>
            {canEdit ? "Cancel" : "Back"}
          </button>
          {canEdit && (
            <>
              <button className="btn btn-ghost" onClick={() => handleSave("draft")} disabled={saving !== null}>
                {saving === "draft"
                  ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
                  : "Save draft"
                }
              </button>
              <button className="btn btn-filled" onClick={() => handleSave("validate")} disabled={saving !== null}>
                {saving === "validate"
                  ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
                  : <><i className="ti ti-device-floppy" /> Save &amp; validate</>
                }
              </button>
            </>
          )}
        </div>
      </div>
    </>
  );
}

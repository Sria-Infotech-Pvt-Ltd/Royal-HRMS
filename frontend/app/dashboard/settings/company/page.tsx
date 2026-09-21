"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import type { CompanyData } from "@/types/company";
import { formatDateTime } from "@/lib/formatDate";
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
  PEOPLE_CONFIG, profileCompletionPercent, sanitizeCompanyResponse, validateCompany,
} from "./_data";

const ALL_SECTION_IDS = ["entity", "gst", "other", "office", "people", "signatory", "bank", "business", "regional", "contact"] as const;

export default function CompanyInfoPage() {
  const router  = useRouter();
  const canEdit = usePermission("settings.edit");

  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());
  const [form,        setForm]        = useState<CompanyData>(EMPTY_COMPANY);
  const [errors,      setErrors]      = useState<ReturnType<typeof validateCompany>>({});
  const [apiError,    setApiError]    = useState<string | null>(null);
  const [loading,     setLoading]     = useState(true);
  const [saving,      setSaving]      = useState<"draft" | "validate" | null>(null);
  const [savedAt,     setSavedAt]     = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState(false);
  // Before the first Save & validate attempt, a blank required field stays
  // quiet rather than flashing "is required" on every card the moment the
  // page loads — but any field that already HAS a value gets real,
  // immediate feedback regardless (a bad format or a cross-field conflict
  // like a CIN's state not matching the registered office is worth
  // surfacing right away, not just at submit time).
  const [hasAttemptedSave, setHasAttemptedSave] = useState(false);
  // Remembers each jurisdiction's own last entity type selection, so
  // toggling India -> Foreign -> India restores what was there rather than
  // resetting to blank every time (see handleJurisdiction below).
  const lastEntityTypeByJurisdiction = useRef<Record<string, string>>({ india: "", foreign: "" });

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
        const raw: CompanyData & { id?: number } = res.data?.data ?? {};
        if (raw.id) {
          const d = sanitizeCompanyResponse(raw);
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

  function toggleSection(id: string) {
    setCollapsedSections(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function handleField(key: keyof CompanyData, value: string | boolean) {
    setForm(prev => {
      const next = { ...prev, [key]: value };
      const fresh = validateCompany(next, false);
      setErrors(() => {
        const merged: typeof fresh = { ...fresh };
        // Suppress a bare "is required" error on a field that's still empty
        // until the user has actually tried to save once — everything else
        // (a value that's present but malformed, or that conflicts with
        // another field) surfaces immediately, live, as intended.
        if (!hasAttemptedSave) {
          for (const k of Object.keys(merged) as (keyof CompanyData)[]) {
            if (!String(next[k] ?? "").trim()) merged[k] = undefined;
          }
        }
        return merged;
      });
      return next;
    });
    setSaveSuccess(false);
  }

  // Switching Jurisdiction used to unconditionally blank out Entity type —
  // even re-clicking the jurisdiction already selected — silently dropping
  // Directors/statutory-ID fields out of the form (52 fields down to 42) with
  // no warning that anything had changed. Now a no-op re-click does nothing,
  // and each jurisdiction remembers its own last entity type so switching
  // India -> Foreign -> India restores what was there instead of resetting it.
  function handleJurisdiction(j: "india" | "foreign") {
    if (j === form.jurisdiction) return;
    lastEntityTypeByJurisdiction.current[form.jurisdiction] = form.entity_type;
    handleField("jurisdiction", j);
    handleField("entity_type", lastEntityTypeByJurisdiction.current[j] ?? "");
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
    if (!isDraft) setHasAttemptedSave(true);
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
        // "logo" itself is excluded too — the API returns it back as the
        // stored file's URL string alongside logo_url, and Django's
        // ImageField rejects a re-submitted string as "not a file". The
        // actual upload is handled separately below via logoFile/logoRemoved.
        if (key === "id" || key === "logo" || key === "logo_url" || key === "updated_at") return;
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
      const saved = sanitizeCompanyResponse<CompanyData>(res.data?.data ?? {});
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
  const peopleConfig = PEOPLE_CONFIG[form.entity_type] ?? null;
  const visibleSectionIds = ALL_SECTION_IDS.filter(id => {
    if ((id === "gst" || id === "other") && !isIndia) return false;
    if (id === "people" && !peopleConfig) return false;
    return true;
  });
  const allSectionsCollapsed = visibleSectionIds.every(id => collapsedSections.has(id));
  function toggleAllSections() {
    setCollapsedSections(allSectionsCollapsed ? new Set() : new Set(visibleSectionIds));
  }

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

  return (
    <>
      {/* ── Page header ─────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <div className="page-title">Company Profile</div>
          <div className="page-sub">Statutory and business details. The form adapts to your entity type, so you only see what applies to you.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={toggleAllSections}>
            <i className={`ti ${allSectionsCollapsed ? "ti-chevron-down" : "ti-chevron-up"}`} />
            {allSectionsCollapsed ? "Expand all" : "Collapse all"}
          </button>
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
          Last saved: {formatDateTime(savedAt)}
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
              onClick={() => handleJurisdiction(j)}
            >
              {j === "india" ? "India" : "Foreign (outside India)"}
            </button>
          ))}
        </div>
      </div>
      <div className="field-group mb-24">
        <label className="field-label"><i className="ti ti-lock" style={{ marginRight: 4 }} /> Entity type — this drives the rest of the form</label>
        <select
          className="field-input field-select"
          value={form.entity_type}
          disabled={!canEdit}
          onChange={e => handleField("entity_type", e.target.value)}
        >
          <option value="">Select…</option>
          {entityOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>

      <EntityIdentityCard {...sectionProps} collapsed={collapsedSections.has("entity")} onToggleCollapse={() => toggleSection("entity")} />
      {isIndia && (
        <GSTRegistrationsSection
          canEdit={canEdit} companyPan={form.pan}
          collapsed={collapsedSections.has("gst")} onToggleCollapse={() => toggleSection("gst")}
        />
      )}
      {isIndia && <OtherRegistrationsCard {...sectionProps} collapsed={collapsedSections.has("other")} onToggleCollapse={() => toggleSection("other")} />}
      <AddressCard {...sectionProps} collapsed={collapsedSections.has("office")} onToggleCollapse={() => toggleSection("office")} />
      {peopleConfig && (
        <DirectorsSection
          canEdit={canEdit} config={peopleConfig}
          collapsed={collapsedSections.has("people")} onToggleCollapse={() => toggleSection("people")}
        />
      )}
      <SignatoryCard {...sectionProps} collapsed={collapsedSections.has("signatory")} onToggleCollapse={() => toggleSection("signatory")} />
      <BankDetailsCard {...sectionProps} collapsed={collapsedSections.has("bank")} onToggleCollapse={() => toggleSection("bank")} />
      <BusinessProfileCard {...sectionProps} collapsed={collapsedSections.has("business")} onToggleCollapse={() => toggleSection("business")} />
      <RegionalFormatsCard {...sectionProps} collapsed={collapsedSections.has("regional")} onToggleCollapse={() => toggleSection("regional")} />
      <ContactBrandingCard
        {...sectionProps}
        displayLogo={displayLogo}
        fileRef={fileRef}
        onLogoChange={handleLogoChange}
        onLogoRemove={handleLogoRemove}
        collapsed={collapsedSections.has("contact")} onToggleCollapse={() => toggleSection("contact")}
      />

      {/* ── Bottom save bar ──────────────────────────────────────────────── */}
      {/* DashboardShell's <main> carries its own bottom padding (p-4 md:p-6).
          `position: sticky` locks to the scroll container's PADDING-BOX edge
          regardless of the element's own margin — a negative margin changes
          how much flow space the bar reserves, but not where "bottom: 0"
          snaps to, so it left a persistent 16-24px gap below the bar
          (verified via a live Playwright check: bar bottom stayed 24px short
          of main's true bottom with -mb-6 alone). What actually cancels the
          parent's padding is offsetting `bottom` itself by that same amount. */}
      <div
        className="sticky -bottom-4 md:-bottom-6"
        style={{
          display: "flex", justifyContent: "space-between",
          alignItems: "center", gap: 10, paddingTop: 14, paddingBottom: 14, marginTop: 8,
          background: "var(--surface)", borderTop: "1px solid var(--outline-v)",
        }}
      >
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

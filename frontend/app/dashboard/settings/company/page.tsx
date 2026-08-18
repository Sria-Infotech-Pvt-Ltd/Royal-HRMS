"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import FinancialYearSection from "./_components/FinancialYearSection";

// ─── Indian states / UTs ──────────────────────────────────────────────────────

const STATES = [
  "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
  "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
  "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
  "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
  "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
  "Andaman and Nicobar Islands", "Chandigarh",
  "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
  "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
];

// ─── Types ────────────────────────────────────────────────────────────────────

type CompanyData = {
  id?:            number;
  company_name:   string;
  trade_name:     string;
  logo_url?:      string | null;
  gstin:          string;
  cin:            string;
  pan:            string;
  tan:            string;
  address:        string;
  city:           string;
  state:          string;
  pin_code:       string;
  website:        string;
  official_phone: string;
  brand_color:    string;
  updated_at?:    string;
};

type FieldErrors = Partial<Record<
  'company_name' | 'gstin' | 'cin' | 'pan' | 'tan' |
  'address' | 'city' | 'state' | 'pin_code' | 'website' | 'official_phone',
  string
>>;

const EMPTY: CompanyData = {
  company_name: "", trade_name: "",
  gstin: "", cin: "", pan: "", tan: "",
  address: "", city: "", state: "", pin_code: "",
  website: "", official_phone: "", brand_color: "",
};

// ─── Validators ───────────────────────────────────────────────────────────────

const GSTIN_RE = /^\d{2}[A-Z]{5}\d{4}[A-Z][A-Z1-9]Z[A-Z\d]$/;
const PAN_RE   = /^[A-Z]{5}\d{4}[A-Z]$/;
const CIN_RE   = /^[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$/;
const TAN_RE   = /^[A-Z]{4}\d{5}[A-Z]$/;
const PIN_RE   = /^\d{6}$/;
const PHONE_RE = /^\+?[\d\s\-()\./]{7,20}$/;

function validate(f: CompanyData): FieldErrors {
  const e: FieldErrors = {};
  if (!f.company_name.trim())                              e.company_name   = "Company name is required.";
  if (!f.gstin.trim())                                     e.gstin          = "GSTIN is required.";
  else if (!GSTIN_RE.test(f.gstin.toUpperCase()))          e.gstin          = "Enter a valid 15-character GSTIN.";
  if (!f.cin.trim())                                       e.cin            = "CIN is required.";
  else if (!CIN_RE.test(f.cin.toUpperCase()))              e.cin            = "Enter a valid CIN (e.g. U74999MH2020PTC123456).";
  if (!f.pan.trim())                                       e.pan            = "PAN is required.";
  else if (!PAN_RE.test(f.pan.toUpperCase()))              e.pan            = "Enter a valid 10-character PAN.";
  if (!f.tan.trim())                                       e.tan            = "TAN is required.";
  else if (!TAN_RE.test(f.tan.toUpperCase()))              e.tan            = "Enter a valid 10-character TAN.";
  if (!f.address.trim())                                   e.address        = "Address is required.";
  if (!f.city.trim())                                      e.city           = "City is required.";
  if (!f.state)                                            e.state          = "State / UT is required.";
  if (!f.pin_code.trim())                                  e.pin_code       = "PIN code is required.";
  else if (!PIN_RE.test(f.pin_code))                       e.pin_code       = "PIN code must be exactly 6 digits.";
  if (f.website && !f.website.startsWith("http://") && !f.website.startsWith("https://"))
                                                           e.website        = "Must start with http:// or https://.";
  if (f.official_phone && !PHONE_RE.test(f.official_phone)) e.official_phone = "Enter a valid phone number.";
  return e;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function CompanyInfoPage() {
  const router    = useRouter();
  const canEdit   = usePermission("settings.edit");

  const [form,        setForm]        = useState<CompanyData>(EMPTY);
  const [errors,      setErrors]      = useState<FieldErrors>({});
  const [apiError,    setApiError]    = useState<string | null>(null);
  const [loading,     setLoading]     = useState(true);
  const [saving,      setSaving]      = useState(false);
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
        const d: CompanyData = res.data?.data ?? {};
        if (d.id) {
          setForm({
            company_name:   d.company_name   ?? "",
            trade_name:     d.trade_name     ?? "",
            gstin:          d.gstin          ?? "",
            cin:            d.cin            ?? "",
            pan:            d.pan            ?? "",
            tan:            d.tan            ?? "",
            address:        d.address        ?? "",
            city:           d.city           ?? "",
            state:          d.state          ?? "",
            pin_code:       d.pin_code       ?? "",
            website:        d.website        ?? "",
            official_phone: d.official_phone ?? "",
            brand_color:    d.brand_color     ?? "",
            logo_url:       d.logo_url       ?? null,
          });
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

  function handleField(key: keyof CompanyData, value: string) {
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

  async function handleSave() {
    const errs = validate(form);
    if (Object.keys(errs).length) {
      setErrors(errs);
      return;
    }
    setApiError(null);
    setSaveSuccess(false);
    setSaving(true);

    try {
      const fd = new FormData();
      fd.append("company_name",   form.company_name.trim());
      fd.append("trade_name",     form.trade_name.trim());
      fd.append("gstin",          form.gstin.trim().toUpperCase());
      fd.append("cin",            form.cin.trim().toUpperCase());
      fd.append("pan",            form.pan.trim().toUpperCase());
      fd.append("tan",            form.tan.trim().toUpperCase());
      fd.append("address",        form.address.trim());
      fd.append("city",           form.city.trim());
      fd.append("state",          form.state);
      fd.append("pin_code",       form.pin_code.trim());
      fd.append("website",        form.website.trim());
      fd.append("official_phone", form.official_phone.trim());
      fd.append("brand_color",    form.brand_color.trim());

      if (logoFile) {
        fd.append("logo", logoFile);
      } else if (logoRemoved) {
        fd.append("remove_logo", "true");
      }

      const res = await clientApi.put(API.settings.company, fd, {
        headers: { "Content-Type": undefined },
      });
      const saved: CompanyData = res.data?.data ?? {};
      setForm(prev => ({ ...prev, logo_url: saved.logo_url ?? null }));
      if (saved.updated_at) setSavedAt(saved.updated_at);
      setLogoFile(null);
      setLogoPreview(null);
      setLogoRemoved(false);
      setSaveSuccess(true);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setApiError(e.message ?? "Failed to save company info. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  // ─── Derived ──────────────────────────────────────────────────────────────

  const displayLogo = logoPreview ?? (logoRemoved ? null : (form.logo_url ?? null));

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

  return (
    <>
      {/* ── Page header ─────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <div className="page-title">Company Information</div>
          <div className="page-sub">Legal entity details, statutory identifiers, and registered address</div>
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

      {/* ── Financial Year Configuration (saved independently of the form below) ── */}
      <FinancialYearSection />

      {/* ── Section 1: Branding ─────────────────────────────────────────── */}
      <div className="card mb-24">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-building" /> Branding</div>
        </div>
        <div style={{ padding: "20px 24px" }}>
          {/* Logo upload */}
          <div style={{ display: "flex", alignItems: "flex-start", gap: 20, marginBottom: 24, paddingBottom: 20, borderBottom: "1px solid var(--outline-v)" }}>
            <div style={{
              width: 80, height: 80, borderRadius: 10,
              border: "1.5px dashed var(--outline-v)", overflow: "hidden",
              background: displayLogo
                ? "repeating-conic-gradient(#e5e7eb 0% 25%, #fff 0% 50%) 0 0 / 12px 12px"
                : "var(--bg-low)",
              flexShrink: 0,
              display: "flex", alignItems: "center", justifyContent: "center",
            }}>
              {displayLogo
                ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img src={displayLogo} alt="Logo" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
                )
                : <i className="ti ti-photo" style={{ fontSize: 28, color: "var(--outline)" }} />
              }
            </div>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 3 }}>Company Logo</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 10 }}>
                JPEG, PNG, WebP or SVG · Max 5 MB
              </div>
              {canEdit && (
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn btn-ghost btn-sm" type="button" onClick={() => fileRef.current?.click()}>
                    <i className="ti ti-upload" /> {displayLogo ? "Change" : "Upload"}
                  </button>
                  {displayLogo && (
                    <button className="btn btn-ghost btn-sm" type="button" onClick={handleLogoRemove}>
                      <i className="ti ti-trash" /> Remove
                    </button>
                  )}
                </div>
              )}
              {canEdit && (
                <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp,image/svg+xml" style={{ display: "none" }} onChange={handleLogoChange} />
              )}
            </div>
          </div>

          {/* Company name + trade name */}
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Company Name <span style={{ color: "var(--error)" }}>*</span></label>
              <input
                className={`field-input${errors.company_name ? " field-error" : ""}`}
                value={form.company_name}
                onChange={e => handleField("company_name", e.target.value)}
                placeholder="Registered company name"
              />
              {errors.company_name && <div className="field-error-msg">{errors.company_name}</div>}
            </div>
            <div className="field-group">
              <label className="field-label">Trade Name</label>
              <input
                className="field-input"
                value={form.trade_name}
                onChange={e => handleField("trade_name", e.target.value)}
                placeholder="DBA or brand name (optional)"
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── Section 2: Legal & Statutory ────────────────────────────────── */}
      <div className="card mb-24">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-license" /> Legal &amp; Statutory</div>
        </div>
        <div className="form-row cols-2" style={{ padding: "20px 24px" }}>
          <div className="field-group">
            <label className="field-label">GSTIN <span style={{ color: "var(--error)" }}>*</span></label>
            <input
              className={`field-input${errors.gstin ? " field-error" : ""}`}
              value={form.gstin}
              onChange={e => handleField("gstin", e.target.value.toUpperCase())}
              placeholder="22AAAAA0000A1Z5"
              maxLength={15}
            />
            {errors.gstin && <div className="field-error-msg">{errors.gstin}</div>}
          </div>
          <div className="field-group">
            <label className="field-label">CIN <span style={{ color: "var(--error)" }}>*</span></label>
            <input
              className={`field-input${errors.cin ? " field-error" : ""}`}
              value={form.cin}
              onChange={e => handleField("cin", e.target.value.toUpperCase())}
              placeholder="U74999MH2020PTC123456"
              maxLength={21}
            />
            {errors.cin && <div className="field-error-msg">{errors.cin}</div>}
          </div>
          <div className="field-group">
            <label className="field-label">PAN <span style={{ color: "var(--error)" }}>*</span></label>
            <input
              className={`field-input${errors.pan ? " field-error" : ""}`}
              value={form.pan}
              onChange={e => handleField("pan", e.target.value.toUpperCase())}
              placeholder="AAAAA0000A"
              maxLength={10}
            />
            {errors.pan && <div className="field-error-msg">{errors.pan}</div>}
          </div>
          <div className="field-group">
            <label className="field-label">TAN <span style={{ color: "var(--error)" }}>*</span></label>
            <input
              className={`field-input${errors.tan ? " field-error" : ""}`}
              value={form.tan}
              onChange={e => handleField("tan", e.target.value.toUpperCase())}
              placeholder="PNEA12345B"
              maxLength={10}
            />
            {errors.tan && <div className="field-error-msg">{errors.tan}</div>}
          </div>
        </div>
      </div>

      {/* ── Section 3: Registered Address ───────────────────────────────── */}
      <div className="card mb-24">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-map-pin" /> Registered Address</div>
        </div>
        <div style={{ padding: "20px 24px" }}>
          <div className="field-group mb-16">
            <label className="field-label">Address <span style={{ color: "var(--error)" }}>*</span></label>
            <textarea
              className={`field-input${errors.address ? " field-error" : ""}`}
              value={form.address}
              onChange={e => handleField("address", e.target.value)}
              placeholder="Street address, building, floor…"
              rows={2}
            />
            {errors.address && <div className="field-error-msg">{errors.address}</div>}
          </div>
          <div className="form-row cols-3">
            <div className="field-group">
              <label className="field-label">City <span style={{ color: "var(--error)" }}>*</span></label>
              <input
                className={`field-input${errors.city ? " field-error" : ""}`}
                value={form.city}
                onChange={e => handleField("city", e.target.value)}
                placeholder="Mumbai"
              />
              {errors.city && <div className="field-error-msg">{errors.city}</div>}
            </div>
            <div className="field-group">
              <label className="field-label">State / UT <span style={{ color: "var(--error)" }}>*</span></label>
              <select
                className={`field-input${errors.state ? " field-error" : ""}`}
                value={form.state}
                onChange={e => handleField("state", e.target.value)}
              >
                <option value="">Select…</option>
                {STATES.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
              {errors.state && <div className="field-error-msg">{errors.state}</div>}
            </div>
            <div className="field-group">
              <label className="field-label">PIN Code <span style={{ color: "var(--error)" }}>*</span></label>
              <input
                className={`field-input${errors.pin_code ? " field-error" : ""}`}
                value={form.pin_code}
                onChange={e => handleField("pin_code", e.target.value.replace(/\D/g, "").slice(0, 6))}
                placeholder="400001"
                maxLength={6}
              />
              {errors.pin_code && <div className="field-error-msg">{errors.pin_code}</div>}
            </div>
          </div>
        </div>
      </div>

      {/* ── Section 4: Contact ──────────────────────────────────────────── */}
      <div className="card mb-24">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-phone" /> Contact</div>
        </div>
        <div className="form-row cols-2" style={{ padding: "20px 24px" }}>
          <div className="field-group">
            <label className="field-label">Website</label>
            <input
              className={`field-input${errors.website ? " field-error" : ""}`}
              value={form.website}
              onChange={e => handleField("website", e.target.value)}
              placeholder="https://royalstaffing.in"
              type="url"
            />
            {errors.website && <div className="field-error-msg">{errors.website}</div>}
          </div>
          <div className="field-group">
            <label className="field-label">Official Phone</label>
            <input
              className={`field-input${errors.official_phone ? " field-error" : ""}`}
              value={form.official_phone}
              onChange={e => handleField("official_phone", e.target.value)}
              placeholder="+91 98765 43210"
              type="tel"
            />
            {errors.official_phone && <div className="field-error-msg">{errors.official_phone}</div>}
          </div>
        </div>
      </div>

      {/* ── Section 5: Branding ─────────────────────────────────────────── */}
      <div className="card mb-24">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-palette" /> Branding</div>
        </div>
        <div className="form-row cols-2" style={{ padding: "20px 24px" }}>
          <div className="field-group">
            <label className="field-label">Accent color</label>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <input
                type="color"
                value={form.brand_color || "#1e4e8c"}
                onChange={e => handleField("brand_color", e.target.value)}
                style={{ width: 44, height: 36, padding: 2, border: "1.5px solid var(--outline-v)", borderRadius: "var(--radius)", cursor: "pointer" }}
              />
              <input
                className="field-input"
                value={form.brand_color}
                onChange={e => handleField("brand_color", e.target.value)}
                placeholder="#1e4e8c"
                style={{ flex: 1 }}
              />
            </div>
            <p style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
              Used on your own login page and dashboard in place of the default color. Leave blank to use the default.
            </p>
          </div>
        </div>
      </div>

      {/* ── Bottom save bar ──────────────────────────────────────────────── */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 10, paddingBottom: 32 }}>
        {savedAt && (
          <span style={{ fontSize: 12, color: "var(--on-variant)", marginRight: "auto", display: "flex", alignItems: "center", gap: 5 }}>
            <i className="ti ti-clock" style={{ fontSize: 13 }} />
            Last saved: {new Date(savedAt).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })}
          </span>
        )}
        <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")} disabled={saving}>
          {canEdit ? "Cancel" : "Back"}
        </button>
        {canEdit && (
          <button className="btn btn-filled" onClick={handleSave} disabled={saving}>
            {saving
              ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
              : <><i className="ti ti-device-floppy" /> Save Changes</>
            }
          </button>
        )}
      </div>
    </>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { buildEmailPreview, type CompanyInfo } from "@/lib/emailPreview";
import EditTemplateModal from "./_components/EditTemplateModal";
import Modal from "@/components/Modal";
import {
  EMAIL_TEMPLATES_BASE, EMAIL_TEMPLATE_CATEGORIES, emailTemplateDetail, emailTemplatePreview,
  flattenTemplates, TYPE_META, catValue,
  type ApiEmailTemplate, type ApiEmailTemplatesResponse, type ApiTemplateCategory, type TemplateForm,
} from "./_data";

const FALLBACK_META = { label: "Other", color: "var(--on-variant)", icon: "ti-tag" };

interface BrandingForm {
  company_name:   string;
  website:        string;
  address:        string;
  city:           string;
  state:          string;
  official_phone: string;
}

const EMPTY_BRANDING: BrandingForm = {
  company_name: "", website: "", address: "", city: "", state: "", official_phone: "",
};

interface BirthdaySettingsForm {
  is_enabled:                     boolean;
  banner_message_template:        string;
  employee_notification_template: string;
  team_notification_template:     string;
  manager_notification_template:  string;
}

const EMPTY_BIRTHDAY: BirthdaySettingsForm = {
  is_enabled:                     true,
  banner_message_template:        "",
  employee_notification_template: "",
  team_notification_template:     "",
  manager_notification_template:  "",
};

export default function EmailTemplatesPage() {
  const router = useRouter();

  const [templates,    setTemplates]    = useState<ApiEmailTemplate[]>([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState<string | null>(null);
  const [categories,   setCategories]   = useState<ApiTemplateCategory[]>([]);

  const [editing,        setEditing]        = useState<ApiEmailTemplate | null | "add">(null);
  const [viewing,        setViewing]        = useState<ApiEmailTemplate | null>(null);
  const [previewHtml,    setPreviewHtml]    = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);

  const [company, setCompany] = useState<CompanyInfo | null>(null);

  // ── Branding state ──────────────────────────────────────────────────────────
  const [brandingOpen,   setBrandingOpen]   = useState(false);
  const [brandingForm,   setBrandingForm]   = useState<BrandingForm>(EMPTY_BRANDING);
  const [brandingSaving, setBrandingSaving] = useState(false);
  const [logoFile,       setLogoFile]       = useState<File | null>(null);
  const [logoPreview,    setLogoPreview]    = useState<string | null>(null);
  const logoInputRef = useRef<HTMLInputElement>(null);

  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [toast,  setToast]  = useState<{ msg: string; ok: boolean } | null>(null);

  // ── Birthday wishes state — merged in from the standalone Birthday Wishes
  // settings page (the master enable toggle and the banner/notification copy
  // aren't email templates, but they're the birthday feature's only other
  // configurable pieces, so they live here as a second settings card). ──
  const [birthdayOpen,    setBirthdayOpen]    = useState(false);
  const [birthday,        setBirthday]        = useState<BirthdaySettingsForm>(EMPTY_BIRTHDAY);
  const [birthdayBase,    setBirthdayBase]    = useState<BirthdaySettingsForm>(EMPTY_BIRTHDAY);
  const [birthdaySaving,  setBirthdaySaving]  = useState(false);

  useEffect(() => { loadData(); loadCategories(); loadCompany(); loadBirthdaySettings(); }, []);

  async function loadBirthdaySettings() {
    try {
      const res  = await clientApi.get<{ data: BirthdaySettingsForm }>(API.hrms.birthdaySettings);
      const data = res.data?.data;
      if (data) { setBirthday(data); setBirthdayBase(data); }
    } catch { /* card just keeps showing the default form */ }
  }

  async function saveBirthdaySettings() {
    setBirthdaySaving(true);
    try {
      const res = await clientApi.patch<{ data: BirthdaySettingsForm }>(API.hrms.birthdaySettings, birthday);
      const updated = res.data?.data ?? birthday;
      setBirthday(updated);
      setBirthdayBase(updated);
      setBirthdayOpen(false);
      showToast("Birthday wishes settings updated");
    } catch (err: unknown) {
      showToast((err as { message?: string }).message ?? "Failed to save birthday settings", false);
    } finally {
      setBirthdaySaving(false);
    }
  }

  function cancelBirthday() {
    setBirthday(birthdayBase);
    setBirthdayOpen(false);
  }

  async function loadCompany() {
    try {
      const res = await clientApi.get<{ data: CompanyInfo }>(API.settings.company);
      const data = res.data?.data ?? null;
      setCompany(data);
      if (data) {
        setBrandingForm({
          company_name:   data.company_name   ?? "",
          website:        data.website        ?? "",
          address:        data.address        ?? "",
          city:           data.city           ?? "",
          state:          data.state          ?? "",
          official_phone: data.official_phone ?? "",
        });
      }
    } catch { /* preview falls back gracefully */ }
  }

  async function loadCategories() {
    try {
      const res  = await clientApi.get(EMAIL_TEMPLATE_CATEGORIES);
      const data = res.data?.data ?? res.data;
      const cats = Array.isArray(data) ? data : (Array.isArray(data?.results) ? data.results : []);
      setCategories(cats);
    } catch { /* silently fall back */ }
  }

  function showToast(msg: string, ok = true) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  }

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const res = await clientApi.get(EMAIL_TEMPLATES_BASE);
      const envelope = res.data?.data;
      const grouped  = (envelope?.results ?? envelope) as ApiEmailTemplatesResponse;
      setTemplates(flattenTemplates(grouped));
    } catch (err: unknown) {
      setError((err as { message?: string }).message ?? "Failed to load email templates");
    } finally {
      setLoading(false);
    }
  }

  // ── Branding save ───────────────────────────────────────────────────────────

  async function saveBranding() {
    setBrandingSaving(true);
    try {
      const fd = new FormData();
      fd.append("company_name",   brandingForm.company_name);
      fd.append("website",        brandingForm.website);
      fd.append("address",        brandingForm.address);
      fd.append("city",           brandingForm.city);
      fd.append("state",          brandingForm.state);
      fd.append("official_phone", brandingForm.official_phone);
      if (logoFile) fd.append("logo", logoFile, logoFile.name);

      const res = await clientApi.patch<{ data: CompanyInfo }>(API.settings.company, fd);
      const updated = res.data?.data;
      if (updated) {
        setCompany(updated);
        setBrandingForm({
          company_name:   updated.company_name   ?? "",
          website:        updated.website        ?? "",
          address:        updated.address        ?? "",
          city:           updated.city           ?? "",
          state:          updated.state          ?? "",
          official_phone: updated.official_phone ?? "",
        });
      }
      setLogoFile(null);
      setLogoPreview(null);
      setBrandingOpen(false);
      showToast("Email branding updated");
    } catch (err: unknown) {
      showToast((err as { message?: string }).message ?? "Failed to save branding", false);
    } finally {
      setBrandingSaving(false);
    }
  }

  function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLogoFile(file);
    const url = URL.createObjectURL(file);
    setLogoPreview(url);
  }

  function cancelBranding() {
    setBrandingOpen(false);
    setLogoFile(null);
    setLogoPreview(null);
    if (company) {
      setBrandingForm({
        company_name:   company.company_name   ?? "",
        website:        company.website        ?? "",
        address:        company.address        ?? "",
        city:           company.city           ?? "",
        state:          company.state          ?? "",
        official_phone: company.official_phone ?? "",
      });
    }
  }

  // Derived footer text (mirrors emailPreview.ts)
  const footerAddr   = [company?.address, company?.city, company?.state].filter(Boolean).join(", ");
  const footerParts  = [company?.website, footerAddr].filter(Boolean);
  const footerText   = footerParts.join("  |  ") || company?.company_name || "—";
  const currentLogo  = logoPreview ?? company?.logo_url ?? company?.logo ?? "";

  // ── Template CRUD ───────────────────────────────────────────────────────────

  async function handleCreate(form: TemplateForm) {
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append("name",                form.name);
      fd.append("display_name",        form.display_name);
      fd.append("template_type",       form.template_type);
      fd.append("subject",             form.subject);
      fd.append("body",                form.body);
      fd.append("available_variables", JSON.stringify(form.available_variables));
      form.attachments.forEach(f => fd.append("attachments", f, f.name));
      const res = await clientApi.post(EMAIL_TEMPLATES_BASE, fd);
      const created: ApiEmailTemplate = res.data.data ?? res.data;
      setTemplates(prev => [...prev, created]);
      setEditing(null);
      showToast("Email template created");
    } catch (err: unknown) {
      showToast((err as { message?: string }).message ?? "Failed to create template", false);
    } finally {
      setSaving(false);
    }
  }

  async function handleUpdate(form: TemplateForm) {
    if (!editing || editing === "add") return;
    const target = editing as ApiEmailTemplate;
    setSaving(true);
    try {
      const fd = new FormData();
      fd.append("subject",             form.subject);
      fd.append("body",                form.body);
      fd.append("available_variables", JSON.stringify(form.available_variables));
      form.attachments.forEach(f => fd.append("attachments", f, f.name));
      await clientApi.patch(emailTemplateDetail(target.id), fd);
      setTemplates(prev => prev.map(t => t.id === target.id ? { ...t, subject: form.subject, body: form.body } : t));
      setEditing(null);
      showToast("Email template updated");
    } catch (err: unknown) {
      showToast((err as { message?: string }).message ?? "Failed to update template", false);
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(template: ApiEmailTemplate) {
    const next = !template.is_active;
    setTemplates(prev => prev.map(t => t.id === template.id ? { ...t, is_active: next } : t));
    try {
      await clientApi.patch(emailTemplateDetail(template.id), { is_active: next });
      showToast(`Template ${next ? "activated" : "deactivated"}`);
    } catch (err: unknown) {
      setTemplates(prev => prev.map(t => t.id === template.id ? { ...t, is_active: !next } : t));
      showToast((err as { message?: string }).message ?? "Failed to update template", false);
    }
  }

  async function openPreview(template: ApiEmailTemplate) {
    setViewing(template);
    setPreviewHtml(null);
    setPreviewLoading(true);
    try {
      const res  = await clientApi.get(emailTemplatePreview(template.id));
      const body = res.data.data?.preview ?? res.data?.preview ?? template.body;
      setPreviewHtml(buildEmailPreview(body, company));
    } catch {
      setPreviewHtml(buildEmailPreview(template.body, company));
    } finally {
      setPreviewLoading(false);
    }
  }

  // ── Filtering + grouping ───────────────────────────────────────────────────

  const q = search.toLowerCase();
  const filtered = templates.filter(t =>
    (t.display_name ?? "").toLowerCase().includes(q) ||
    (t.template_type_display ?? "").toLowerCase().includes(q) ||
    (t.description ?? "").toLowerCase().includes(q)
  );

  const typeGroups = filtered.reduce<Record<string, ApiEmailTemplate[]>>((acc, t) => {
    (acc[t.template_type] ??= []).push(t);
    return acc;
  }, {});

  const catByCode    = Object.fromEntries(categories.map(c => [catValue(c), c]));
  const catCodes     = categories.map(c => catValue(c));
  const extraTypes   = Object.keys(typeGroups).filter(t => !catCodes.includes(t));
  const orderedTypes = [...catCodes.filter(code => typeGroups[code]), ...extraTypes];

  const isAddMode    = editing === "add";
  const editTemplate = editing && editing !== "add" ? editing : null;

  return (
    <>
      {/* Toast */}
      {toast && (
        <div className="et-toast" style={{ position: "fixed", top: 16, right: 20, zIndex: 9999, display: "flex", alignItems: "center", gap: 10, padding: "12px 18px", background: toast.ok ? "var(--success-c)" : "var(--error-c)", border: `1px solid ${toast.ok ? "var(--success)" : "var(--error)"}`, borderRadius: "var(--radius)", boxShadow: "var(--shadow-md)", fontSize: 13, color: toast.ok ? "var(--success)" : "var(--error)", animation: "slideIn 0.2s ease" }}>
          <i className={`ti ${toast.ok ? "ti-circle-check" : "ti-alert-circle"}`} style={{ fontSize: 16 }} />
          {toast.msg}
        </div>
      )}

      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-title">Email Templates</div>
          <div className="page-sub">Customize transactional email messages sent by Royal HRMS</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")} suppressHydrationWarning>
            <i className="ti ti-arrow-left" /> Back
          </button>
          <button className="btn btn-filled btn-sm" onClick={() => setEditing("add")} suppressHydrationWarning>
            <i className="ti ti-plus" /> Add Template
          </button>
        </div>
      </div>

      {/* ── Email Branding Card ── */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", marginBottom: 24, overflow: "hidden" }}>
        {/* Card header */}
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", borderBottom: "1px solid var(--outline-v)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <i className="ti ti-palette" style={{ fontSize: 16, color: "var(--primary)" }} />
            <span style={{ fontSize: 13, fontWeight: 600 }}>Email Header &amp; Footer</span>
            <span style={{ fontSize: 11, color: "var(--on-variant)", marginLeft: 4 }}>Applied to every outgoing email</span>
          </div>
          {!brandingOpen && (
            <button className="btn btn-ghost btn-sm" onClick={() => setBrandingOpen(true)} suppressHydrationWarning>
              <i className="ti ti-pencil" style={{ fontSize: 13 }} /> Edit
            </button>
          )}
        </div>

        {/* Preview row — always visible */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0 }}>
          {/* Header preview */}
          <div style={{ padding: "20px 24px", borderRight: "1px solid var(--outline-v)" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>Header</div>
            <div style={{ background: "#fff", borderRadius: 6, padding: "16px 20px", textAlign: "center", borderBottom: "3px solid #4f46e5", boxShadow: "0 1px 4px rgba(0,0,0,0.06)" }}>
              {currentLogo ? (
                <img src={currentLogo} alt={company?.company_name ?? "Logo"} style={{ maxHeight: 60, maxWidth: 200, objectFit: "contain" }} />
              ) : (
                <span style={{ fontSize: 16, fontWeight: 700, color: "#1a1a2e" }}>{company?.company_name ?? "[Company Name]"}</span>
              )}
            </div>
          </div>

          {/* Footer preview */}
          <div style={{ padding: "20px 24px" }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 10 }}>Footer</div>
            <div style={{ background: "#f8f8fb", borderRadius: 6, padding: "14px 20px", textAlign: "center", border: "1px solid #eee", boxShadow: "0 1px 4px rgba(0,0,0,0.04)" }}>
              <span style={{ fontSize: 12, color: "#888", lineHeight: 1.6 }}>{footerText}</span>
            </div>
          </div>
        </div>

        {/* Inline edit form */}
        {brandingOpen && (
          <div style={{ padding: "20px 24px", borderTop: "1px solid var(--outline-v)", background: "var(--bg)" }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 16, color: "var(--on-bg)" }}>Edit Email Branding</div>

            {/* Logo upload */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: "var(--on-variant)", display: "block", marginBottom: 6 }}>Logo</label>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                {currentLogo && (
                  <img src={currentLogo} alt="Logo" style={{ height: 44, maxWidth: 140, objectFit: "contain", borderRadius: 4, border: "1px solid var(--outline-v)", background: "#fff", padding: 4 }} />
                )}
                <input ref={logoInputRef} type="file" accept="image/*" style={{ display: "none" }} onChange={handleLogoChange} />
                <button className="btn btn-ghost btn-sm" onClick={() => logoInputRef.current?.click()} suppressHydrationWarning>
                  <i className="ti ti-upload" style={{ fontSize: 13 }} /> {currentLogo ? "Change Logo" : "Upload Logo"}
                </button>
                {logoFile && <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{logoFile.name}</span>}
              </div>
            </div>

            {/* Text fields grid */}
            <div className="et-branding-grid">
              {([
                ["company_name",   "Company Name",   "text"],
                ["website",        "Website URL",    "url"],
                ["official_phone", "Phone",          "tel"],
                ["address",        "Address",        "text"],
                ["city",           "City",           "text"],
                ["state",          "State",          "text"],
              ] as [keyof BrandingForm, string, string][]).map(([field, label, type]) => (
                <div key={field}>
                  <label style={{ fontSize: 12, fontWeight: 500, color: "var(--on-variant)", display: "block", marginBottom: 5 }}>{label}</label>
                  <input
                    type={type}
                    className="field-input"
                    value={brandingForm[field]}
                    onChange={e => setBrandingForm(prev => ({ ...prev, [field]: e.target.value }))}
                    suppressHydrationWarning
                  />
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 18, justifyContent: "flex-end" }}>
              <button className="btn btn-ghost btn-sm" onClick={cancelBranding} disabled={brandingSaving} suppressHydrationWarning>Cancel</button>
              <button className="btn btn-filled btn-sm" onClick={saveBranding} disabled={brandingSaving} suppressHydrationWarning>
                {brandingSaving ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</> : "Save Branding"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Birthday Wishes Card ── */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", marginBottom: 24, overflow: "hidden" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "14px 18px", borderBottom: "1px solid var(--outline-v)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <i className="ti ti-cake" style={{ fontSize: 16, color: "var(--primary)" }} />
            <span style={{ fontSize: 13, fontWeight: 600 }}>Automatic Birthday Wishes</span>
            <span style={{ fontSize: 11, fontWeight: 600, marginLeft: 4, color: birthday.is_enabled ? "var(--success)" : "var(--on-variant)" }}>
              {birthday.is_enabled ? "Enabled" : "Disabled"}
            </span>
          </div>
          {!birthdayOpen && (
            <button className="btn btn-ghost btn-sm" onClick={() => setBirthdayOpen(true)} suppressHydrationWarning>
              <i className="ti ti-pencil" style={{ fontSize: 13 }} /> Edit
            </button>
          )}
        </div>

        {!birthdayOpen && (
          <div style={{ padding: "16px 18px", fontSize: 12, color: "var(--on-variant)", display: "flex", flexDirection: "column", gap: 6 }}>
            <span>
              Dashboard banner and notification copy shown to the employee, their team, and their manager on someone&apos;s birthday.
              The birthday <em>email</em> subject/body is edited below, in the Wish template.
            </span>
            <a href="/dashboard/settings/audit?module=birthday" style={{ color: "var(--primary)", fontWeight: 500 }}>
              <i className="ti ti-history" /> View birthday email delivery logs — Audit Log →
            </a>
          </div>
        )}

        {birthdayOpen && (
          <div style={{ padding: "20px 24px", borderTop: "1px solid var(--outline-v)", background: "var(--bg)", display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label className="module-check">
                <input
                  type="checkbox"
                  checked={birthday.is_enabled}
                  onChange={e => setBirthday(f => ({ ...f, is_enabled: e.target.checked }))}
                />
                <span>Enable automatic birthday wishes</span>
              </label>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                When off, no birthday email, dashboard banner, or notification is sent to anyone.
              </div>
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: "var(--on-variant)", display: "block", marginBottom: 5 }}>Dashboard birthday banner message</label>
              <textarea
                className="field-input"
                rows={2}
                value={birthday.banner_message_template}
                onChange={e => setBirthday(f => ({ ...f, banner_message_template: e.target.value }))}
              />
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                Shown under &quot;Happy Birthday, [Name]!&quot; on every employee&apos;s dashboard, company-wide, whenever it&apos;s someone&apos;s birthday.
              </div>
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: "var(--on-variant)", display: "block", marginBottom: 5 }}>Employee in-app notification text</label>
              <textarea
                className="field-input"
                rows={2}
                value={birthday.employee_notification_template}
                onChange={e => setBirthday(f => ({ ...f, employee_notification_template: e.target.value }))}
              />
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: "var(--on-variant)", display: "block", marginBottom: 5 }}>Teammate notification / card text</label>
              <textarea
                className="field-input"
                rows={2}
                value={birthday.team_notification_template}
                onChange={e => setBirthday(f => ({ ...f, team_notification_template: e.target.value }))}
              />
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                Use <code>{"{employee_name}"}</code> as a placeholder — shown to teammates sharing the same reporting manager.
              </div>
            </div>

            <div>
              <label style={{ fontSize: 12, fontWeight: 500, color: "var(--on-variant)", display: "block", marginBottom: 5 }}>Manager notification / card text</label>
              <textarea
                className="field-input"
                rows={2}
                value={birthday.manager_notification_template}
                onChange={e => setBirthday(f => ({ ...f, manager_notification_template: e.target.value }))}
              />
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                Use <code>{"{employee_name}"}</code> as a placeholder — shown to the employee&apos;s reporting manager.
              </div>
            </div>

            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-ghost btn-sm" onClick={cancelBirthday} disabled={birthdaySaving} suppressHydrationWarning>Cancel</button>
              <button className="btn btn-filled btn-sm" onClick={saveBirthdaySettings} disabled={birthdaySaving} suppressHydrationWarning>
                {birthdaySaving ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</> : "Save Birthday Settings"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Search */}
      <div style={{ marginBottom: 20 }}>
        <div className="et-search-wrap" style={{ position: "relative" }}>
          <i className="ti ti-search" style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", fontSize: 15, color: "var(--outline)", pointerEvents: "none" }} />
          <input className="field-input" placeholder="Search templates…" value={search}
            onChange={e => setSearch(e.target.value)} style={{ paddingLeft: 36 }} suppressHydrationWarning />
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 260, gap: 10, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "spin 1s linear infinite" }} /> Loading templates…
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="alert alert-error mb-24">
          <i className="ti ti-alert-circle" />
          <div>
            <strong>Failed to load</strong> — {error}
            <div style={{ marginTop: 8 }}><button className="btn btn-ghost btn-sm" onClick={loadData} suppressHydrationWarning>Retry</button></div>
          </div>
        </div>
      )}

      {/* No search match */}
      {!loading && !error && templates.length > 0 && filtered.length === 0 && (
        <div style={{ textAlign: "center", padding: "32px", color: "var(--on-variant)" }}>
          <i className="ti ti-search-off" style={{ fontSize: 32, opacity: 0.3, display: "block", marginBottom: 10 }} />
          No templates match &quot;{search}&quot;
        </div>
      )}

      {/* Grouped sections */}
      {!loading && !error && filtered.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>
          {orderedTypes.map(type => {
            const group = typeGroups[type];
            if (!group?.length) return null;
            const cat  = catByCode[type];
            const meta = (TYPE_META as Record<string, { label: string; color: string; icon: string }>)[type] ?? { ...FALLBACK_META, label: cat?.name ?? type };
            return (
              <div key={type}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", marginBottom: 12, background: meta.color, borderRadius: "var(--radius)" }}>
                  <i className={`ti ${meta.icon}`} style={{ fontSize: 16, color: "#fff" }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>{meta.label} Templates</span>
                  <span style={{ marginLeft: "auto", fontSize: 12, color: "rgba(255,255,255,0.75)" }}>
                    {group.length} template{group.length !== 1 ? "s" : ""}
                  </span>
                </div>

                <div className="et-cards-grid" style={{ display: "grid", gap: 10 }}>
                  {group.map(template => (
                    <div key={template.id} className="et-card" style={{
                      background: "#fff", border: "1px solid var(--outline-v)",
                      borderRadius: "var(--radius)", padding: "14px 16px",
                      display: "flex", alignItems: "flex-start", gap: 12,
                      opacity: template.is_active ? 1 : 0.6,
                    }}>
                      <div style={{ width: 36, height: 36, borderRadius: 8, background: `${meta.color}15`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1 }}>
                        <i className={`ti ${meta.icon}`} style={{ fontSize: 15, color: meta.color }} />
                      </div>
                      <div className="et-card-body" style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", marginBottom: 2, cursor: "pointer" }}
                          onClick={() => setEditing(template)}>
                          {template.display_name}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)", lineHeight: 1.5, marginBottom: 6 }}>
                          {template.description}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--outline)", fontFamily: "ui-monospace, monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {template.subject}
                        </div>
                      </div>
                      <div className="et-card-actions" style={{ display: "flex", gap: 3, flexShrink: 0, marginTop: 2, alignItems: "center" }}>
                        <button className="btn btn-ghost btn-sm" title="Preview" onClick={() => openPreview(template)} style={{ padding: "4px 7px" }} suppressHydrationWarning>
                          <i className="ti ti-eye" style={{ fontSize: 14 }} />
                        </button>
                        <button className="btn btn-ghost btn-sm" title="Edit" onClick={() => setEditing(template)} style={{ padding: "4px 7px" }} suppressHydrationWarning>
                          <i className="ti ti-pencil" style={{ fontSize: 14 }} />
                        </button>
                        <button
                          title={template.is_active ? "Deactivate" : "Activate"}
                          onClick={() => handleToggleActive(template)}
                          suppressHydrationWarning
                          style={{
                            width: 34, height: 20, borderRadius: 10, border: "none", cursor: "pointer",
                            background: template.is_active ? "var(--primary)" : "var(--outline-v)",
                            position: "relative", flexShrink: 0, transition: "background 0.2s",
                            marginLeft: 2,
                          }}
                        >
                          <span style={{
                            position: "absolute", top: 3, left: template.is_active ? 17 : 3,
                            width: 14, height: 14, borderRadius: "50%", background: "#fff",
                            transition: "left 0.2s", boxShadow: "0 1px 3px rgba(0,0,0,0.2)",
                          }} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Edit / Add modal */}
      {editing !== null && (
        <EditTemplateModal
          template={isAddMode ? null : editTemplate}
          saving={saving}
          onClose={() => setEditing(null)}
          onSave={isAddMode ? handleCreate : handleUpdate}
        />
      )}

      {/* Preview modal */}
      {viewing && (
        <Modal
          title={<>Preview — {viewing.display_name}<div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2, fontWeight: 400 }}>Subject: <strong>{viewing.subject}</strong></div></>}
          onClose={() => setViewing(null)}
          size="lg"
          maxWidth={680}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setViewing(null)} suppressHydrationWarning>Close</button>
              <button className="btn btn-filled" onClick={() => { setViewing(null); setEditing(viewing); }} suppressHydrationWarning>
                <i className="ti ti-pencil" /> Edit Template
              </button>
            </>
          }
        >
          {previewLoading ? (
            <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "24px 0", color: "var(--on-variant)", justifyContent: "center" }}>
              <i className="ti ti-loader-2" style={{ fontSize: 20, animation: "spin 1s linear infinite" }} /> Loading preview…
            </div>
          ) : (
            <iframe
              srcDoc={previewHtml ?? buildEmailPreview(viewing.body, company)}
              sandbox="allow-same-origin"
              style={{ width: "100%", height: 420, border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", display: "block" }}
              title="Email preview"
            />
          )}
        </Modal>
      )}

      <style>{`
        @keyframes spin    { to { transform: rotate(360deg); } }
        @keyframes slideIn { from { opacity: 0; transform: translateX(12px); } to { opacity: 1; transform: translateX(0); } }

        .et-cards-grid { grid-template-columns: minmax(0, 1fr); }
        @media (min-width: 560px)  { .et-cards-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
        @media (min-width: 1100px) { .et-cards-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
        .et-card { min-width: 0; }

        .et-search-wrap { max-width: 100%; }
        @media (min-width: 560px) { .et-search-wrap { max-width: 360px; } }

        .et-branding-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px 16px;
        }
        @media (max-width: 560px) { .et-branding-grid { grid-template-columns: 1fr; } }

        @media (max-width: 500px) {
          .et-card { padding: 10px 12px !important; gap: 8px !important; flex-wrap: wrap; }
          .et-card-body { min-width: 0; width: 100%; }
          .et-card-actions { margin-top: 0 !important; margin-left: auto; }
        }

        @media (max-width: 480px) {
          .et-toast { left: 8px !important; right: 8px !important; top: 8px !important; width: auto !important; }
        }
      `}</style>
    </>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { buildEmailPreview, type CompanyInfo } from "@/lib/emailPreview";
import EditTemplateModal from "./_components/EditTemplateModal";
import {
  EMAIL_TEMPLATES_BASE, EMAIL_TEMPLATE_CATEGORIES, emailTemplateDetail, emailTemplatePreview,
  flattenTemplates, TYPE_META, catValue,
  type ApiEmailTemplate, type ApiEmailTemplatesResponse, type ApiTemplateCategory, type TemplateForm, type TemplateType,
} from "./_data";

const TYPE_ORDER: TemplateType[] = ["document", "notification", "reminder", "wish"];

const FALLBACK_META = { label: "Other", color: "var(--on-variant)", icon: "ti-tag" };

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

  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  const [toast,  setToast]  = useState<{ msg: string; ok: boolean } | null>(null);

  useEffect(() => { loadData(); loadCategories(); loadCompany(); }, []);

  async function loadCompany() {
    try {
      const res = await clientApi.get<{ data: CompanyInfo }>(API.settings.company);
      setCompany(res.data?.data ?? null);
    } catch { /* preview falls back to no-branding */ }
  }

  async function loadCategories() {
    try {
      const res  = await clientApi.get(EMAIL_TEMPLATE_CATEGORIES);
      const data = res.data?.data ?? res.data;
      // Handle both flat array and paginated { results: [] } responses
      const cats = Array.isArray(data) ? data : (Array.isArray(data?.results) ? data.results : []);
      setCategories(cats);
    } catch {
      // silently fall back — templates still render grouped by their own template_type
    }
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

  // ── Create ─────────────────────────────────────────────────────────────────

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

  // ── Update ─────────────────────────────────────────────────────────────────

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

  // ── Toggle active ──────────────────────────────────────────────────────────

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

  // ── Preview ────────────────────────────────────────────────────────────────

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

  // Group templates by their own template_type — this always works regardless of categories
  const typeGroups = filtered.reduce<Record<string, ApiEmailTemplate[]>>((acc, t) => {
    (acc[t.template_type] ??= []).push(t);
    return acc;
  }, {});

  // Map category code → fetched category (for header enrichment)
  const catByCode = Object.fromEntries(categories.map(c => [catValue(c), c]));

  // Order: categories from API first (in their order), then any template_types not covered
  const catCodes    = categories.map(c => catValue(c));
  const extraTypes  = Object.keys(typeGroups).filter(t => !catCodes.includes(t));
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
            const meta = TYPE_META[type as TemplateType] ?? { ...FALLBACK_META, label: cat?.name ?? type };
            return (
              <div key={type}>
                {/* Section header */}
                <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", marginBottom: 12, background: meta.color, borderRadius: "var(--radius)" }}>
                  <i className={`ti ${meta.icon}`} style={{ fontSize: 16, color: "#fff" }} />
                  <span style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>{meta.label} Templates</span>
                  <span style={{ marginLeft: "auto", fontSize: 12, color: "rgba(255,255,255,0.75)" }}>
                    {group.length} template{group.length !== 1 ? "s" : ""}
                  </span>
                </div>

                {/* Cards grid */}
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
                        {/* Active toggle */}
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
        <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) setViewing(null); }}>
          <div className="modal" style={{ width: "min(680px, 96vw)", maxHeight: "88vh", display: "flex", flexDirection: "column" }}>
            <div className="modal-header" style={{ flexShrink: 0 }}>
              <div>
                <div className="modal-title">Preview — {viewing.display_name}</div>
                <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                  Subject: <strong>{viewing.subject}</strong>
                </div>
              </div>
              <button className="modal-close" onClick={() => setViewing(null)} suppressHydrationWarning><i className="ti ti-x" /></button>
            </div>
            <div className="modal-body" style={{ flex: 1, overflow: "auto" }}>
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
            </div>
            <div className="modal-footer" style={{ flexShrink: 0 }}>
              <button className="btn btn-ghost" onClick={() => setViewing(null)} suppressHydrationWarning>Close</button>
              <button className="btn btn-filled" onClick={() => { setViewing(null); setEditing(viewing); }} suppressHydrationWarning>
                <i className="ti ti-pencil" /> Edit Template
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes spin    { to { transform: rotate(360deg); } }
        @keyframes slideIn { from { opacity: 0; transform: translateX(12px); } to { opacity: 1; transform: translateX(0); } }

        /* Cards grid: 1 col → 2 col → 3 col */
        .et-cards-grid { grid-template-columns: 1fr; }
        @media (min-width: 560px)  { .et-cards-grid { grid-template-columns: 1fr 1fr; } }
        @media (min-width: 1100px) { .et-cards-grid { grid-template-columns: 1fr 1fr 1fr; } }

        /* Search: full-width mobile, capped on larger screens */
        .et-search-wrap { max-width: 100%; }
        @media (min-width: 560px) { .et-search-wrap { max-width: 360px; } }

        /* Card: tighter padding + stack body/actions on very small screens */
        @media (max-width: 400px) {
          .et-card { padding: 10px 12px !important; gap: 8px !important; flex-wrap: wrap; }
          .et-card-body { min-width: 0; width: 100%; }
          .et-card-actions { margin-top: 0 !important; margin-left: auto; }
        }

        /* Toast: full-width on mobile */
        @media (max-width: 480px) {
          .et-toast { left: 8px !important; right: 8px !important; top: 8px !important; width: auto !important; }
        }
      `}</style>
    </>
  );
}

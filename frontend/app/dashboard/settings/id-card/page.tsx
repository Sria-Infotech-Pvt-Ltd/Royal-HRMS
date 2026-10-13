"use client";
/* eslint-disable @next/next/no-img-element */
// Plain <img>: remote logo/signature URLs and local blob previews, as on the Company Info page.

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import { IdCardPreview } from "@/components/idcard/IdCardFaces";
import { formatBytes, sampleCardData, termsFromText, type IdCardCompany } from "@/lib/idCard";

interface IdCardSettings {
  signatory_label:          string;
  terms:                    string;
  default_terms:            string;
  show_date_of_birth:       boolean;
  show_residential_address: boolean;
  show_contact_details:     boolean;
  reference_pdf_name:       string;
  reference_pdf_size:       number | null;
  reference_pdf_url:        string | null;
  signature_url:            string | null;
  updated_at:               string | null;
  updated_by_name:          string | null;
}

interface CompanyInfo {
  company_name?: string;
  trade_name?:   string;
  logo_url?:     string | null;
  website?:      string;
  address?:      string;
  city?:         string;
  state?:        string;
  pin_code?:     string;
}

type FormState = Pick<IdCardSettings,
  "signatory_label" | "terms" | "show_date_of_birth" | "show_residential_address" | "show_contact_details">;

const EMPTY_FORM: FormState = {
  signatory_label: "Authorised Signatory", terms: "",
  show_date_of_birth: true, show_residential_address: true, show_contact_details: true,
};

function toForm(s: IdCardSettings): FormState {
  return {
    signatory_label: s.signatory_label, terms: s.terms,
    show_date_of_birth: s.show_date_of_birth, show_residential_address: s.show_residential_address,
    show_contact_details: s.show_contact_details,
  };
}

const TOGGLES: { key: keyof FormState; label: string; hint: string }[] = [
  { key: "show_date_of_birth",       label: "Date of birth",        hint: "Front of the card" },
  { key: "show_residential_address", label: "Residential address",  hint: "Back of the card" },
  { key: "show_contact_details",     label: "Phone and email",      hint: "Back of the card (Contact Details)" },
];

export default function IdCardSettingsPage() {
  const router  = useRouter();
  const canEdit = usePermission("settings.edit");

  const [settings, setSettings] = useState<IdCardSettings | null>(null);
  const [company,  setCompany]  = useState<CompanyInfo>({});
  const [form,     setForm]     = useState<FormState>(EMPTY_FORM);
  const [pdfFile,  setPdfFile]  = useState<File | null>(null);
  const [removePdf, setRemovePdf] = useState(false);
  const [sigFile,  setSigFile]  = useState<File | null>(null);
  const [sigPreview, setSigPreview] = useState<string | null>(null);
  const [removeSig, setRemoveSig] = useState(false);
  const [loading,  setLoading]  = useState(true);
  const [saving,   setSaving]   = useState(false);
  const [saved,    setSaved]    = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      clientApi.get<{ data: IdCardSettings }>(API.settings.idCard),
      clientApi.get<{ data: CompanyInfo }>(API.settings.company).catch(() => ({ data: { data: {} as CompanyInfo } })),
    ])
      .then(([s, c]) => {
        setSettings(s.data.data);
        setForm(toForm(s.data.data));
        setCompany(c.data.data ?? {});
      })
      .catch(() => setApiError("Could not load ID card settings."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => () => { if (sigPreview) URL.revokeObjectURL(sigPreview); }, [sigPreview]);

  const dirty = !!settings && (
    JSON.stringify(form) !== JSON.stringify(toForm(settings)) || !!pdfFile || removePdf || !!sigFile || removeSig
  );

  const companyName = company.trade_name || company.company_name || null;
  const previewData = useMemo(() => {
    const companyCard: IdCardCompany = {
      name: companyName,
      logo_url: company.logo_url ?? null,
      website: (company.website ?? "").replace(/^https?:\/\//i, "").replace(/\/$/, "") || null,
      website_url: company.website || null,
      office_address: "[Branch office address]",
    };
    return sampleCardData(companyCard, {
      terms: termsFromText(form.terms, settings?.default_terms ?? "", companyName),
      signature_url: removeSig ? null : (sigPreview ?? settings?.signature_url ?? null),
      signatory_label: form.signatory_label.trim() || "Authorised Signatory",
      show_date_of_birth: form.show_date_of_birth,
      show_residential_address: form.show_residential_address,
      show_contact_details: form.show_contact_details,
    });
  }, [company, companyName, form, settings, sigPreview, removeSig]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setSaved(false);
    setApiError(null);
    setForm(f => ({ ...f, [key]: value }));
  }

  function pickPdf(file: File | undefined) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".pdf")) { setApiError("The reference file must be a PDF."); return; }
    if (file.size > 10 * 1024 * 1024) { setApiError("The reference PDF must be under 10 MB."); return; }
    setApiError(null); setSaved(false); setPdfFile(file); setRemovePdf(false);
  }

  function pickSignature(file: File | undefined) {
    if (!file) return;
    if (!["image/png", "image/jpeg", "image/webp"].includes(file.type)) { setApiError("The signature must be a PNG, JPEG, or WebP image."); return; }
    if (file.size > 2 * 1024 * 1024) { setApiError("The signature image must be under 2 MB."); return; }
    setApiError(null); setSaved(false); setSigFile(file); setRemoveSig(false);
    setSigPreview(URL.createObjectURL(file));
  }

  function resetChanges() {
    if (settings) setForm(toForm(settings));
    setPdfFile(null); setRemovePdf(false); setSigFile(null); setSigPreview(null); setRemoveSig(false);
    setApiError(null); setSaved(false);
  }

  async function onSave() {
    setSaving(true);
    setApiError(null);
    try {
      const fd = new FormData();
      fd.append("signatory_label", form.signatory_label.trim());
      fd.append("terms", form.terms);
      fd.append("show_date_of_birth", String(form.show_date_of_birth));
      fd.append("show_residential_address", String(form.show_residential_address));
      fd.append("show_contact_details", String(form.show_contact_details));
      if (pdfFile) fd.append("reference_pdf", pdfFile);
      else if (removePdf) fd.append("remove_reference_pdf", "true");
      if (sigFile) fd.append("signature_image", sigFile);
      else if (removeSig) fd.append("remove_signature", "true");

      const { data } = await clientApi.put<{ data: IdCardSettings }>(API.settings.idCard, fd, {
        headers: { "Content-Type": undefined },
      });
      setSettings(data.data);
      setForm(toForm(data.data));
      setPdfFile(null); setRemovePdf(false); setSigFile(null); setSigPreview(null); setRemoveSig(false);
      setSaved(true);
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { message?: string } } };
      setApiError(apiErr?.response?.data?.message ?? "Failed to save. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, gap: 10, color: "var(--on-variant)" }}>
        <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "spin 1s linear infinite" }} />
        Loading settings…
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  const hasPdf = !!settings?.reference_pdf_name && !removePdf;
  const shownSignature = removeSig ? null : (sigPreview ?? settings?.signature_url ?? null);

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">ID Card</div>
          <div className="page-sub">Employee ID card design, terms and authorised signature</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
          {canEdit && (
            <button className="btn btn-filled" onClick={onSave} disabled={saving || !dirty}>
              {saving
                ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
                : <><i className="ti ti-device-floppy" /> Save Changes</>}
            </button>
          )}
        </div>
      </div>

      {apiError && (
        <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /><div>{apiError}</div></div>
      )}
      {saved && (
        <div className="alert alert-success mb-16"><i className="ti ti-circle-check" /><div>ID card settings saved.</div></div>
      )}
      {!canEdit && (
        <div className="alert alert-info mb-16"><i className="ti ti-lock" /><div>You can view these settings but not change them.</div></div>
      )}

      <div style={{ display: "flex", gap: "1.5rem", alignItems: "flex-start", flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 420px", minWidth: 0 }}>
          {/* Reference design */}
          <div className="card mb-24">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-file-type-pdf" /> Reference design</div>
            </div>
            <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ fontSize: 12.5, color: "var(--on-variant)", lineHeight: 1.5 }}>
                Keep the approved ID card PDF here for reference. Cards are generated from the built-in
                front/back template that reproduces this design. The PDF itself isn&apos;t filled in, because a
                design export already contains one person&apos;s details.
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                {pdfFile ? (
                  <span style={{ fontSize: 13 }}><i className="ti ti-file-upload" /> {pdfFile.name} ({formatBytes(pdfFile.size)}) — saves on Save Changes</span>
                ) : hasPdf ? (
                  <>
                    <span style={{ fontSize: 13, fontWeight: 600 }}><i className="ti ti-file-type-pdf" style={{ color: "var(--error)" }} /> {settings?.reference_pdf_name}</span>
                    <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{formatBytes(settings?.reference_pdf_size)}</span>
                    {settings?.reference_pdf_url && (
                      <a className="btn btn-ghost btn-sm" href={settings.reference_pdf_url} target="_blank" rel="noopener noreferrer">
                        <i className="ti ti-external-link" /> View
                      </a>
                    )}
                  </>
                ) : (
                  <span style={{ fontSize: 13, color: "var(--on-variant)" }}>No reference PDF uploaded.</span>
                )}
              </div>
              {canEdit && (
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <label className="btn btn-ghost btn-sm" style={{ cursor: "pointer" }}>
                    <i className="ti ti-upload" /> {hasPdf || pdfFile ? "Replace PDF" : "Upload PDF"}
                    <input type="file" accept=".pdf,application/pdf" hidden
                      onChange={e => { pickPdf(e.target.files?.[0]); e.target.value = ""; }} />
                  </label>
                  {(hasPdf || pdfFile) && (
                    <button className="btn btn-ghost btn-sm" onClick={() => { setPdfFile(null); setRemovePdf(!!settings?.reference_pdf_name); setSaved(false); }}>
                      <i className="ti ti-trash" /> Remove
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Branding — read-only, from Company Info */}
          <div className="card mb-24">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-building" /> Logo and website</div>
            </div>
            <div style={{ padding: "20px 24px", display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
              <div style={{ width: 96, height: 56, border: "1px solid var(--outline-v)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "#fff" }}>
                {company.logo_url
                  ? <img src={company.logo_url} alt="Company logo" style={{ maxWidth: 86, maxHeight: 48, objectFit: "contain" }} />
                  : <span style={{ fontSize: 11, color: "var(--on-variant)" }}>No logo</span>}
              </div>
              <div style={{ flex: 1, minWidth: 180, fontSize: 12.5, color: "var(--on-variant)", lineHeight: 1.5 }}>
                The card uses the company logo and website from Company Info
                {company.website ? <> ({company.website})</> : <> (no website set)</>}.
              </div>
              <button className="btn btn-ghost btn-sm" onClick={() => router.push("/dashboard/settings/company")}>
                <i className="ti ti-pencil" /> Edit in Company Info
              </button>
            </div>
          </div>

          {/* Card content */}
          <div className="card mb-24">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-id" /> Card content</div>
            </div>
            <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 20 }}>
              <div className="field-group">
                <label className="field-label">Authorised signature</label>
                <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                  <div style={{ width: 120, height: 56, border: "1px dashed var(--outline-v)", borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", background: "#fff" }}>
                    {shownSignature
                      ? <img src={shownSignature} alt="Signature" style={{ maxWidth: 110, maxHeight: 48, objectFit: "contain" }} />
                      : <span style={{ fontSize: 11, color: "var(--on-variant)" }}>None</span>}
                  </div>
                  {canEdit && (
                    <>
                      <label className="btn btn-ghost btn-sm" style={{ cursor: "pointer" }}>
                        <i className="ti ti-upload" /> {shownSignature ? "Replace" : "Upload"}
                        <input type="file" accept="image/png,image/jpeg,image/webp" hidden
                          onChange={e => { pickSignature(e.target.files?.[0]); e.target.value = ""; }} />
                      </label>
                      {shownSignature && (
                        <button className="btn btn-ghost btn-sm" onClick={() => { setSigFile(null); setSigPreview(null); setRemoveSig(!!settings?.signature_url); setSaved(false); }}>
                          <i className="ti ti-trash" /> Remove
                        </button>
                      )}
                    </>
                  )}
                </div>
                <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                  Signature or stamp image (PNG with a transparent background works best). PNG, JPEG or WebP, up to 2 MB. Stored privately.
                </div>
              </div>

              <div className="field-group">
                <label className="field-label">Signature caption</label>
                <input className="field-input" style={{ maxWidth: 280 }} maxLength={60} disabled={!canEdit}
                  value={form.signatory_label} onChange={e => update("signatory_label", e.target.value)} />
              </div>

              <div className="field-group">
                <label className="field-label">Terms &amp; conditions</label>
                <textarea className="field-input" rows={4} disabled={!canEdit} style={{ resize: "vertical" }}
                  placeholder={settings?.default_terms ?? ""}
                  value={form.terms} onChange={e => update("terms", e.target.value)} />
                <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                  One condition per line, up to 6. Use {"{company}"} for the company name. Leave blank to use the default conditions shown.
                </div>
              </div>

              <div className="field-group">
                <label className="field-label">Personal details printed on the card</label>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {TOGGLES.map(t => (
                    <label key={t.key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, cursor: canEdit ? "pointer" : "default" }}>
                      <input type="checkbox" disabled={!canEdit} checked={form[t.key] as boolean}
                        onChange={e => update(t.key, e.target.checked)} />
                      {t.label}
                      <span style={{ fontSize: 11.5, color: "var(--on-variant)" }}>— {t.hint}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Sample preview */}
        <div className="card mb-24" style={{ flex: "0 1 460px", minWidth: 0 }}>
          <div className="card-header">
            <div className="card-title"><i className="ti ti-eye" /> Layout preview</div>
          </div>
          <div style={{ padding: "20px 16px", overflowX: "auto" }}>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 14 }}>
              Sample layout with placeholder text. To preview and print a real card, open an employee&apos;s
              profile and choose <strong>ID Card</strong>.
            </div>
            <IdCardPreview data={previewData} />
          </div>
        </div>
      </div>

      {canEdit && (
        <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 10, paddingBottom: 32 }}>
          <button className="btn btn-ghost" disabled={!dirty || saving} onClick={resetChanges}>Cancel</button>
          <button className="btn btn-filled" onClick={onSave} disabled={saving || !dirty}>
            {saving
              ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
              : <><i className="ti ti-device-floppy" /> Save Changes</>}
          </button>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}

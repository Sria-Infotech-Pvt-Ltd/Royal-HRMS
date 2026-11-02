"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

type IdFormat = "date_initials" | "first_date_last";

interface EmployeeCodeSettings {
  prefix:        string;
  id_format:     IdFormat;
  padding:       number;
  next_sequence: number;
}

interface FieldErrors {
  prefix?:        string;
  padding?:       string;
  next_sequence?: string;
}

// Employee ID = prefix + date of joining (DDMM) + name initials (first
// letter of first name + first letter of last name), in one of two orders
// (backend EmployeeCodeSettings.build_base_id):
//   date_initials   — RSS + 0308 + TG        -> RSS0308TG
//   first_date_last — RIS + T + 0308 + G     -> RIST0308G
// Shown with fixed example people/dates, not derived from padding/
// next_sequence (those no longer affect the generated id).
const FORMAT_OPTIONS: { value: IdFormat; label: string; description: string }[] = [
  { value: "date_initials",   label: "Prefix + DDMM + initials",                     description: "prefix + date of joining (DDMM) + first and last name initials" },
  { value: "first_date_last", label: "Prefix + first initial + DDMM + last initial", description: "prefix + first name initial + date of joining (DDMM) + last name initial" },
];

const PREVIEW_EXAMPLES: { name: string; doj: string; ddmm: string; initials: string }[] = [
  { name: "Teerdaveni Gedela", doj: "03 Aug", ddmm: "0308", initials: "TG" },
  { name: "Ravi Kumar",        doj: "15 Sep", ddmm: "1509", initials: "RK" },
  { name: "Rahul Kumar",       doj: "15 Sep", ddmm: "1509", initials: "RK" },
];

function buildPreview(prefix: string, format: IdFormat): { label: string; code: string; note?: string }[] {
  const p = prefix || "EMP";
  return PREVIEW_EXAMPLES.map((ex, i) => {
    const base = format === "first_date_last"
      ? `${p}${ex.initials[0]}${ex.ddmm}${ex.initials[1]}`
      : `${p}${ex.ddmm}${ex.initials}`;
    return {
      label: `${ex.name} (joined ${ex.doj})`,
      code: i === 2 ? `${base}2` : base,
      note: i === 2 ? "Same day + same initials as above — a 2 is appended to keep it unique" : undefined,
    };
  });
}

function toSettings(d: Partial<EmployeeCodeSettings>): EmployeeCodeSettings {
  return {
    prefix: d.prefix ?? "", id_format: d.id_format ?? "date_initials",
    padding: d.padding ?? 5, next_sequence: d.next_sequence ?? 1,
  };
}

export default function EmployeeCodeSettingsPage() {
  const router = useRouter();

  const [form,    setForm]    = useState<EmployeeCodeSettings>(toSettings({}));
  const [base,    setBase]    = useState<EmployeeCodeSettings>(toSettings({}));
  const [errors,  setErrors]  = useState<FieldErrors>({});
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);
  const [saved,   setSaved]   = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    clientApi
      .get<{ data: EmployeeCodeSettings }>(API.settings.employeeCode)
      .then(({ data }) => {
        const safe = toSettings(data.data ?? {});
        setForm(safe);
        setBase(safe);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const dirty = JSON.stringify(form) !== JSON.stringify(base);

  function validate(): boolean {
    const errs: FieldErrors = {};
    if (!form.prefix.trim()) {
      errs.prefix = "Prefix is required.";
    } else if (!/^[A-Za-z]+$/.test(form.prefix.trim())) {
      errs.prefix = "Prefix must contain letters only.";
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  // padding/next_sequence are no longer editable here, but are still part
  // of the save payload below (API contract unchanged) — carried through
  // from whatever GET returned, untouched by the user.
  function onPrefixChange(value: string) {
    setSaved(false);
    setApiError(null);
    setErrors(e => ({ ...e, prefix: undefined }));
    setForm(f => ({ ...f, prefix: value }));
  }

  function onFormatChange(value: IdFormat) {
    setSaved(false);
    setApiError(null);
    setForm(f => ({ ...f, id_format: value }));
  }

  async function onSave() {
    if (!validate()) return;
    setSaving(true);
    setApiError(null);
    try {
      const { data } = await clientApi.put<{ data: EmployeeCodeSettings }>(
        API.settings.employeeCode,
        {
          prefix: form.prefix.trim().toUpperCase(), id_format: form.id_format,
          padding: form.padding, next_sequence: form.next_sequence,
        }
      );
      const safe = toSettings(data.data ?? {});
      setForm(safe);
      setBase(safe);
      setSaved(true);
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { data?: FieldErrors; message?: string } } };
      if (apiErr?.response?.data?.data) {
        setErrors(apiErr.response.data.data as FieldErrors);
      } else {
        setApiError(apiErr?.response?.data?.message ?? "Failed to save. Please try again.");
      }
    } finally {
      setSaving(false);
    }
  }

  const preview = buildPreview(form.prefix.trim().toUpperCase() || "EMP", form.id_format);
  const formatOption = FORMAT_OPTIONS.find(o => o.value === form.id_format) ?? FORMAT_OPTIONS[0];

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, gap: 10, color: "var(--on-variant)" }}>
        <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "spin 1s linear infinite" }} />
        Loading settings…
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  return (
    <>
      {/* Page header */}
      <div className="page-header">
        <div>
          <div className="page-title">Employee ID Format</div>
          <div className="page-sub">Configure the prefix used for new employee codes</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
          <button className="btn btn-filled" onClick={onSave} disabled={saving || !dirty}>
            {saving
              ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
              : <><i className="ti ti-device-floppy" /> Save Changes</>
            }
          </button>
        </div>
      </div>

      {/* Feedback banners */}
      {apiError && (
        <div className="alert alert-error mb-16">
          <i className="ti ti-alert-circle" />
          <div>{apiError}</div>
        </div>
      )}
      {saved && (
        <div className="alert alert-success mb-16">
          <i className="ti ti-circle-check" />
          <div>Employee ID format saved successfully.</div>
        </div>
      )}

      <div style={{ display: "flex", gap: "1.5rem", alignItems: "flex-start" }}>
        {/* Config card */}
        <div className="card mb-24" style={{ flex: 1 }}>
          <div className="card-header">
            <div className="card-title"><i className="ti ti-id-badge" /> Configuration</div>
          </div>
          <div style={{ padding: "20px 24px", display: "flex", flexDirection: "column", gap: 20 }}>

            {/* Prefix */}
            <div className="field-group">
              <label className="field-label">
                Prefix <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <input
                className={`field-input${errors.prefix ? " field-error" : ""}`}
                value={form.prefix}
                onChange={e => onPrefixChange(e.target.value)}
                maxLength={10}
                placeholder="e.g. RSS"
                style={{ maxWidth: 200 }}
              />
              {errors.prefix && <div className="field-error-msg">{errors.prefix}</div>}
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                Letters only, max 10 characters. Saved as uppercase.
              </div>
            </div>

            {/* Format */}
            <div className="field-group">
              <label className="field-label">Format</label>
              <select
                className="field-input"
                value={form.id_format}
                onChange={e => onFormatChange(e.target.value as IdFormat)}
                style={{ maxWidth: 380 }}
              >
                {FORMAT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                Applies to employees created from now on. Existing employee IDs are not changed.
              </div>
            </div>

          </div>
        </div>

        {/* Preview card */}
        <div className="card mb-24" style={{ width: 240, flexShrink: 0 }}>
          <div className="card-header">
            <div className="card-title"><i className="ti ti-eye" /> Preview</div>
          </div>
          <div style={{ padding: "20px 24px" }}>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 14 }}>
              Format: {formatOption.description}. Example IDs:
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {preview.map((ex, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 2,
                    padding: "8px 12px",
                    borderRadius: "var(--radius)",
                    background: "var(--bg-low)",
                    border: "1px solid var(--outline-v)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{
                      fontFamily: "monospace",
                      fontSize: 14,
                      fontWeight: 700,
                      color: "var(--on-bg)",
                      flex: 1,
                    }}>
                      {ex.code}
                    </span>
                  </div>
                  <span style={{ fontSize: 11, color: "var(--on-variant)" }}>{ex.label}</span>
                  {ex.note && (
                    <span style={{ fontSize: 11, color: "var(--primary)" }}>{ex.note}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom action bar */}
      <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 10, paddingBottom: 32 }}>
        <button
          className="btn btn-ghost"
          disabled={!dirty || saving}
          onClick={() => { setForm(base); setErrors({}); setSaved(false); setApiError(null); }}
        >
          Cancel
        </button>
        <button className="btn btn-filled" onClick={onSave} disabled={saving || !dirty}>
          {saving
            ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} /> Saving…</>
            : <><i className="ti ti-device-floppy" /> Save Changes</>
          }
        </button>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}

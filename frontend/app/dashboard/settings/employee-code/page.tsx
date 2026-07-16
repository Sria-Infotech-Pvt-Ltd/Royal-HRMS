"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

interface EmployeeCodeSettings {
  prefix:        string;
  padding:       number;
  next_sequence: number;
}

interface FieldErrors {
  prefix?:        string;
  padding?:       string;
  next_sequence?: string;
}

const PREVIEW_COUNT = 3;

function buildPreview(prefix: string, padding: number, start: number): string[] {
  return Array.from({ length: PREVIEW_COUNT }, (_, i) =>
    `${prefix}${String(start + i).padStart(padding, "0")}`
  );
}

export default function EmployeeCodeSettingsPage() {
  const router = useRouter();

  const [form,    setForm]    = useState<EmployeeCodeSettings>({ prefix: "", padding: 5, next_sequence: 1 });
  const [base,    setBase]    = useState<EmployeeCodeSettings>({ prefix: "", padding: 5, next_sequence: 1 });
  const [errors,  setErrors]  = useState<FieldErrors>({});
  const [loading, setLoading] = useState(true);
  const [saving,  setSaving]  = useState(false);
  const [saved,   setSaved]   = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  useEffect(() => {
    clientApi
      .get<{ data: EmployeeCodeSettings }>(API.settings.employeeCode)
      .then(({ data }) => {
        setForm(data.data);
        setBase(data.data);
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
    if (form.padding < 3 || form.padding > 8) {
      errs.padding = "Padding must be between 3 and 8.";
    }
    if (form.next_sequence < 1) {
      errs.next_sequence = "Starting number must be at least 1.";
    }
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  function onField(key: keyof EmployeeCodeSettings, value: string) {
    setSaved(false);
    setApiError(null);
    setErrors(e => ({ ...e, [key]: undefined }));
    setForm(f => ({
      ...f,
      [key]: key === "prefix" ? value : Number(value),
    }));
  }

  async function onSave() {
    if (!validate()) return;
    setSaving(true);
    setApiError(null);
    try {
      const { data } = await clientApi.put<{ data: EmployeeCodeSettings }>(
        API.settings.employeeCode,
        { prefix: form.prefix.trim().toUpperCase(), padding: form.padding, next_sequence: form.next_sequence }
      );
      setForm(data.data);
      setBase(data.data);
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

  const preview = buildPreview(
    form.prefix.trim().toUpperCase() || "EMP",
    form.padding,
    form.next_sequence
  );

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
          <div className="page-sub">Configure the prefix, digit count, and starting number for employee codes</div>
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
                onChange={e => onField("prefix", e.target.value)}
                maxLength={10}
                placeholder="e.g. RSS"
                style={{ maxWidth: 200 }}
              />
              {errors.prefix && <div className="field-error-msg">{errors.prefix}</div>}
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                Letters only, max 10 characters. Saved as uppercase.
              </div>
            </div>

            {/* Digit padding */}
            <div className="field-group">
              <label className="field-label">
                Digit padding <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <input
                type="number"
                className={`field-input${errors.padding ? " field-error" : ""}`}
                value={form.padding}
                min={3}
                max={8}
                onChange={e => onField("padding", e.target.value)}
                style={{ maxWidth: 200 }}
              />
              {errors.padding && <div className="field-error-msg">{errors.padding}</div>}
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                Number of digits (3–8). E.g. 5 produces RSS00001.
              </div>
            </div>

            {/* Next sequence */}
            <div className="field-group">
              <label className="field-label">
                Next sequence number <span style={{ color: "var(--error)" }}>*</span>
              </label>
              <input
                type="number"
                className={`field-input${errors.next_sequence ? " field-error" : ""}`}
                value={form.next_sequence}
                min={1}
                onChange={e => onField("next_sequence", e.target.value)}
                style={{ maxWidth: 200 }}
              />
              {errors.next_sequence && <div className="field-error-msg">{errors.next_sequence}</div>}
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 4 }}>
                The number assigned to the next new employee created.
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
              Next {PREVIEW_COUNT} employee IDs that will be generated:
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {preview.map((code, idx) => (
                <div
                  key={idx}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 12px",
                    borderRadius: "var(--radius)",
                    background: idx === 0 ? "var(--primary-c, rgba(30,78,140,0.08))" : "var(--bg-low)",
                    border: idx === 0 ? "1px solid rgba(30,78,140,0.2)" : "1px solid var(--outline-v)",
                  }}
                >
                  <span style={{
                    fontFamily: "monospace",
                    fontSize: 14,
                    fontWeight: 700,
                    color: idx === 0 ? "var(--primary)" : "var(--on-bg)",
                    flex: 1,
                  }}>
                    {code}
                  </span>
                  {idx === 0 && (
                    <span style={{
                      fontSize: 10,
                      fontWeight: 600,
                      color: "var(--primary)",
                      background: "rgba(30,78,140,0.1)",
                      padding: "2px 6px",
                      borderRadius: 4,
                      letterSpacing: "0.03em",
                    }}>
                      NEXT
                    </span>
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

"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

interface SeriesRow {
  employment_type:         string;
  employment_type_display: string;
  prefix:                  string;
  padding:                 number;
  next_sequence:           number;
  format_description:      string;
}

interface RowErrors {
  prefix?:        string;
  padding?:       string;
  next_sequence?: string;
}

/** One row's own editable draft + save state — rows save independently so
 * fixing a typo in Freelancer's prefix never risks also resubmitting
 * Permanent's unrelated, unsaved in-progress edit. */
function SeriesRowEditor({ row, onSaved }: { row: SeriesRow; onSaved: (row: SeriesRow) => void }) {
  const [form, setForm] = useState(row);
  const [errors, setErrors] = useState<RowErrors>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const dirty = form.prefix !== row.prefix || form.padding !== row.padding || form.next_sequence !== row.next_sequence;

  function onField(key: "prefix" | "padding" | "next_sequence", value: string) {
    setSaved(false);
    setApiError(null);
    setErrors(e => ({ ...e, [key]: undefined }));
    setForm(f => ({ ...f, [key]: key === "prefix" ? value : Number(value) }));
  }

  function validate(): boolean {
    const errs: RowErrors = {};
    if (!form.prefix.trim()) errs.prefix = "Required.";
    else if (!/^[A-Za-z0-9_-]+$/.test(form.prefix.trim())) errs.prefix = "Letters, numbers, -, _ only.";
    if (form.padding < 3 || form.padding > 8) errs.padding = "3–8.";
    if (form.next_sequence < 1) errs.next_sequence = "Min 1.";
    setErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function onSave() {
    if (!validate()) return;
    setSaving(true);
    setApiError(null);
    try {
      const { data } = await clientApi.put<{ data: SeriesRow }>(
        API.settings.employeeCodeSeriesDetail(row.employment_type),
        { prefix: form.prefix.trim().toUpperCase(), padding: form.padding, next_sequence: form.next_sequence },
      );
      setForm(data.data);
      onSaved(data.data);
      setSaved(true);
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { data?: RowErrors; message?: string } } };
      if (apiErr?.response?.data?.data) setErrors(apiErr.response.data.data);
      else setApiError(apiErr?.response?.data?.message ?? "Failed to save.");
    } finally {
      setSaving(false);
    }
  }

  const preview = `${(form.prefix || "").toUpperCase()}${String(form.next_sequence).padStart(form.padding, "0")}`;

  return (
    <tr>
      <td style={{ padding: "10px 12px", fontWeight: 600 }}>{row.employment_type_display}</td>
      <td style={{ padding: "10px 12px" }}>
        <input
          className={`field-input${errors.prefix ? " field-error" : ""}`}
          value={form.prefix}
          onChange={e => onField("prefix", e.target.value)}
          maxLength={10}
          style={{ width: 90 }}
        />
        {errors.prefix && <div className="field-error-msg">{errors.prefix}</div>}
      </td>
      <td style={{ padding: "10px 12px" }}>
        <input
          type="number"
          className={`field-input${errors.padding ? " field-error" : ""}`}
          value={form.padding}
          min={3}
          max={8}
          onChange={e => onField("padding", e.target.value)}
          style={{ width: 70 }}
        />
        {errors.padding && <div className="field-error-msg">{errors.padding}</div>}
      </td>
      <td style={{ padding: "10px 12px" }}>
        <input
          type="number"
          className={`field-input${errors.next_sequence ? " field-error" : ""}`}
          value={form.next_sequence}
          min={1}
          onChange={e => onField("next_sequence", e.target.value)}
          style={{ width: 90 }}
        />
        {errors.next_sequence && <div className="field-error-msg">{errors.next_sequence}</div>}
      </td>
      <td style={{ padding: "10px 12px", fontFamily: "monospace", fontWeight: 600, color: "var(--primary)" }}>{preview}</td>
      <td style={{ padding: "10px 12px" }}>
        <button className="btn btn-ghost btn-sm" disabled={!dirty || saving} onClick={onSave}>
          {saving ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
        {apiError && <div className="field-error-msg">{apiError}</div>}
      </td>
    </tr>
  );
}

/** Per-employment-type ID series (EMP/CON/FRL/...) — each type gets its own
 * independent, concurrency-safe counter server-side (see
 * EmployeeCodeSeries.generate_employee_id_for_type); this just lets an
 * admin see and edit each type's prefix/digit-count/starting number. */
export default function EmployeeCodeSeriesCard() {
  const [rows, setRows] = useState<SeriesRow[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    clientApi.get<{ data: SeriesRow[] }>(API.settings.employeeCodeSeries)
      .then(({ data }) => setRows(data.data ?? []))
      .catch(() => setLoadError("Failed to load per-type ID series."));
  }, []);

  function onRowSaved(updated: SeriesRow) {
    setRows(prev => prev?.map(r => r.employment_type === updated.employment_type ? updated : r) ?? prev);
  }

  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-list-numbers" /> ID Series by Worker Type</div>
      </div>
      <div style={{ padding: "12px 24px 20px" }}>
        <p style={{ fontSize: 12.5, color: "var(--on-variant)", marginBottom: 14 }}>
          Each worker type (Permanent, Contract, Freelancer, …) gets its own independent, non-reused ID series —
          e.g. permanent hires as <code>EMP00001</code>, contractors as <code>CON00001</code>, freelancers as
          <code> FRL00001</code>. The ID is picked automatically from the type selected at hire; changing an
          existing employee&apos;s type later does not change their existing ID.
        </p>
        {loadError && (
          <div className="alert alert-error mb-16">
            <i className="ti ti-alert-circle" /> <div>{loadError}</div>
          </div>
        )}
        {!rows && !loadError ? (
          <div style={{ color: "var(--on-variant)", fontSize: 13 }}>Loading…</div>
        ) : rows && rows.length > 0 ? (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", color: "var(--on-variant)", fontSize: 11, textTransform: "uppercase", letterSpacing: "0.04em" }}>
                  <th style={{ padding: "6px 12px" }}>Worker type</th>
                  <th style={{ padding: "6px 12px" }}>Prefix</th>
                  <th style={{ padding: "6px 12px" }}>Digits</th>
                  <th style={{ padding: "6px 12px" }}>Next number</th>
                  <th style={{ padding: "6px 12px" }}>Next ID</th>
                  <th style={{ padding: "6px 12px" }}></th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <SeriesRowEditor key={row.employment_type} row={row} onSaved={onRowSaved} />
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </div>
  );
}

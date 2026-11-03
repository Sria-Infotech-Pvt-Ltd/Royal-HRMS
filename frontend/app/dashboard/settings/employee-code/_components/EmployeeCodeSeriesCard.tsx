"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";

interface SeriesRow {
  employment_type:         string;
  employment_type_display: string;
  range_start:              number;
  range_end:                number;
  next_sequence:            number;
  format_description:       string;
  usage_percent:            number;
  is_exhausted:             boolean;
}

interface RowErrors {
  range_start?:   string;
  range_end?:     string;
  next_sequence?: string;
}

/** One row's own editable draft + save state — rows save independently so
 * fixing a typo in one type's range never risks also resubmitting another
 * type's unrelated, unsaved in-progress edit. */
type NumericField = "range_start" | "range_end" | "next_sequence";

function SeriesRowEditor({ row, onSaved }: { row: SeriesRow; onSaved: (row: SeriesRow) => void }) {
  const [form, setForm] = useState(row);
  // The raw text the user is typing, kept separate from the parsed `form`
  // numbers — a plain controlled <input value={number}> forces the DOM back
  // to e.g. "0" on every keystroke while the field is being cleared/retyped
  // (Number("") === 0), which made it impossible to clear a field or type a
  // new value that doesn't start with the digit already there.
  const [text, setText] = useState<Record<NumericField, string>>({
    range_start: String(row.range_start),
    range_end: String(row.range_end),
    next_sequence: String(row.next_sequence),
  });
  const [errors, setErrors] = useState<RowErrors>({});
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const dirty = form.range_start !== row.range_start || form.range_end !== row.range_end || form.next_sequence !== row.next_sequence;

  function onField(key: NumericField, value: string) {
    setSaved(false);
    setApiError(null);
    setErrors(e => ({ ...e, [key]: undefined }));
    // Allow free typing (including a momentarily-empty field) in the text
    // box; only a fully-numeric value updates the real numeric form state
    // that validation/save actually use.
    setText(t => ({ ...t, [key]: value }));
    if (/^\d+$/.test(value)) {
      setForm(f => ({ ...f, [key]: Number(value) }));
    }
  }

  function validate(): boolean {
    const errs: RowErrors = {};
    if (!/^\d+$/.test(text.range_start)) errs.range_start = "Required — whole number.";
    if (!/^\d+$/.test(text.range_end)) errs.range_end = "Required — whole number.";
    if (!/^\d+$/.test(text.next_sequence)) errs.next_sequence = "Required — whole number.";
    if (!errs.range_start && !errs.range_end && form.range_end <= form.range_start) errs.range_end = "Must be greater than range start.";
    if (!errs.range_start && !errs.range_end && !errs.next_sequence && (form.next_sequence <= form.range_start || form.next_sequence > form.range_end + 1)) {
      errs.next_sequence = `Must be between ${form.range_start + 1} and ${form.range_end} to issue a new ID (or ${form.range_end + 1}, which marks the range as fully used up).`;
    }
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
        { range_start: form.range_start, range_end: form.range_end, next_sequence: form.next_sequence },
      );
      setForm(data.data);
      setText({
        range_start: String(data.data.range_start),
        range_end: String(data.data.range_end),
        next_sequence: String(data.data.next_sequence),
      });
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

  const preview = form.next_sequence > form.range_end ? "Exhausted" : String(form.next_sequence);

  return (
    <tr>
      <td style={{ padding: "10px 12px", fontWeight: 600 }}>{row.employment_type_display}</td>
      <td style={{ padding: "10px 12px" }}>
        <input
          type="number"
          className={`field-input${errors.range_start ? " field-error" : ""}`}
          value={text.range_start}
          onChange={e => onField("range_start", e.target.value)}
          style={{ width: 110 }}
        />
        {errors.range_start && <div className="field-error-msg">{errors.range_start}</div>}
      </td>
      <td style={{ padding: "10px 12px" }}>
        <input
          type="number"
          className={`field-input${errors.range_end ? " field-error" : ""}`}
          value={text.range_end}
          onChange={e => onField("range_end", e.target.value)}
          style={{ width: 110 }}
        />
        {errors.range_end && <div className="field-error-msg">{errors.range_end}</div>}
      </td>
      <td style={{ padding: "10px 12px" }}>
        <input
          type="number"
          className={`field-input${errors.next_sequence ? " field-error" : ""}`}
          value={text.next_sequence}
          onChange={e => onField("next_sequence", e.target.value)}
          style={{ width: 110 }}
        />
        {errors.next_sequence && <div className="field-error-msg">{errors.next_sequence}</div>}
      </td>
      <td style={{ padding: "10px 12px", fontFamily: "monospace", fontWeight: 600, color: form.next_sequence > form.range_end ? "var(--error)" : "var(--primary)" }}>
        {preview}
      </td>
      <td style={{ padding: "10px 12px" }}>
        <span style={{ fontSize: 12, color: row.usage_percent >= 90 ? "var(--error)" : "var(--on-variant)" }}>
          {row.usage_percent}%{row.usage_percent >= 90 && !row.is_exhausted && <i className="ti ti-alert-triangle" style={{ marginLeft: 4 }} title="Nearing exhaustion" />}
        </span>
      </td>
      <td style={{ padding: "10px 12px" }}>
        <button className="btn btn-ghost btn-sm" disabled={!dirty || saving} onClick={onSave}>
          {saving ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
        {apiError && <div className="field-error-msg">{apiError}</div>}
      </td>
    </tr>
  );
}

/** Per-employment-type numeric ID range (SAP-personnel-number style) — each
 * type owns a disjoint 8-digit range server-side (see
 * EmployeeCodeSeries.generate_employee_id_for_type); this just lets an
 * admin see and edit each type's range and next number. */
export default function EmployeeCodeSeriesCard() {
  const { data: fetchedRows, error: loadError } = useFetch<SeriesRow[]>(API.settings.employeeCodeSeries);
  // A local, independently-patchable copy of the fetched rows — each row
  // saves itself (see onRowSaved) without waiting on a full refetch, so
  // fixing one type's range doesn't flicker/reset every other row's
  // in-progress edit.
  const [rows, setRows] = useState<SeriesRow[] | null>(null);

  useEffect(() => {
    if (fetchedRows) setRows(fetchedRows);
  }, [fetchedRows]);

  function onRowSaved(updated: SeriesRow) {
    setRows(prev => prev?.map(r => r.employment_type === updated.employment_type ? updated : r) ?? prev);
  }

  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-list-numbers" /> ID Range by Worker Type</div>
      </div>
      <div style={{ padding: "12px 24px 20px" }}>
        <p style={{ fontSize: 12.5, color: "var(--on-variant)", marginBottom: 14 }}>
          Every ID is 8 digits, purely numeric — no letters. Each worker type gets its own non-overlapping,
          non-reused numeric range, so the leading digit alone tells you the worker type — e.g.{" "}
          <code>10000123</code> is Permanent, <code>50000045</code> is an Intern. The ID is picked automatically
          from the type selected at hire; changing an existing employee&apos;s type later does not change their
          existing ID, so its leading digit may no longer match their current type — that&apos;s expected.
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
                  <th style={{ padding: "6px 12px" }}>Range from</th>
                  <th style={{ padding: "6px 12px" }}>Range to</th>
                  <th style={{ padding: "6px 12px" }}>Next number</th>
                  <th style={{ padding: "6px 12px" }}>Next ID</th>
                  <th style={{ padding: "6px 12px" }}>Used</th>
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

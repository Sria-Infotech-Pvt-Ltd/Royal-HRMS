"use client";

// Per-employment-type numeric ID ranges (SAP-personnel-number style): each type owns a disjoint 8-digit range server-side (see
// EmployeeCodeSeries.generate_employee_id_for_type). This shows the totals, a map of the whole number space, and a table to edit each range.

import { useState } from "react";
import { useEmployeeSeries } from "@/hooks/useEmployeeSeries";
import RangeMap from "./RangeMap";
import SeriesTable from "./SeriesTable";
import { findOverlaps, sortRows, summarise, tint, type SortDirection, type SortKey } from "./employeeCodeView";

const SHIMMER = { background: "linear-gradient(90deg, #eceff6 25%, #f7f8fc 50%, #eceff6 75%)", backgroundSize: "300% 100%", animation: "ann-shimmer 1.4s linear infinite" } as const;

export default function EmployeeCodeSeriesCard() {
  const { rows, loadError, drafts, dirtyTypes, setField, reset, save, saveAll, resetAll } = useEmployeeSeries();
  const [sort, setSort] = useState<{ key: SortKey; direction: SortDirection }>({ key: "range_start", direction: "asc" });
  const [isSavingAll, setIsSavingAll] = useState(false);

  const shown = rows ? sortRows(rows, sort.key, sort.direction) : [];
  const ranges = (rows ?? []).filter(row => drafts[row.employment_type]).map(row => {
    const form = drafts[row.employment_type].form;
    return { type: row.employment_type, label: row.employment_type_display, start: form.range_start, end: form.range_end, next: form.next_sequence };
  });
  const overlaps = findOverlaps(ranges);
  const totals = rows ? summarise(rows) : null;

  function onSort(key: SortKey) {
    setSort(previous => previous.key === key ? { key, direction: previous.direction === "asc" ? "desc" : "asc" } : { key, direction: "asc" });
  }

  async function onSaveAll() {
    setIsSavingAll(true);
    try { await saveAll(); } finally { setIsSavingAll(false); }
  }

  return (
    <>
      {loadError && <div role="alert" className="alert alert-error mb-16"><i className="ti ti-alert-circle" /> <div>{loadError}</div></div>}

      {totals && (
        <p aria-label="Summary" style={{ margin: "0 0 14px", fontSize: 13, color: "var(--on-variant)" }}>
          <b style={{ color: "var(--on-bg)" }}>{totals.types}</b> worker types · <b style={{ color: "var(--on-bg)" }}>{totals.idsLeft.toLocaleString("en-IN")}</b> IDs left to issue · <b style={{ color: totals.nearing > 0 ? "#EA580C" : "var(--on-bg)" }}>{totals.nearing}</b> need attention
        </p>
      )}

      <RangeMap ranges={ranges.map(range => ({ ...range, isOverlapping: overlaps.has(range.type) }))} />

      {overlaps.size > 0 && (
        <div role="alert" style={{ marginBottom: 14, padding: "10px 14px", borderRadius: 12, fontSize: 13, color: "var(--on-bg)", background: tint("#DC2626", 0.08), border: `1px solid ${tint("#DC2626", 0.28)}` }}>
          <i className="ti ti-alert-triangle" aria-hidden="true" style={{ color: "#DC2626" }} /> Two worker types share some of the same numbers. Change a range so they no longer overlap before saving.
        </div>
      )}

      {rows && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, marginBottom: 10 }}>
          <p style={{ margin: 0, fontSize: 12.5, color: "var(--on-variant)", maxWidth: 760, lineHeight: 1.5 }}>
            Every ID is 8 digits and purely numeric. Each worker type has its own range, so the first digit tells you the type. The ID is picked automatically at hire;
            changing someone&apos;s type later does not change their existing ID.
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {dirtyTypes.length > 0 && <span style={{ fontSize: 12, fontWeight: 700, color: "#EA580C" }}>{dirtyTypes.length} unsaved {dirtyTypes.length === 1 ? "change" : "changes"}</span>}
            <button type="button" className="btn btn-ghost btn-sm" disabled={dirtyTypes.length === 0 || isSavingAll} onClick={resetAll}>Reset all</button>
            <button type="button" className="btn btn-filled btn-sm" disabled={dirtyTypes.length === 0 || isSavingAll} onClick={onSaveAll}>{isSavingAll ? "Saving…" : "Save all"}</button>
          </div>
        </div>
      )}

      {!rows && !loadError && <div aria-label="Loading" style={{ ...SHIMMER, height: 320, borderRadius: 16 }} />}
      {rows && rows.length > 0 && <SeriesTable rows={shown} drafts={drafts} overlaps={overlaps} sort={sort} onSort={onSort} onField={setField} onSave={save} onReset={reset} />}
      {rows && rows.length === 0 && <div style={{ textAlign: "center", padding: "40px 16px", color: "var(--on-variant)" }}>No worker types are set up yet.</div>}
    </>
  );
}

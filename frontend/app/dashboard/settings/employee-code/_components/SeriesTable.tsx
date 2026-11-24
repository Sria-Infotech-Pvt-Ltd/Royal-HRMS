"use client";

// The ID ranges as a table you edit in place: click a heading to sort, change a number and the row is marked as unsaved (Enter saves it),
// the Next ID follows what is typed, and each row shows how full its range is. Rows with overlapping ranges are marked in red.

import { useT } from "@/hooks/useI18n";
import type { SeriesDraft } from "@/hooks/useEmployeeSeries";
import { isDraftDirty } from "@/hooks/useEmployeeSeries";
import { BRAND, HEALTH_STYLE, MONO_FONT, healthOf, idsLeft, leadingDigit, tint, usageColour, type NumericField, type SeriesRow, type SortDirection, type SortKey } from "./employeeCodeView";

interface Props {
  rows: SeriesRow[];
  drafts: Record<string, SeriesDraft>;
  overlaps: Set<string>;
  sort: { key: SortKey; direction: SortDirection };
  onSort: (key: SortKey) => void;
  onField: (type: string, key: NumericField, value: string) => void;
  onSave: (type: string) => void;
  onReset: (type: string) => void;
}

const INPUTS: { key: NumericField; label: string }[] = [
  { key: "range_start", label: "Range from" },
  { key: "range_end", label: "Range to" },
  { key: "next_sequence", label: "Next number" },
];

function SortHeader({ label, sortKey, sort, onSort }: { label: string; sortKey: SortKey; sort: Props["sort"]; onSort: (key: SortKey) => void }) {
  const t = useT();
  const active = sort.key === sortKey;
  return (
    <th aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}>
      <button type="button" onClick={() => onSort(sortKey)} style={{ display: "inline-flex", alignItems: "center", gap: 4, background: "none", border: 0, padding: 0, font: "inherit", textTransform: "inherit", letterSpacing: "inherit", cursor: "pointer", color: active ? BRAND : "inherit" }}>
        {t(label)}<i className={`ti ${active ? (sort.direction === "asc" ? "ti-arrow-up" : "ti-arrow-down") : "ti-arrows-sort"}`} aria-hidden="true" style={{ fontSize: 13, opacity: active ? 1 : 0.5 }} />
      </button>
    </th>
  );
}

export default function SeriesTable({ rows, drafts, overlaps, sort, onSort, onField, onSave, onReset }: Props) {
  const t = useT();
  return (
    <section aria-label={t("ID ranges")} className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <SortHeader label="Worker type" sortKey="name" sort={sort} onSort={onSort} />
              <SortHeader label="Range from" sortKey="range_start" sort={sort} onSort={onSort} />
              <th>{t("Range to")}</th><th>{t("Next number")}</th><th>{t("Next ID")}</th>
              <SortHeader label="Used" sortKey="usage" sort={sort} onSort={onSort} />
              <th>{t("Status")}</th><th style={{ textAlign: "right" }}>{t("Actions")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => {
              const draft = drafts[row.employment_type];
              if (!draft) return null;
              const dirty = isDraftDirty(row, draft);
              const overlapping = overlaps.has(row.employment_type);
              const isUsedUp = draft.form.next_sequence > draft.form.range_end;
              const health = HEALTH_STYLE[healthOf(row.usage_percent, row.is_exhausted)];
              const barColour = usageColour(row.usage_percent, row.is_exhausted);
              return (
                <tr key={row.employment_type} aria-label={row.employment_type_display} style={{ background: overlapping ? tint("#DC2626", 0.05) : dirty ? tint("#EA580C", 0.05) : undefined, boxShadow: `inset 3px 0 0 ${overlapping ? "#DC2626" : dirty ? "#EA580C" : "transparent"}` }}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span aria-hidden="true" style={{ width: 30, height: 30, borderRadius: 9, display: "grid", placeItems: "center", fontSize: 14, fontWeight: 800, color: "#fff", background: BRAND }}>{leadingDigit(row.range_start)}</span>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: 13.5, color: "var(--on-bg)" }}>{row.employment_type_display}</div>
                        {overlapping && <div style={{ fontSize: 11, fontWeight: 700, color: "#DC2626" }}><i className="ti ti-alert-triangle" aria-hidden="true" /> {t("Overlaps another range")}</div>}
                      </div>
                    </div>
                  </td>
                  {INPUTS.map(input => (
                    <td key={input.key} style={{ verticalAlign: "top", paddingTop: 12 }}>
                      <input
                        type="number" aria-label={`${row.employment_type_display} ${t(input.label)}`} className={`field-input${draft.errors[input.key] ? " field-error" : ""}`}
                        value={draft.text[input.key]} onChange={event => onField(row.employment_type, input.key, event.target.value)}
                        onKeyDown={event => { if (event.key === "Enter") onSave(row.employment_type); }} style={{ width: 118, fontFamily: MONO_FONT }}
                      />
                      {draft.errors[input.key] && <div className="field-error-msg" style={{ maxWidth: 180 }}>{draft.errors[input.key]}</div>}
                    </td>
                  ))}
                  <td style={{ fontFamily: MONO_FONT, fontWeight: 800, fontSize: 14, color: isUsedUp ? "#DC2626" : BRAND }}>{isUsedUp ? t("Exhausted") : draft.form.next_sequence}</td>
                  <td style={{ minWidth: 130 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "var(--on-variant)", marginBottom: 4 }}><span>{row.usage_percent}%</span><span>{t("{count} left", { count: idsLeft(draft.form).toLocaleString("en-IN") })}</span></div>
                    <div role="progressbar" aria-label={t("{name} range used", { name: row.employment_type_display })} aria-valuenow={row.usage_percent} aria-valuemin={0} aria-valuemax={100} style={{ height: 6, borderRadius: 999, background: tint(barColour, 0.15), overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${Math.min(Math.max(row.usage_percent, row.usage_percent > 0 ? 2 : 0), 100)}%`, background: barColour }} />
                    </div>
                  </td>
                  <td><span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 11.5, fontWeight: 700, padding: "3px 10px", borderRadius: 999, whiteSpace: "nowrap", background: tint(health.colour, 0.14), color: health.colour }}><i className={`ti ${health.icon}`} aria-hidden="true" />{t(health.label)}</span></td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    {draft.apiError && <div role="alert" className="field-error-msg" style={{ margin: "0 0 4px" }}>{draft.apiError}</div>}
                    {!dirty && draft.saved && <span style={{ fontSize: 12, fontWeight: 700, color: "#16A34A", marginRight: 8 }}><i className="ti ti-check" aria-hidden="true" /> {t("Saved")}</span>}
                    {dirty && <button type="button" className="btn btn-ghost btn-sm" onClick={() => onReset(row.employment_type)} disabled={draft.saving} style={{ marginRight: 6 }}>{t("Reset")}</button>}
                    <button type="button" className="btn btn-filled btn-sm" aria-label={t("Save {name}", { name: row.employment_type_display })} disabled={!dirty || draft.saving} onClick={() => onSave(row.employment_type)}>{draft.saving ? t("Saving…") : t("Save")}</button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}

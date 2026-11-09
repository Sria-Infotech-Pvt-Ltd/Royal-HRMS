"use client";

import { ROW_STATUS_LABEL } from "@/lib/employeeImport";
import type { ImportPreviewRow, ImportSummary } from "@/types/employeeImport";

interface SummaryProps {
  summary: ImportSummary;
}

const TILES: { key: keyof ImportSummary; label: string; color: string }[] = [
  { key: "total", label: "Total rows", color: "var(--on-bg)" },
  { key: "valid", label: "Valid", color: "var(--success)" },
  { key: "invalid", label: "Invalid", color: "var(--error)" },
  { key: "duplicate", label: "Duplicate", color: "var(--warn)" },
];

export function ImportSummaryTiles({ summary }: SummaryProps) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8, marginBottom: 14 }}>
      {TILES.map(tile => (
        <div key={tile.key} style={{ border: "1px solid var(--outline-v)", borderRadius: 8, padding: "10px 6px", textAlign: "center" }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: tile.color }}>{summary[tile.key]}</div>
          <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{tile.label}</div>
        </div>
      ))}
    </div>
  );
}

interface TableProps {
  rows: ImportPreviewRow[];
}

const STATUS_COLOR = { valid: "var(--success)", invalid: "var(--error)", duplicate: "var(--warn)" } as const;

/** Row-by-row preview: non-sensitive columns only, with the errors found for each row. */
export default function ImportPreviewTable({ rows }: TableProps) {
  return (
    <div style={{ border: "1px solid var(--outline-v)", borderRadius: 8, maxHeight: 280, overflow: "auto" }}>
      <table style={{ width: "100%", fontSize: 12 }}>
        <thead>
          <tr style={{ background: "var(--bg-low)", position: "sticky", top: 0 }}>
            {["Row", "Status", "Name", "Work Email", "Branch", "Position", "Joining", "Errors"].map(heading => (
              <th key={heading} style={{ textAlign: "left", padding: "6px 10px" }}>{heading}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.row} style={{ borderTop: "1px solid var(--outline-v)", verticalAlign: "top" }}>
              <td style={{ padding: "6px 10px" }}>{row.row}</td>
              <td style={{ padding: "6px 10px", color: STATUS_COLOR[row.status], fontWeight: 600 }}>{ROW_STATUS_LABEL[row.status]}</td>
              <td style={{ padding: "6px 10px" }}>{`${row.values.first_name ?? ""} ${row.values.last_name ?? ""}`.trim()}</td>
              <td style={{ padding: "6px 10px" }}>{row.values.email}</td>
              <td style={{ padding: "6px 10px" }}>{row.values.branch}</td>
              <td style={{ padding: "6px 10px" }}>{row.values.position}</td>
              <td style={{ padding: "6px 10px" }}>{row.values.date_of_joining}</td>
              <td style={{ padding: "6px 10px", color: "var(--error)" }}>{row.errors.join(" ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

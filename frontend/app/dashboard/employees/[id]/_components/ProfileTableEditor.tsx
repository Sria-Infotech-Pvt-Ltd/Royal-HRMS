"use client";

import { useRef, useState } from "react";
import { type ProfileSection, type TableColumn, type TableRow } from "../../_data";

/* ── shared cell input style ────────────────────────────────── */
const CELL =
  "w-full px-2.5 py-1.5 rounded-md border text-[12.5px] outline-none transition-all" +
  " bg-[var(--surface)] placeholder:text-[#7c8aa3]" +
  " focus:border-[var(--primary)] focus:ring-1 focus:ring-[rgba(124,58,237,0.15)]";

/* ── table editor with read/edit toggle ─────────────────────── */
export default function TableEditor({
  section,
  rows,
  onRowsChange,
}: {
  section: Extract<ProfileSection, { kind: "table" }>;
  rows: TableRow[];
  onRowsChange: (rows: TableRow[]) => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const counter = useRef(0);

  function blankRow(): TableRow {
    counter.current += 1;
    const r: TableRow = { _id: `new-${counter.current}` };
    section.columns.forEach((c) => { r[c.key] = ""; });
    return r;
  }

  const addRow = () => {
    const r = blankRow();
    onRowsChange([...rows, r]);
    setEditingId(r._id);
  };
  const removeRow = (id: string) => {
    onRowsChange(rows.filter((r) => r._id !== id));
    setEditingId(null);
  };
  const updateCell = (id: string, key: string, val: string) =>
    onRowsChange(rows.map((r) => (r._id === id ? { ...r, [key]: val } : r)));

  return (
    <div>
      {/* Sub-header — description + add button */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-[13px]" style={{ color: "var(--on-variant)" }}>
          {section.description ?? `Manage ${section.label.toLowerCase()} records`}
        </p>
        <button
          onClick={addRow}
          suppressHydrationWarning
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg border text-[13px] font-medium transition-colors"
          style={{ borderColor: "var(--outline-v)", color: "var(--primary)", background: "var(--surface)" }}
        >
          <i className="ti ti-plus text-[13px]" />
          {section.addLabel}
        </button>
      </div>

      {/* Table */}
      <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--outline-v)" }}>
        <table className="w-full border-collapse">
          <thead>
            <tr style={{ background: "var(--bg-low)", borderBottom: "1px solid var(--outline-v)" }}>
              {section.columns.map((c) => (
                <th
                  key={c.key}
                  className="text-left text-[11px] font-semibold uppercase tracking-wide px-4 py-3 whitespace-nowrap"
                  style={{ color: "var(--on-variant)" }}
                >
                  {c.label}
                </th>
              ))}
              <th
                className="text-right text-[11px] font-semibold uppercase tracking-wide px-4 py-3"
                style={{ color: "var(--on-variant)" }}
              >
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={section.columns.length + 1}
                  className="px-4 py-10 text-center text-[13px]"
                  style={{ color: "var(--on-variant)" }}
                >
                  No records yet — click &ldquo;{section.addLabel}&rdquo; to add one.
                </td>
              </tr>
            ) : (
              rows.map((row) => {
                const isEditing = editingId === row._id;
                return (
                  <tr
                    key={row._id}
                    className="border-b last:border-0"
                    style={{ borderColor: "var(--outline-v)" }}
                  >
                    {section.columns.map((col) => (
                      <td key={col.key} className="px-4 py-3 align-middle">
                        {isEditing ? (
                          <CellInput
                            col={col}
                            value={row[col.key] ?? ""}
                            onChange={(v) => updateCell(row._id, col.key, v)}
                          />
                        ) : (
                          <CellDisplay col={col} value={row[col.key] ?? ""} />
                        )}
                      </td>
                    ))}

                    {/* Action */}
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setEditingId(isEditing ? null : row._id)}
                          title={isEditing ? "Done" : "Edit"}
                          suppressHydrationWarning
                          className="w-7 h-7 flex items-center justify-center rounded-md border transition-colors"
                          style={{
                            borderColor: "var(--outline-v)",
                            color: isEditing ? "var(--primary)" : "var(--on-variant)",
                            background: isEditing ? "rgba(124,58,237,0.06)" : "#fff",
                          }}
                        >
                          <i className={`ti ${isEditing ? "ti-check" : "ti-pencil"} text-[13px]`} />
                        </button>
                        {isEditing && (
                          <button
                            onClick={() => removeRow(row._id)}
                            title="Delete"
                            suppressHydrationWarning
                            className="w-7 h-7 flex items-center justify-center rounded-md transition-colors"
                            style={{ color: "var(--error)" }}
                          >
                            <i className="ti ti-trash text-[13px]" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ── read-only cell display ─────────────────────────────────── */
function CellDisplay({ col, value }: { col: TableColumn; value: string }) {
  if (!value) {
    return <span className="text-[13px]" style={{ color: "var(--on-variant)" }}>—</span>;
  }

  /* Yes / No badge */
  if (col.key === "dependent") {
    const yes = value.toLowerCase() === "yes";
    return (
      <span
        className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[12px] font-medium"
        style={{
          background: yes ? "rgba(23,144,90,0.12)" : "rgba(194,58,47,0.10)",
          color: yes ? "#17905a" : "#c23a2f",
        }}
      >
        {yes ? "Yes" : "No"}
      </span>
    );
  }

  /* Name — primary colour */
  if (col.key === "name") {
    return (
      <span className="text-[13px] font-semibold" style={{ color: "var(--primary)" }}>
        {value}
      </span>
    );
  }

  /* Relationship — accent */
  if (col.key === "relationship") {
    return (
      <span className="text-[13px]" style={{ color: "var(--primary)" }}>
        {value}
      </span>
    );
  }

  /* Date fields — format "mmm d, yyyy" */
  if (col.type === "date") {
    const [y, m, d] = value.split("-").map(Number);
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    if (y && m && d) {
      return (
        <span className="text-[13px]" style={{ color: "var(--on-bg)" }}>
          {months[m - 1]} {d}, {y}
        </span>
      );
    }
  }

  return <span className="text-[13px]" style={{ color: "var(--on-bg)" }}>{value}</span>;
}

/* ── editable cell input ────────────────────────────────────── */
function CellInput({
  col,
  value,
  onChange,
}: {
  col: TableColumn;
  value: string;
  onChange: (v: string) => void;
}) {
  if (col.type === "select") {
    return (
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        suppressHydrationWarning
        className={`${CELL} field-select`}
        style={{ borderColor: "#d3dae8" }}
      >
        <option value="">—</option>
        {col.options?.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    );
  }
  return (
    <input
      type={col.type === "date" ? "date" : col.type === "number" ? "number" : "text"}
      value={value}
      placeholder={col.placeholder}
      onChange={(e) => onChange(e.target.value)}
      suppressHydrationWarning
      className={CELL}
      style={{ borderColor: "#d3dae8" }}
    />
  );
}

"use client";

import React, { useRef, useState } from "react";
import type {
  DetailValues,
  DocEntry,
  FieldOption,
  ProfileSection,
  TableColumn,
  TableRow,
} from "../../_data";
import FormField from "../../_components/FormField";
import DocPreviewModal from "@/components/DocPreviewModal";

/* ── shared cell input style ────────────────────────────────── */
const CELL =
  "w-full px-2.5 py-1.5 rounded-md border text-[12.5px] outline-none transition-all" +
  " bg-white placeholder:text-[#7c8aa3]" +
  " focus:border-[var(--primary)] focus:ring-1 focus:ring-[rgba(30,78,140,0.15)]";

export default function ProfileForm({
  section,
  values,
  rows,
  dirty,
  saving,
  liveDocuments,
  fieldOptions,
  fieldSlot,
  readOnly,
  onFieldChange,
  onRowsChange,
  onSave,
  onCancel,
  onEdit,
  onUploadDocument,
  uploadingDocType,
  docUploadError,
}: {
  section: ProfileSection;
  values: DetailValues;
  rows: TableRow[];
  dirty: boolean;
  saving?: boolean;
  liveDocuments?: DocEntry[];
  fieldOptions?: Record<string, FieldOption[]>;
  fieldSlot?: (key: string, disabled: boolean) => React.ReactNode | null | "hidden";
  readOnly?: boolean;
  onFieldChange: (key: string, val: string) => void;
  onRowsChange: (rows: TableRow[]) => void;
  onSave: () => void;
  onCancel: () => void;
  onEdit?: () => void;
  onUploadDocument?: (documentType: string, file: File) => void;
  uploadingDocType?: string | null;
  docUploadError?: string;
}) {
  return (
    <div
      className="rounded-xl border overflow-hidden flex flex-col"
      style={{ background: "#fff", borderColor: "var(--outline-v)" }}
    >
      {/* ── Blue header ─────────────────────────────────────── */}
      <div
        className="flex items-center justify-between px-5 py-3"
        style={{ background: "var(--primary)" }}
      >
        <div className="flex items-center gap-2">
          <i className={`ti ${section.icon} text-[16px] text-white`} />
          <h3 className="text-[14px] font-semibold text-white">{section.label}</h3>
        </div>
        <div className="flex items-center gap-1">
          <HeaderBtn icon="ti-upload" title="Import" />
          <HeaderBtn icon="ti-download" title="Export" />
          {readOnly && onEdit && (
            <button
              onClick={onEdit}
              suppressHydrationWarning
              title="Edit"
              className="flex items-center gap-1.5 ml-1 px-3 py-1.5 rounded-lg text-[12px] font-semibold text-white/90 border border-white/30 hover:bg-white/15 transition-colors"
            >
              <i className="ti ti-pencil text-[13px]" />
              Edit
            </button>
          )}
        </div>
      </div>

      {/* ── Body ────────────────────────────────────────────── */}
      <div className="p-7 flex-1">
        {section.kind === "grid" && (
          <div className="grid grid-cols-2 gap-x-6 gap-y-5">
            {section.fields.map((f) => {
              const slot = fieldSlot?.(f.key, readOnly ?? true);
              if (slot === "hidden") return null;
              if (slot != null) {
                return <div key={f.key}>{slot}</div>;
              }
              const overrideOpts = fieldOptions?.[f.key];
              const mergedField = overrideOpts ? { ...f, options: overrideOpts } : f;
              return (
                <FormField
                  key={f.key}
                  field={mergedField}
                  value={values[f.key] ?? ""}
                  onChange={onFieldChange}
                  disabled={readOnly}
                />
              );
            })}
          </div>
        )}

        {section.kind === "table" && (
          <TableEditor section={section} rows={rows} onRowsChange={onRowsChange} />
        )}

        {section.kind === "docs" && (
          section.variant === "table"
            ? <DocsTable documents={liveDocuments ?? section.documents} />
            : (
              <DocsCards
                documents={liveDocuments ?? section.documents}
                onUpload={onUploadDocument}
                uploadingDocType={uploadingDocType}
                uploadError={docUploadError}
              />
            )
        )}
      </div>

      {/* ── Footer — hidden in read-only mode ───────────────── */}
      {!readOnly && (
        <div
          className="flex items-center justify-end gap-3 px-6 py-3 border-t"
          style={{ borderColor: "var(--outline-v)", background: "var(--bg-low)" }}
        >
          <button
            onClick={onCancel}
            disabled={!dirty}
            suppressHydrationWarning
            className="px-4 py-2 rounded-lg text-[13px] font-medium border transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ borderColor: "var(--outline-v)", color: "var(--on-bg)", background: "#fff" }}
          >
            Cancel
          </button>
          <button
            onClick={onSave}
            disabled={saving}
            suppressHydrationWarning
            className="flex items-center gap-2 px-5 py-2 rounded-lg text-[13px] font-semibold text-white transition-colors shadow-sm disabled:opacity-70 disabled:cursor-not-allowed"
            style={{ background: "var(--primary)" }}
          >
            <i className={`ti ${saving ? "ti-loader-2 animate-spin" : "ti-device-floppy"} text-[15px]`} />
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      )}
    </div>
  );
}

/* ── header icon button ─────────────────────────────────────── */
function HeaderBtn({ icon, title }: { icon: string; title: string }) {
  return (
    <button
      title={title}
      suppressHydrationWarning
      className="w-8 h-8 flex items-center justify-center rounded-lg text-white/80 hover:bg-white/15 transition-colors"
    >
      <i className={`ti ${icon} text-[16px]`} />
    </button>
  );
}

/* ── table editor with read/edit toggle ─────────────────────── */
function TableEditor({
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
          style={{ borderColor: "var(--outline-v)", color: "var(--primary)", background: "#fff" }}
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
                            background: isEditing ? "rgba(30,78,140,0.06)" : "#fff",
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
          background: yes ? "rgba(27,138,107,0.12)" : "rgba(192,57,43,0.10)",
          color: yes ? "#1b8a6b" : "#c0392b",
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
        className={CELL}
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

function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const DOC_ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

/* ── Employee Documents — 4-col card grid ───────────────────── */
function DocsCards({
  documents,
  onUpload,
  uploadingDocType,
  uploadError,
}: {
  documents: DocEntry[];
  onUpload?: (documentType: string, file: File) => void;
  uploadingDocType?: string | null;
  uploadError?: string;
}) {
  const [preview, setPreview] = useState<DocEntry | null>(null);

  function handleFileChange(documentType: string, e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file to re-trigger onChange
    if (file && onUpload) onUpload(documentType, file);
  }

  return (
    <>
      {preview && preview.fileUrl && (
        <DocPreviewModal
          name={preview.name}
          fileName={preview.fileName}
          fileUrl={preview.fileUrl}
          fileSize={preview.fileSize}
          onClose={() => setPreview(null)}
        />
      )}

      <div>
        <div className="mb-5">
          <p className="text-[13px]" style={{ color: "var(--on-variant)" }}>
            All documents uploaded by the employee or{" "}
            <span className="font-semibold" style={{ color: "var(--primary)" }}>HR</span>
          </p>
          {uploadError && (
            <p className="text-[12.5px] font-medium mt-2" style={{ color: "var(--error)" }}>
              {uploadError}
            </p>
          )}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: "1rem" }}>
          {documents.map((doc) => {
            const uploaded   = !!doc.fileUrl;
            const uploading  = uploadingDocType === doc.documentType;
            return (
              <div
                key={doc.name}
                className="flex items-center gap-3 px-3.5 py-3 rounded-xl border bg-white"
                style={{ borderColor: "var(--outline-v)" }}
              >
                <div
                  className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: uploaded ? "rgba(27,138,107,0.10)" : "var(--bg-mid)" }}
                >
                  <i
                    className={`ti ${uploading ? "ti-loader-2 animate-spin" : uploaded ? "ti-file-check" : "ti-file-off"} text-[18px]`}
                    style={{ color: uploaded ? "#1b8a6b" : "var(--on-variant)" }}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-[13px] font-semibold truncate leading-snug" style={{ color: "var(--on-bg)" }}>
                    {doc.name}
                  </p>
                  <p className="text-[11.5px] leading-snug" style={{ color: "var(--on-variant)" }}>
                    {uploading
                      ? "Uploading…"
                      : uploaded
                        ? `${doc.uploadedOn}${doc.fileSize ? ` · ${fmtBytes(doc.fileSize)}` : ""}`
                        : "Not uploaded"}
                  </p>
                </div>
                <label
                  title={uploaded ? "Replace document" : "Upload document"}
                  suppressHydrationWarning
                  className={`w-7 h-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-mid)] flex-shrink-0 transition-colors ${uploading ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
                  style={{ color: "var(--on-variant)" }}
                >
                  <i className={`ti ${uploaded ? "ti-refresh" : "ti-upload"} text-[15px]`} />
                  <input
                    type="file"
                    accept={DOC_ACCEPT}
                    className="hidden"
                    disabled={uploading}
                    onChange={(e) => handleFileChange(doc.documentType, e)}
                  />
                </label>
                <button
                  title={uploaded ? "Preview document" : "Not uploaded"}
                  disabled={!uploaded}
                  onClick={() => uploaded && setPreview(doc)}
                  suppressHydrationWarning
                  className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-mid)] flex-shrink-0 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  style={{ color: uploaded ? "var(--primary)" : "var(--on-variant)" }}
                >
                  <i className="ti ti-eye text-[15px]" />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}

/* ── Joining Document — table with Verified / Pending status ── */
function DocsTable({ documents }: { documents: DocEntry[] }) {
  const [preview, setPreview] = useState<DocEntry | null>(null);
  return (
    <>
      {preview && preview.fileUrl && (
        <DocPreviewModal
          name={preview.name}
          fileName={preview.fileName}
          fileUrl={preview.fileUrl}
          fileSize={preview.fileSize}
          onClose={() => setPreview(null)}
        />
      )}
    <div>
      {/* Info banner */}
      <div
        className="flex items-center gap-2.5 px-4 py-3 rounded-lg mb-5"
        style={{ background: "rgba(30,78,140,0.06)", border: "1px solid rgba(30,78,140,0.15)" }}
      >
        <i className="ti ti-info-circle text-[16px]" style={{ color: "var(--primary)" }} />
        <p className="text-[13px]" style={{ color: "var(--primary)" }}>
          Joining documents are mandatory and locked once verified by HR.
        </p>
      </div>

      {/* Status table */}
      <div className="rounded-lg border overflow-hidden" style={{ borderColor: "var(--outline-v)" }}>
        <table className="w-full border-collapse">
          <thead>
            <tr style={{ background: "var(--bg-low)", borderBottom: "1px solid var(--outline-v)" }}>
              {["Document", "Required", "Status", "Uploaded On", "Action"].map((h) => (
                <th
                  key={h}
                  className="text-left text-[11px] font-semibold uppercase tracking-wide px-4 py-3 whitespace-nowrap"
                  style={{ color: "var(--on-variant)" }}
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => (
              <tr
                key={doc.name}
                className="border-b last:border-0"
                style={{ borderColor: "var(--outline-v)" }}
              >
                {/* Document name */}
                <td className="px-4 py-3.5">
                  <span className="text-[13px] font-semibold" style={{ color: "var(--on-bg)" }}>
                    {doc.name}
                  </span>
                </td>

                {/* Required */}
                <td className="px-4 py-3.5">
                  <span className="text-[13px]" style={{ color: "var(--on-variant)" }}>
                    {doc.required ? "Yes" : "No"}
                  </span>
                </td>

                {/* Status badge */}
                <td className="px-4 py-3.5">
                  {doc.status === "verified" && (
                    <span
                      className="inline-flex items-center px-3 py-0.5 rounded-full text-[12px] font-medium"
                      style={{ background: "rgba(27,138,107,0.12)", color: "#1b8a6b" }}
                    >
                      Verified
                    </span>
                  )}
                  {doc.status === "pending" && (
                    <span
                      className="inline-flex items-center px-3 py-0.5 rounded-full text-[12px] font-medium"
                      style={{ background: "rgba(234,179,8,0.15)", color: "#b45309" }}
                    >
                      Pending
                    </span>
                  )}
                  {!doc.status && (
                    <span className="text-[13px]" style={{ color: "var(--on-variant)" }}>—</span>
                  )}
                </td>

                {/* Uploaded on */}
                <td className="px-4 py-3.5">
                  <span
                    className="text-[13px]"
                    style={{ color: doc.uploadedOn ? "var(--primary)" : "var(--on-variant)" }}
                  >
                    {doc.uploadedOn ?? "—"}
                  </span>
                </td>

                {/* Action */}
                <td className="px-4 py-3.5">
                  <button
                    suppressHydrationWarning
                    disabled={!doc.fileUrl}
                    onClick={() => doc.fileUrl && setPreview(doc)}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-[12.5px] font-medium transition-colors hover:bg-[var(--bg-mid)] disabled:opacity-30 disabled:cursor-not-allowed"
                    style={{ borderColor: "var(--outline-v)", color: "var(--on-bg)", background: "#fff" }}
                  >
                    <i className="ti ti-eye text-[13px]" />
                    View
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
    </>
  );
}

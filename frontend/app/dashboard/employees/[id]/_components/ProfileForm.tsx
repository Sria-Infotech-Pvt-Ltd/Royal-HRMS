"use client";

import React from "react";
import {
  type DetailValues,
  type DocEntry,
  type FieldOption,
  type ProfileSection,
  type TableRow,
} from "../../_data";
import FormField from "../../_components/FormField";
import TableEditor from "./ProfileTableEditor";
import DocsCards from "./ProfileDocsCards";
import DocsTable from "./ProfileDocsTable";

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
      style={{ background: "var(--surface)", borderColor: "var(--outline-v)" }}
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
            style={{ borderColor: "var(--outline-v)", color: "var(--on-bg)", background: "var(--surface)" }}
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

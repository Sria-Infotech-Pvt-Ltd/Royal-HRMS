"use client";

import { useState } from "react";
import type { CustomFieldFileValue } from "@/types/onboardingFieldConfig";
import DocPreviewModal from "@/components/DocPreviewModal";

const FILE_ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
  fieldKey: string;
  label: string;
  required?: boolean;
  allowMultiple: boolean;
  value: CustomFieldFileValue[];
  uploading?: boolean;
  onUpload: (fieldKey: string, file: File) => void;
  // Omitted in read-only contexts (e.g. self-service Profile's
  // Personal/Education/Bank tabs) to disable delete/replace entirely.
  onDelete?: (fieldKey: string, valueId: number) => void;
  disabled?: boolean;
}

// Shared file/image custom-field upload control — one component for the
// onboarding wizard, self-service Profile (Emergency, editable; Personal/
// Education/Bank, read-only via onDelete omitted), and HR Employee Detail
// (via the fieldSlot extension point). Modeled on ProfileForm.tsx's
// DocsCards: hidden file input behind a styled icon button, upload spinner,
// filename+size badge, delete, preview via the existing DocPreviewModal.
// Only the endpoint/value source differs per call site — plumbed by the
// parent through onUpload/onDelete/value, not by this component.
export default function CustomFieldFileUpload({
  fieldKey, label, required, allowMultiple, value, uploading, onUpload, onDelete, disabled,
}: Props) {
  const [preview, setPreview] = useState<CustomFieldFileValue | null>(null);
  const canAddMore = allowMultiple || value.length === 0;
  const readOnly = !onDelete;

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = ""; // allow re-selecting the same file
    if (file) onUpload(fieldKey, file);
  }

  function renderCard(item: CustomFieldFileValue | null) {
    const uploaded = !!item?.file_url;
    return (
      <div
        key={item?.id ?? "empty"}
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
            {item?.file_name || label}
          </p>
          <p className="text-[11.5px] leading-snug" style={{ color: "var(--on-variant)" }}>
            {uploading
              ? "Uploading…"
              : uploaded
                ? `${new Date(item!.uploaded_at).toLocaleDateString()}${item!.file_size ? ` · ${fmtBytes(item!.file_size)}` : ""}`
                : "Not uploaded"}
          </p>
        </div>
        {!readOnly && !disabled && (!allowMultiple || !uploaded) && (
          <label
            title={uploaded ? "Replace file" : "Upload file"}
            suppressHydrationWarning
            className={`w-7 h-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-mid)] flex-shrink-0 transition-colors ${uploading ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
            style={{ color: "var(--on-variant)" }}
          >
            <i className={`ti ${uploaded ? "ti-refresh" : "ti-upload"} text-[15px]`} />
            <input
              type="file"
              accept={FILE_ACCEPT}
              className="hidden"
              disabled={uploading}
              onChange={handleFileChange}
            />
          </label>
        )}
        {!readOnly && !disabled && uploaded && item && (
          <button
            type="button"
            title="Delete file"
            onClick={() => onDelete!(fieldKey, item.id)}
            suppressHydrationWarning
            className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-mid)] flex-shrink-0 transition-colors"
            style={{ color: "var(--error)" }}
          >
            <i className="ti ti-trash text-[15px]" />
          </button>
        )}
        <button
          type="button"
          title={uploaded ? "Preview file" : "Not uploaded"}
          disabled={!uploaded}
          onClick={() => uploaded && item && setPreview(item)}
          suppressHydrationWarning
          className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-[var(--bg-mid)] flex-shrink-0 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          style={{ color: uploaded ? "var(--primary)" : "var(--on-variant)" }}
        >
          <i className="ti ti-eye text-[15px]" />
        </button>
      </div>
    );
  }

  return (
    <div>
      {preview && preview.file_url && (
        <DocPreviewModal
          name={label}
          fileName={preview.file_name}
          fileUrl={preview.file_url}
          fileSize={preview.file_size}
          onClose={() => setPreview(null)}
        />
      )}

      <p className="text-[12px] font-medium mb-1.5" style={{ color: "var(--on-variant)" }}>
        {label}{required && <span style={{ color: "var(--error)" }}> *</span>}
      </p>

      <div className="flex flex-col gap-2">
        {value.length === 0 ? renderCard(null) : value.map(item => renderCard(item))}
        {!readOnly && !disabled && allowMultiple && canAddMore && value.length > 0 && (
          <label
            suppressHydrationWarning
            className={`flex items-center justify-center gap-2 px-3.5 py-2.5 rounded-xl border border-dashed text-[12.5px] font-medium transition-colors ${uploading ? "opacity-40 cursor-not-allowed" : "cursor-pointer hover:bg-[var(--bg-mid)]"}`}
            style={{ borderColor: "var(--outline-v)", color: "var(--on-variant)" }}
          >
            <i className="ti ti-plus text-[14px]" />
            Add file
            <input
              type="file"
              accept={FILE_ACCEPT}
              className="hidden"
              disabled={uploading}
              onChange={handleFileChange}
            />
          </label>
        )}
      </div>
    </div>
  );
}

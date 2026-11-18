"use client";

import { useEffect, useMemo, useRef, useState } from "react";

const MAX_RECEIPT_BYTES = 5 * 1024 * 1024;
const ALLOWED_TYPES = ["image/jpeg", "image/png", "application/pdf"];
const RECEIPT_PREVIEW_LIFETIME_MS = 60_000;

interface Props {
  files: File[];
  error?: string;
  onChange: (files: File[]) => void;
  onError: (message: string | undefined) => void;
}

function openReceiptPreview(file: File) {
  const url = URL.createObjectURL(file);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), RECEIPT_PREVIEW_LIFETIME_MS);
}

function sizeLabel(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** Checks the type and size of every file; returns the first problem, or null when all are fine. */
function firstProblem(selected: File[]): string | null {
  for (const file of selected) {
    if (file.size > MAX_RECEIPT_BYTES) return `"${file.name}" exceeds 5 MB.`;
    if (!ALLOWED_TYPES.includes(file.type)) return `"${file.name}" must be PDF, JPG, or PNG.`;
  }
  return null;
}

/** Image receipts get a small thumbnail; the object URLs are released when the list changes or the form closes. */
function useThumbnails(files: File[]): string[] {
  const urls = useMemo(() => files.map(file => (file.type.startsWith("image/") ? URL.createObjectURL(file) : "")), [files]);
  useEffect(() => () => urls.forEach(url => url && URL.revokeObjectURL(url)), [urls]);
  return urls;
}

export default function ExpenseReceiptPicker({ files, error, onChange, onError }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const thumbnails = useThumbnails(files);

  function accept(selected: File[]) {
    if (!selected.length) return;
    const problem = firstProblem(selected);
    if (problem) { onError(problem); return; }
    onError(undefined);
    onChange([...files, ...selected]);
  }

  return (
    <div>
      {files.length > 0 && (
        <div className="xf-files">
          {files.map((file, index) => (
            <div key={`${file.name}-${index}`} className="xf-file">
              <span className="xf-thumb" style={thumbnails[index] ? { backgroundImage: `url(${thumbnails[index]})`, backgroundSize: "cover", backgroundPosition: "center" } : undefined}>
                {!thumbnails[index] && <i className="ti ti-file-type-pdf" />}
              </span>
              <div className="xf-file-main">
                <div className="xf-file-name">{file.name}</div>
                <div className="xf-file-size">{sizeLabel(file.size)}</div>
              </div>
              <button type="button" className="xf-icon-btn" title="View receipt" aria-label={`View receipt ${file.name}`} onClick={() => openReceiptPreview(file)}>
                <i className="ti ti-eye" />
              </button>
              <button type="button" className="xf-icon-btn" style={{ color: "var(--error)" }} aria-label={`Remove receipt ${file.name}`} onClick={() => onChange(files.filter((_, i) => i !== index))}>
                <i className="ti ti-x" />
              </button>
            </div>
          ))}
        </div>
      )}

      <div
        className={`xf-drop${isDragging ? " is-over" : ""}${error ? " is-bad" : ""}`}
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); inputRef.current?.click(); } }}
        onDragOver={event => { event.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={event => { event.preventDefault(); setIsDragging(false); accept(Array.from(event.dataTransfer.files)); }}
      >
        <i className="ti ti-cloud-upload" />
        <p>{files.length > 0 ? "Add more receipts" : "Drag receipts here or click to upload"}</p>
        <small>PDF, JPG, PNG up to 5 MB each — at least one required</small>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.jpg,.jpeg,.png"
        multiple
        style={{ display: "none" }}
        onChange={event => { accept(Array.from(event.target.files ?? [])); event.target.value = ""; }}
      />
      {error && <p className="field-error-msg">{error}</p>}
    </div>
  );
}

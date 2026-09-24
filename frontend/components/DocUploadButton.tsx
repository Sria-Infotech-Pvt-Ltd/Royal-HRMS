"use client";

import { useRef } from "react";

export interface HireDocument {
  id: string;
  document_type: string;
  document_type_display: string;
  entry_ref: string;
  file_name: string;
  file_size: number;
  uploaded_at: string;
}

interface Props {
  documentType: string;
  label: string;
  existing?: HireDocument;
  uploading: boolean;
  onUpload: (documentType: string, file: File, entryRef?: string) => void;
  onDelete?: (doc: HireDocument) => void;
  /** The specific education/experience entry this file belongs to — set
   * for per-entry attachments (a certificate per qualification, a letter
   * per employer), left unset for the one-slot-per-type documents
   * (PAN, Aadhaar, Passport, etc). */
  entryRef?: string;
}

/** Small inline "Upload"/"Uploaded" control shared by the Hire wizard's
 * Statutory step (PAN/Aadhaar/Passport), its Documents step (every item),
 * and Education & Experience (one certificate per entry) — all talk to the
 * same hire-action document endpoint, so a file uploaded from any of these
 * places shows up as already-uploaded everywhere else, with no separate
 * state to keep in sync. */
export default function DocUploadButton({ documentType, label, existing, uploading, onUpload, onDelete, entryRef }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  function handleFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) onUpload(documentType, file, entryRef);
    e.target.value = "";
  }

  if (existing) {
    return (
      <div className="flex items-center gap-2" style={{ fontSize: 12 }}>
        <span className="badge badge-success"><i className="ti ti-circle-check" /> Uploaded</span>
        <span style={{ color: "var(--on-variant)" }} title={existing.file_name}>
          {existing.file_name.length > 22 ? `${existing.file_name.slice(0, 19)}…` : existing.file_name}
        </span>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="btn btn-ghost btn-sm"
          disabled={uploading}
        >
          Replace
        </button>
        {onDelete && (
          <button
            type="button"
            onClick={() => onDelete(existing)}
            className="btn btn-ghost btn-sm"
            style={{ color: "var(--error)" }}
            disabled={uploading}
            title={`Remove ${label}`}
          >
            <i className="ti ti-trash" />
          </button>
        )}
        <input ref={inputRef} type="file" accept=".pdf,.jpg,.jpeg,.png" style={{ display: "none" }} onChange={handleFile} />
      </div>
    );
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className="btn btn-ghost btn-sm"
        disabled={uploading}
      >
        {uploading ? <><i className="ti ti-loader-2 animate-spin" /> Uploading…</> : <><i className="ti ti-upload" /> Upload {label}</>}
      </button>
      <input ref={inputRef} type="file" accept=".pdf,.jpg,.jpeg,.png" style={{ display: "none" }} onChange={handleFile} />
    </div>
  );
}

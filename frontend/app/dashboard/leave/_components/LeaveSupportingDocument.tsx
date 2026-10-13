"use client";

// Optional / required supporting document for a leave request — a compact upload row
// that turns into a file row (with view and remove) once a file is picked.

import { useState, type ChangeEvent } from "react";
import {
  ACCEPTED_EXTENSIONS, ACCEPTED_TYPES_LABEL, MAX_FILE_SIZE_LABEL, formatFileSize, openFilePreview, validateDocumentFile,
} from "@/lib/documentFile";
import { Err, Lbl } from "./applyLeaveFormHelpers";

interface Props {
  file: File | null;
  isRequired: boolean;
  error?: string;
  onChange: (file: File | null) => void;
}

export default function LeaveSupportingDocument({ file, isRequired, error, onChange }: Props) {
  const [fileError, setFileError] = useState<string | null>(null);

  function handlePicked(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0];
    event.target.value = "";
    if (!picked) return;
    const problem = validateDocumentFile(picked);
    setFileError(problem);
    if (!problem) onChange(picked);
  }

  return (
    <div>
      <Lbl text="Supporting document" required={isRequired} hint={isRequired ? undefined : "Optional"} />
      {file ? (
        <div className="flex items-center gap-3 rounded-lg border border-[var(--outline-v)] bg-[var(--bg-low)] px-3.5 py-2.5">
          <i className="ti ti-file text-base text-[var(--primary)]" />
          <span className="min-w-0 flex-1 truncate text-[13px] text-[var(--on-bg)]" title={file.name}>{file.name}</span>
          <span className="text-xs text-[var(--on-variant)]">{formatFileSize(file.size)}</span>
          <button type="button" onClick={() => openFilePreview(file)} aria-label="View file" title="View file" className="text-[var(--on-variant)] hover:text-[var(--primary)]">
            <i className="ti ti-eye" />
          </button>
          <button type="button" onClick={() => { onChange(null); setFileError(null); }} aria-label="Remove file" title="Remove file" className="text-[var(--on-variant)] hover:text-[var(--error)]">
            <i className="ti ti-x" />
          </button>
        </div>
      ) : (
        <label className={[
          "flex cursor-pointer items-center gap-3 rounded-lg border border-dashed px-3.5 py-3 transition-colors",
          error || fileError ? "border-[var(--error)]" : "border-[var(--outline)] hover:border-[var(--primary)]",
        ].join(" ")}>
          <i className="ti ti-upload text-base text-[var(--on-variant)]" />
          <span className="text-[13px] text-[var(--on-bg)]">
            <span className="font-semibold text-[var(--primary)]">Choose a file</span>
            <span className="ml-2 text-xs text-[var(--on-variant)]">{ACCEPTED_TYPES_LABEL} · up to {MAX_FILE_SIZE_LABEL}</span>
          </span>
          <input type="file" accept={ACCEPTED_EXTENSIONS.join(",")} className="hidden" onChange={handlePicked} />
        </label>
      )}
      <Err msg={fileError ?? error} />
    </div>
  );
}

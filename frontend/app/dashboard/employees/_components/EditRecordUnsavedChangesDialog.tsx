"use client";

import { useId, useRef } from "react";
import { useDialogFocus } from "@/hooks/useDialogFocus";

interface Props {
  saving: boolean;
  savingDraft: boolean;
  onKeepEditing: () => void;
  onDontSave: () => void;
  onSaveAsDraft: () => void;
  onSave: () => void;
}

/** Unsaved-changes confirmation shown by EditRecordModal's close (X/Esc/
 * backdrop/browser-close) path — a separate component (not inline JSX) so
 * useDialogFocus's mount-time effect actually runs each time this dialog
 * opens, trapping Tab inside it and giving Esc/stacking priority over the
 * edit modal underneath, the same way ConfirmModal.tsx does. */
export default function EditRecordUnsavedChangesDialog({
  saving, savingDraft, onKeepEditing, onDontSave, onSaveAsDraft, onSave,
}: Props) {
  const mouseDownOnOverlay = useRef(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useDialogFocus(dialogRef, onKeepEditing);

  return (
    <div
      className="modal-overlay open"
      style={{ zIndex: 1010 }}
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) onKeepEditing(); }}
    >
      <div ref={dialogRef} tabIndex={-1} role="alertdialog" aria-modal="true" aria-labelledby={titleId} className="modal" style={{ maxWidth: "min(440px, 94vw)" }}>
        <div className="modal-header">
          <div id={titleId} className="modal-title">You have unsaved changes</div>
        </div>
        <div className="modal-body">
          <p style={{ fontSize: 14, color: "var(--on-variant)", lineHeight: 1.6, margin: 0 }}>
            What would you like to do with your changes?
          </p>
        </div>
        <div className="modal-footer" style={{ flexWrap: "wrap", gap: 8 }}>
          {/* Default focus lands here per spec — the safest action (don't lose anything, keep going). */}
          <button autoFocus className="btn btn-ghost" onClick={onKeepEditing}>Keep editing</button>
          <button className="btn btn-ghost" onClick={onDontSave}>Don&apos;t save</button>
          <button className="btn btn-ghost" disabled={savingDraft} onClick={onSaveAsDraft}>
            {savingDraft ? "Saving…" : "Save as draft"}
          </button>
          <button className="btn btn-filled" disabled={saving} onClick={onSave}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

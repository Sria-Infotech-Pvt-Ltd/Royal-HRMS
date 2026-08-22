"use client";

import { useRef } from "react";

interface Props {
  title:        string;
  body:         string;
  confirmLabel: string;
  danger?:      boolean;
  saving?:      boolean;
  onConfirm:    () => void;
  onCancel:     () => void;
}

export default function ConfirmModal({ title, body, confirmLabel, danger, saving, onConfirm, onCancel }: Props) {
  const btnCls = danger ? "btn-danger" : "btn-filled";
  // A click's target is resolved at mouseup, not mousedown — selecting the
  // body text and releasing past the modal's edge would otherwise land on
  // the overlay and close it. Only close when the gesture both started AND
  // ended on the backdrop itself.
  const mouseDownOnOverlay = useRef(false);

  return (
    <div
      className="modal-overlay open"
      style={{ zIndex: 1010 }}
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) onCancel(); }}
    >
      <div className="modal" style={{ maxWidth: "min(420px, 94vw)" }}>
        <div className="modal-header">
          <div className="modal-title" style={danger ? { color: "var(--error)" } : undefined}>
            <i className={`ti ${danger ? "ti-alert-triangle" : "ti-help-circle"}`} style={{ marginRight: 8 }} />
            {title}
          </div>
          <button className="modal-close" onClick={onCancel} suppressHydrationWarning>
            <i className="ti ti-x" />
          </button>
        </div>

        <div className="modal-body">
          <p style={{ fontSize: 14, color: "var(--on-variant)", lineHeight: 1.6, margin: 0 }}>{body}</p>
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onCancel} disabled={saving} suppressHydrationWarning>
            Go Back
          </button>
          <button className={`btn ${btnCls}`} onClick={onConfirm} disabled={saving} suppressHydrationWarning>
            {saving ? <><i className="ti ti-loader-2 spin" /> Working…</> : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

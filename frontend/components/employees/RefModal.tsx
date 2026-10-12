"use client";

// The Employee Directory reference's dialog shell: a title with an italic accent word, a one-line subtitle,
// a scrolling body of stacked sections, and a footer with a status note on the left and the actions on the
// right. Used by "Perform an action", "Basic pay" and "Leave". Other dialogs keep the app's shared <Modal>.

import { useEffect, useId, useRef, type ReactNode } from "react";

interface Props {
  /** Plain part of the title, e.g. "Basic". */
  title: string;
  /** Italic accent word, e.g. "pay". */
  accent: string;
  subtitle?: ReactNode;
  onClose: () => void;
  /** Disables close (X, backdrop, Esc) while something is saving. */
  closeDisabled?: boolean;
  children: ReactNode;
  /** Left side of the footer. */
  note?: ReactNode;
  /** Right side of the footer — buttons. */
  actions: ReactNode;
}

export default function RefModal({ title, accent, subtitle, onClose, closeDisabled = false, children, note, actions }: Props) {
  const titleId = useId();
  const pressedOnBackdrop = useRef(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape" && !closeDisabled) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose, closeDisabled]);

  return (
    <div
      className="ref-modal-back"
      onMouseDown={event => { pressedOnBackdrop.current = event.target === event.currentTarget; }}
      onClick={event => { if (pressedOnBackdrop.current && event.target === event.currentTarget && !closeDisabled) onClose(); }}
    >
      <div className="modal sm ref-modal" role="dialog" aria-modal="true" aria-labelledby={titleId}>
        <div className="modal-head">
          <div>
            <h2 id={titleId}>{title} <em className="hl">{accent}</em></h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <button className="xbtn" type="button" aria-label="Close" onClick={onClose} disabled={closeDisabled}>
            <i className="ti ti-x" />
          </button>
        </div>
        <div className="modal-body">
          <div className="actform">{children}</div>
        </div>
        <div className="modal-foot">
          <div className="progwrap">{note}</div>
          <div className="footacts">{actions}</div>
        </div>
      </div>
    </div>
  );
}

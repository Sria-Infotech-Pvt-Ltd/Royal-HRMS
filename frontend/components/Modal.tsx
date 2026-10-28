"use client";

import { useId, useRef, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useDialogFocus } from "@/hooks/useDialogFocus";

interface ModalProps {
  title: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  size?: "default" | "lg";
  maxWidth?: number | string;
  zIndex?: number;
  /** Disables the header close (X) button and backdrop-click-to-close — for modals mid save/delete. */
  closeDisabled?: boolean;
  /** Override modal-body's default padding, e.g. `{ padding: 0 }` for an edge-to-edge table. */
  bodyStyle?: CSSProperties;
  /**
   * Pins the header and footer in place and scrolls only the body — for tall
   * forms where the footer should stay visible while the form scrolls.
   * Without this, the whole modal scrolls together (the default, and correct
   * behavior for most modals).
   */
  scrollBody?: boolean;
}

export default function Modal({
  title,
  onClose,
  children,
  footer,
  size = "default",
  maxWidth,
  zIndex,
  closeDisabled = false,
  bodyStyle,
  scrollBody = false,
}: ModalProps) {
  function handleClose() {
    if (!closeDisabled) onClose();
  }

  // A click's target is resolved at mouseup, not mousedown — selecting text
  // inside a field and releasing the drag past the modal's edge would
  // otherwise land on the overlay and close it mid-input. Only close when
  // the gesture both started AND ended on the backdrop itself.
  const mouseDownOnOverlay = useRef(false);
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  // Focus moves in, Tab stays in, Esc closes (unless a save is running), focus returns to the opener on close.
  useDialogFocus(dialogRef, closeDisabled ? null : onClose);

  // Rendered at the top level of the page (document.body), not where the caller happens to sit in the tree. A
  // position:fixed element inside a transformed ancestor — e.g. the employee side panel, which slides in with
  // `transform: translateX(...)` — is positioned and clipped against THAT ancestor, not the screen, so a modal
  // opened from inside the panel appeared half-hidden underneath it.
  const overlay = (
    <div
      className="modal-overlay open"
      style={zIndex ? { zIndex } : undefined}
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => {
        if (mouseDownOnOverlay.current && e.target === e.currentTarget) handleClose();
      }}
    >
      <div
        ref={dialogRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`modal${size === "lg" ? " modal-lg" : ""}`}
        style={{
          // The `.modal`/`.modal-lg` classes set a fixed `width`, and CSS
          // `max-width` can only shrink a fixed width, never grow it — so a
          // maxWidth larger than the class's width (e.g. 1100 vs .modal-lg's
          // 780) would otherwise be silently ignored. Setting `width` here
          // makes it the actual target size; deliberately NOT setting inline
          // `max-width` too, so the class's own `max-width: 95vw` keeps
          // capping it responsively on narrow viewports.
          ...(maxWidth ? { width: maxWidth } : undefined),
          ...(scrollBody ? { display: "flex", flexDirection: "column", maxHeight: "90vh" } : undefined),
        }}
      >
        <div className="modal-header" style={scrollBody ? { flexShrink: 0 } : undefined}>
          <div className="modal-title" id={titleId}>{title}</div>
          <button
            className="modal-close"
            aria-label="Close"
            suppressHydrationWarning
            onClick={handleClose}
            disabled={closeDisabled}
            style={closeDisabled ? { opacity: 0.4, cursor: "not-allowed" } : undefined}
          >
            <i className="ti ti-x" />
          </button>
        </div>
        <div
          className="modal-body"
          style={{
            ...(scrollBody ? { flex: 1, overflowY: "auto" } : undefined),
            // bodyStyle last so a caller can deliberately override scrollBody's
            // own overflow/flex defaults (e.g. a multi-pane layout that wants
            // to scroll its own inner panes independently instead of the
            // whole body scrolling as one block).
            ...bodyStyle,
          }}
        >
          {children}
        </div>
        {footer && (
          <div className="modal-footer" style={scrollBody ? { flexShrink: 0 } : undefined}>
            {footer}
          </div>
        )}
      </div>
    </div>
  );
  return typeof document === "undefined" ? overlay : createPortal(overlay, document.body);
}

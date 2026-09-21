"use client";

import { useRef, type CSSProperties, type ReactNode } from "react";

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

  return (
    <div
      className="modal-overlay open"
      style={zIndex ? { zIndex } : undefined}
      onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
      onClick={e => {
        if (mouseDownOnOverlay.current && e.target === e.currentTarget) handleClose();
      }}
    >
      <div
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
          <div className="modal-title">{title}</div>
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
            ...bodyStyle,
            ...(scrollBody ? { flex: 1, overflowY: "auto" } : undefined),
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
}

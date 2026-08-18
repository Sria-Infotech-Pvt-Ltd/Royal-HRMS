"use client";

import type { CSSProperties, ReactNode } from "react";

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

  return (
    <div
      className="modal-overlay open"
      style={zIndex ? { zIndex } : undefined}
      onClick={e => e.target === e.currentTarget && handleClose()}
    >
      <div
        className={`modal${size === "lg" ? " modal-lg" : ""}`}
        style={{
          ...(maxWidth ? { maxWidth } : undefined),
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

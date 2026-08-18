"use client";

import type { ReactNode } from "react";
import Modal from "./Modal";

interface ConfirmDialogProps {
  title: ReactNode;
  message: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: "primary" | "success" | "danger";
  loading?: boolean;
  onConfirm: () => void;
  onClose: () => void;
  children?: ReactNode;
  maxWidth?: number | string;
}

export default function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  confirmVariant = "primary",
  loading = false,
  onConfirm,
  onClose,
  children,
  maxWidth = 420,
}: ConfirmDialogProps) {
  const confirmClass =
    confirmVariant === "success" ? "btn-success" : confirmVariant === "danger" ? "btn-danger" : "btn-primary";

  return (
    <Modal
      title={title}
      onClose={onClose}
      maxWidth={maxWidth}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={loading} suppressHydrationWarning>
            {cancelLabel}
          </button>
          <button className={`btn ${confirmClass}`} onClick={onConfirm} disabled={loading} suppressHydrationWarning>
            {loading ? (
              <>
                <i className="ti ti-loader-2 spin" /> Working…
              </>
            ) : (
              confirmLabel
            )}
          </button>
        </>
      }
    >
      <p style={{ fontSize: 14, color: "var(--on-variant)", lineHeight: 1.6, marginBottom: children ? 12 : 0 }}>
        {message}
      </p>
      {children}
    </Modal>
  );
}

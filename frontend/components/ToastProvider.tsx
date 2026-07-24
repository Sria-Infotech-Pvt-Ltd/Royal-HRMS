"use client";

import { createContext, useCallback, useContext, useState } from "react";

type ToastType = "success" | "error" | "info";

interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

interface ToastContextValue {
  showToast: (message: string, type?: ToastType) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}

const ICON: Record<ToastType, string> = {
  success: "ti-circle-check",
  error:   "ti-alert-circle",
  info:    "ti-info-circle",
};

// A flat 4s timeout reads fine for "Saved." but disappears mid-sentence for
// something like the leave-type clarification question. Scale with message
// length instead (~roughly reading speed), clamped so short toasts don't
// linger and very long ones don't sit forever — manual dismiss (click)
// covers whatever that clamp doesn't.
const MIN_DURATION_MS = 3000;
const MAX_DURATION_MS = 10000;
const MS_PER_CHARACTER = 60;

function toastDuration(message: string): number {
  return Math.min(MAX_DURATION_MS, Math.max(MIN_DURATION_MS, message.length * MS_PER_CHARACTER));
}

let _id = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const showToast = useCallback((message: string, type: ToastType = "info") => {
    const id = ++_id;
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => dismiss(id), toastDuration(message));
  }, [dismiss]);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="toast-container">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`toast toast-${t.type}`}
            onClick={() => dismiss(t.id)}
            title="Dismiss"
            style={{ cursor: "pointer" }}
          >
            <i className={`ti ${ICON[t.type]}`} style={{ fontSize: 16, flexShrink: 0 }} />
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

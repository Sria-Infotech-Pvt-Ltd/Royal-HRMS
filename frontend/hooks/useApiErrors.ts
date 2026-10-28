"use client";

// A form's failed-save handling in one place: the server's message as a toast, and each field's message beside its input.
// `handleError(err, fallback)` is all a catch block needs; the spinner stays the form's own (reset it in `finally`).

import { useCallback, useState } from "react";
import { useToast } from "@/components/ToastProvider";
import { parseApiError, type ParsedApiError } from "@/lib/apiError";

export function useApiErrors(labels?: Record<string, string>) {
  const { showToast } = useToast();
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);

  const handleError = useCallback((err: unknown, fallback: string): ParsedApiError => {
    const parsed = parseApiError(err, fallback, labels);
    setFieldErrors(parsed.fieldErrors);
    setFormError(parsed.message);
    showToast(parsed.message, "error");
    return parsed;
  }, [labels, showToast]);

  const clearAll = useCallback(() => { setFieldErrors({}); setFormError(null); }, []);

  /** Drops one field's message as soon as the person edits that field. */
  const clearField = useCallback((key: string) => {
    setFieldErrors(previous => {
      if (!(key in previous)) return previous;
      const remaining = { ...previous };
      delete remaining[key];
      return remaining;
    });
  }, []);

  return { fieldErrors, formError, handleError, clearAll, clearField };
}

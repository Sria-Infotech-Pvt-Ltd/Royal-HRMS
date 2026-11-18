"use client";

import { useEffect, useRef } from "react";
import type { CheckState } from "@/lib/permissionMatrixView";

interface TriStateCheckboxProps {
  state: CheckState;
  onChange: () => void;
  label: string;
  isDisabled?: boolean;
}

/** A checkbox that also shows "some of these are on" (the dash), for a row or a column header that switches many permissions. */
export default function TriStateCheckbox({ state, onChange, label, isDisabled = false }: TriStateCheckboxProps) {
  const reference = useRef<HTMLInputElement | null>(null);
  useEffect(() => {
    if (reference.current) reference.current.indeterminate = state === "some";
  }, [state]);
  return (
    <input
      ref={reference}
      type="checkbox"
      className="h-4 w-4 cursor-pointer accent-[var(--primary)] disabled:cursor-not-allowed"
      checked={state === "all"}
      disabled={isDisabled}
      onChange={onChange}
      aria-label={label}
      aria-checked={state === "some" ? "mixed" : state === "all"}
    />
  );
}

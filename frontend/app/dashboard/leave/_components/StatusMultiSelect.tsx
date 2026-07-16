"use client";

import { useEffect, useRef, useState } from "react";

export interface StatusOption {
  value: string;
  label: string;
}

interface Props {
  options:  StatusOption[];
  selected: string[];
  onChange: (values: string[]) => void;
}

export default function StatusMultiSelect({ options, selected, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function toggle(value: string) {
    onChange(selected.includes(value) ? selected.filter(v => v !== value) : [...selected, value]);
  }

  const buttonLabel = selected.length === 0
    ? "All Statuses"
    : selected.length === 1
      ? (options.find(o => o.value === selected[0])?.label ?? selected[0])
      : `${selected.length} statuses`;

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        suppressHydrationWarning
        className="flex items-center gap-2 px-3 py-1.5 text-[13px] rounded-lg border border-[var(--outline-v)] bg-white text-[var(--on-bg)] min-w-[160px] justify-between"
      >
        {buttonLabel}
        <i className={`ti ti-chevron-down text-xs transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute z-20 mt-1 w-56 rounded-lg border border-[var(--outline-v)] bg-white shadow-lg p-2 flex flex-col gap-0.5">
          {options.map(opt => (
            <label key={opt.value} className="module-check w-full py-1 px-1">
              <input type="checkbox" checked={selected.includes(opt.value)} onChange={() => toggle(opt.value)} />
              <span>{opt.label}</span>
            </label>
          ))}
          {selected.length > 0 && (
            <button
              type="button"
              suppressHydrationWarning
              onClick={() => onChange([])}
              className="text-xs text-[var(--primary)] mt-1 px-1 text-left"
            >
              Clear all
            </button>
          )}
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";

export interface SearchableSelectOption {
  value: string;
  label: string;
}

interface Props {
  value: string;
  onChange: (value: string) => void;
  options: SearchableSelectOption[];
  placeholder?: string;
  inputClassName?: string;
  disabled?: boolean;
  searchPlaceholder?: string;
}

/** Generic searchable single-select dropdown — the same pattern already
 * used by CountrySelect.tsx and StateDistrictSelect.tsx, extracted here so
 * any plain native <select> in the app (which the browser is free to open
 * ABOVE its trigger whenever it decides there isn't enough room below —
 * exactly what happened with the Hire modal's Org Unit/Position selects,
 * a decision this component's own CSS controls instead of leaving to the
 * browser) can be swapped for one with predictable, always-below
 * positioning without hand-rolling the open/search/click-outside logic
 * again at each call site. */
export default function SearchableSelect({
  value, onChange, options, placeholder, inputClassName = "finput", disabled, searchPlaceholder,
}: Props) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const filtered = options.filter(o => o.label.toLowerCase().includes(search.trim().toLowerCase()));
  const selected = options.find(o => o.value === value);

  function select(option: SearchableSelectOption) {
    onChange(option.value);
    setSearch("");
    setOpen(false);
  }

  return (
    <div ref={rootRef} style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => { if (!disabled) setOpen(o => !o); }}
        className={inputClassName}
        disabled={disabled}
        style={{ width: "100%", textAlign: "left", cursor: disabled ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6, opacity: disabled ? 0.6 : 1 }}
      >
        <span style={{ color: selected ? "inherit" : "var(--on-variant, #7c8aa3)" }}>
          {selected?.label || placeholder || "Select"}
        </span>
        <i className="ti ti-chevron-down" style={{ fontSize: 14, color: "var(--on-variant)", flexShrink: 0 }} />
      </button>

      {open && !disabled && (
        <div
          style={{
            position: "absolute", top: "calc(100% + 4px)", left: 0, zIndex: 30,
            width: "100%", minWidth: 220, maxHeight: 280, overflow: "hidden", display: "flex", flexDirection: "column",
            background: "var(--surface, #fff)", border: "1px solid var(--outline-v, #e2e2e2)",
            borderRadius: 8, boxShadow: "0 8px 24px rgba(0,0,0,0.14)",
          }}
        >
          <input
            autoFocus
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={searchPlaceholder ?? "Search…"}
            className={inputClassName}
            style={{ margin: 6, width: "calc(100% - 12px)" }}
          />
          <div style={{ overflowY: "auto" }}>
            {filtered.length === 0 && (
              <div style={{ padding: "8px 12px", fontSize: 12, color: "var(--on-variant)" }}>No matches.</div>
            )}
            {filtered.map(o => (
              <div
                key={o.value}
                onClick={() => select(o)}
                style={{
                  padding: "6px 12px", cursor: "pointer", fontSize: 12.5,
                  background: o.value === value ? "rgba(124,58,237,0.08)" : "transparent",
                }}
              >
                {o.label}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

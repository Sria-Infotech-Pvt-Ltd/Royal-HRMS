"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { COUNTRIES } from "@/lib/countries";

interface CountrySelectProps {
  value: string;
  onChange: (value: string) => void;
  /** "demonym" for a Nationality-style field ("Indian"); "name" for a
   * Country-style field ("India"). Both modes read the same master list —
   * see lib/countries.ts — so the two never drift out of sync with
   * each other even as that list is updated over time. */
  mode: "demonym" | "name";
  placeholder?: string;
  inputClassName?: string;
}

/** Single-select searchable country dropdown, backed by the one shared
 * country list (lib/countries.ts) instead of a free-text box — stores/emits
 * a plain string, so it's a drop-in replacement for a plain <input> with no
 * schema change. If the current value doesn't match any entry (e.g. an
 * older free-typed value from before this component existed), it's kept
 * as-is and shown selected rather than silently cleared — nothing already
 * saved on an employee's profile appears broken. */
export default function CountrySelect({ value, onChange, mode, placeholder, inputClassName = "field-input" }: CountrySelectProps) {
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

  const options = useMemo(
    () => COUNTRIES.map(c => (mode === "demonym" ? c.demonym : c.name)),
    [mode],
  );
  const filtered = options.filter(o => o.toLowerCase().includes(search.trim().toLowerCase()));
  const isKnownValue = value === "" || options.includes(value);

  function select(option: string) {
    onChange(option);
    setSearch("");
    setOpen(false);
  }

  return (
    <div ref={rootRef} style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className={inputClassName}
        style={{ width: "100%", textAlign: "left", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}
      >
        <span style={{ color: value ? "inherit" : "var(--on-variant, #7c8aa3)" }}>
          {value || placeholder || (mode === "demonym" ? "Select nationality" : "Select country")}
        </span>
        <i className="ti ti-chevron-down" style={{ fontSize: 14, color: "var(--on-variant)", flexShrink: 0 }} />
      </button>
      {!isKnownValue && (
        <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 3 }}>
          Not in the current list — pick one below to update it, or leave as-is.
        </div>
      )}

      {open && (
        <div
          style={{
            position: "absolute", top: "calc(100% + 4px)", left: 0, zIndex: 30,
            width: 260, maxHeight: 300, overflow: "hidden", display: "flex", flexDirection: "column",
            background: "var(--surface, #fff)", border: "1px solid var(--outline-v, #e2e2e2)",
            borderRadius: 8, boxShadow: "0 8px 24px rgba(0,0,0,0.14)",
          }}
        >
          <input
            autoFocus
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder={mode === "demonym" ? "Search nationalities…" : "Search countries…"}
            className={inputClassName}
            style={{ margin: 6, width: "calc(100% - 12px)" }}
          />
          <div style={{ overflowY: "auto" }}>
            {filtered.length === 0 && (
              <div style={{ padding: "8px 12px", fontSize: 12, color: "var(--on-variant)" }}>No matches.</div>
            )}
            {filtered.map(o => (
              <div
                key={o}
                onClick={() => select(o)}
                style={{
                  padding: "6px 12px", cursor: "pointer", fontSize: 12.5,
                  background: o === value ? "rgba(124,58,237,0.08)" : "transparent",
                }}
              >
                {o}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

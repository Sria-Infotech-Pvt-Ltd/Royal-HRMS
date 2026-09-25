"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { INDIA_STATE_NAMES, districtsForState } from "@/lib/indiaStatesDistricts";

interface BaseProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  inputClassName?: string;
}

/** Shared dropdown shell for State/District — same searchable single-select
 * pattern as CountrySelect.tsx (this app's existing convention), kept as its
 * own small component here rather than reusing CountrySelect directly since
 * these two read from lib/indiaStatesDistricts.ts, not lib/countries.ts, and
 * District additionally depends on whichever State is currently selected. */
function SearchableSelect({ value, onChange, options, placeholder, inputClassName = "field-input", disabled }: BaseProps & { options: string[]; disabled?: boolean }) {
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

  const filtered = options.filter(o => o.toLowerCase().includes(search.trim().toLowerCase()));
  // A saved value that doesn't match the current list (an older free-typed
  // entry from before this dropdown existed, or a district typed under a
  // different state) is kept as-is and shown selected rather than silently
  // cleared — same "don't break what's already saved" rule CountrySelect
  // itself follows.
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
        onClick={() => { if (!disabled) setOpen(o => !o); }}
        className={inputClassName}
        disabled={disabled}
        style={{ width: "100%", textAlign: "left", cursor: disabled ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6, opacity: disabled ? 0.6 : 1 }}
      >
        <span style={{ color: value ? "inherit" : "var(--on-variant, #7c8aa3)" }}>
          {value || placeholder || "Select"}
        </span>
        <i className="ti ti-chevron-down" style={{ fontSize: 14, color: "var(--on-variant)", flexShrink: 0 }} />
      </button>
      {!isKnownValue && (
        <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 3 }}>
          Not in the current list — pick one below to update it, or leave as-is.
        </div>
      )}

      {open && !disabled && (
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
            placeholder="Search…"
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

/** Single-select searchable dropdown for Indian states/UTs, backed by
 * lib/indiaStatesDistricts.ts instead of a free-text box. */
export function StateSelect({ value, onChange, placeholder, inputClassName }: BaseProps) {
  return (
    <SearchableSelect
      value={value} onChange={onChange}
      options={INDIA_STATE_NAMES}
      placeholder={placeholder ?? "Select state"}
      inputClassName={inputClassName}
    />
  );
}

interface DistrictSelectProps extends BaseProps {
  /** The State this District list is filtered to — an unset/unrecognized
   * state means no district list is known yet, so the field is disabled
   * rather than showing every district in the country unfiltered. */
  state: string;
}

/** Single-select searchable dropdown for districts within `state` — reruns
 * its option list whenever `state` changes; caller is responsible for
 * clearing the District value when the State changes to a different one
 * (a stale district for the previous state is worse than an empty field). */
export function DistrictSelect({ value, onChange, state, placeholder, inputClassName }: DistrictSelectProps) {
  const options = useMemo(() => districtsForState(state), [state]);
  const disabled = !state;
  return (
    <SearchableSelect
      value={value} onChange={onChange}
      options={options}
      placeholder={disabled ? "Select state first" : (placeholder ?? "Select district")}
      inputClassName={inputClassName}
      disabled={disabled}
    />
  );
}

"use client";

import { useEffect, useMemo, useRef, useState } from "react";

// India's 22 scheduled languages plus English (the language most HR forms
// in India actually ask about) and the handful of other international
// languages an employee's profile realistically needs — not a full
// ISO-639 list, which would make the dropdown unusable.
const ALL_LANGUAGES = [
  "English", "Hindi", "Assamese", "Bengali", "Bodo", "Dogri", "Gujarati",
  "Kannada", "Kashmiri", "Konkani", "Maithili", "Malayalam", "Manipuri",
  "Marathi", "Nepali", "Odia", "Punjabi", "Sanskrit", "Santali", "Sindhi",
  "Tamil", "Telugu", "Urdu",
  "Arabic", "Chinese (Mandarin)", "French", "German", "Japanese",
  "Portuguese", "Russian", "Spanish",
];

function parseSelected(value: string): string[] {
  return value.split(",").map(v => v.trim()).filter(Boolean);
}

interface LanguagesSelectProps {
  value: string; // comma-separated, e.g. "Telugu, Hindi, English" — same shape this field already stored
  onChange: (value: string) => void;
  placeholder?: string;
  inputClassName?: string;
}

/** Multi-select dropdown of languages with a search box and checkbox list —
 * stores/emits the same comma-separated string this field already used, so
 * it's a drop-in replacement for the free-text input with no schema change. */
export default function LanguagesSelect({ value, onChange, placeholder, inputClassName = "field-input" }: LanguagesSelectProps) {
  const selected = useMemo(() => parseSelected(value), [value]);
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

  function toggle(lang: string) {
    const next = selected.includes(lang) ? selected.filter(l => l !== lang) : [...selected, lang];
    onChange(next.join(", "));
  }

  const filtered = ALL_LANGUAGES.filter(l => l.toLowerCase().includes(search.trim().toLowerCase()));

  return (
    <div ref={rootRef} style={{ position: "relative" }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className={inputClassName}
        style={{
          width: "100%", display: "flex", alignItems: "center", flexWrap: "wrap", gap: 5,
          cursor: "pointer", minHeight: 38, textAlign: "left",
        }}
      >
        {selected.length === 0 ? (
          <span style={{ color: "var(--on-variant, #7c8aa3)" }}>{placeholder ?? "Select languages"}</span>
        ) : (
          selected.map(lang => (
            <span
              key={lang}
              style={{
                fontSize: 11.5, fontWeight: 600, padding: "2px 8px", borderRadius: 20,
                background: "rgba(124,58,237,0.10)", color: "var(--primary, #7c3aed)",
                display: "inline-flex", alignItems: "center", gap: 4,
              }}
            >
              {lang}
              <i
                className="ti ti-x"
                style={{ fontSize: 10, cursor: "pointer" }}
                onClick={e => { e.stopPropagation(); toggle(lang); }}
              />
            </span>
          ))
        )}
      </button>

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
            placeholder="Search languages…"
            className={inputClassName}
            style={{ margin: 6, width: "calc(100% - 12px)" }}
          />
          <div style={{ overflowY: "auto" }}>
            {filtered.length === 0 && (
              <div style={{ padding: "8px 12px", fontSize: 12, color: "var(--on-variant)" }}>No matches.</div>
            )}
            {filtered.map(lang => (
              <label
                key={lang}
                style={{
                  display: "flex", alignItems: "center", gap: 8, padding: "6px 12px",
                  cursor: "pointer", fontSize: 12.5,
                }}
              >
                <input type="checkbox" checked={selected.includes(lang)} onChange={() => toggle(lang)} />
                {lang}
              </label>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

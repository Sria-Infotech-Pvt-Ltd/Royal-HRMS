"use client";

import { useEffect, useMemo, useRef, useState } from "react";

interface CountryDialOption { iso: string; dial: string; flag: string; name: string; }

// Common countries this app's employees/candidates are realistically hiring
// from or relocating between — not the full ISO-3166 list, to keep the
// dropdown scannable. India first and used as the default/fallback country,
// matching the "+91 90000 00000" placeholder every phone field in this app
// already used before this component existed.
const COUNTRY_DIAL_OPTIONS: CountryDialOption[] = [
  { iso: "IN", dial: "91",  flag: "🇮🇳", name: "India" },
  { iso: "US", dial: "1",   flag: "🇺🇸", name: "United States" },
  { iso: "CA", dial: "1",   flag: "🇨🇦", name: "Canada" },
  { iso: "GB", dial: "44",  flag: "🇬🇧", name: "United Kingdom" },
  { iso: "AE", dial: "971", flag: "🇦🇪", name: "United Arab Emirates" },
  { iso: "SA", dial: "966", flag: "🇸🇦", name: "Saudi Arabia" },
  { iso: "QA", dial: "974", flag: "🇶🇦", name: "Qatar" },
  { iso: "KW", dial: "965", flag: "🇰🇼", name: "Kuwait" },
  { iso: "OM", dial: "968", flag: "🇴🇲", name: "Oman" },
  { iso: "SG", dial: "65",  flag: "🇸🇬", name: "Singapore" },
  { iso: "MY", dial: "60",  flag: "🇲🇾", name: "Malaysia" },
  { iso: "AU", dial: "61",  flag: "🇦🇺", name: "Australia" },
  { iso: "NZ", dial: "64",  flag: "🇳🇿", name: "New Zealand" },
  { iso: "DE", dial: "49",  flag: "🇩🇪", name: "Germany" },
  { iso: "FR", dial: "33",  flag: "🇫🇷", name: "France" },
  { iso: "NP", dial: "977", flag: "🇳🇵", name: "Nepal" },
  { iso: "BD", dial: "880", flag: "🇧🇩", name: "Bangladesh" },
  { iso: "LK", dial: "94",  flag: "🇱🇰", name: "Sri Lanka" },
  { iso: "PH", dial: "63",  flag: "🇵🇭", name: "Philippines" },
  { iso: "ZA", dial: "27",  flag: "🇿🇦", name: "South Africa" },
  { iso: "JP", dial: "81",  flag: "🇯🇵", name: "Japan" },
  { iso: "CN", dial: "86",  flag: "🇨🇳", name: "China" },
];

const DEFAULT_COUNTRY = COUNTRY_DIAL_OPTIONS[0];

// Longest dial code first, so "+971..." isn't mis-parsed against a
// shorter, unrelated dial code that happens to share a leading digit.
const BY_DIAL_LENGTH_DESC = [...COUNTRY_DIAL_OPTIONS].sort((a, b) => b.dial.length - a.dial.length);

function splitValue(value: string): { country: CountryDialOption; national: string } {
  const trimmed = value.trim();
  if (trimmed.startsWith("+")) {
    const digits = trimmed.slice(1);
    const match = BY_DIAL_LENGTH_DESC.find(c => digits.startsWith(c.dial));
    if (match) {
      return { country: match, national: digits.slice(match.dial.length).replace(/^[\s-]+/, "") };
    }
  }
  return { country: DEFAULT_COUNTRY, national: trimmed };
}

interface PhoneInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  /** Class applied to both the flag button and the number input — this app
   * has two co-existing field-style classes ("field-input" in most places,
   * "finput" in the reference-mockup-styled components like the Hire
   * wizard's EmergencyContactsList), so callers pass whichever their
   * surrounding fields already use rather than this component guessing. */
  inputClassName?: string;
}

/** A phone number input with a country-code picker — shows that country's
 * flag once selected, or auto-detected from a pasted/typed "+<dial>..."
 * value (e.g. pasting "+971 50 123 4567" auto-selects the UAE flag).
 * Stores/emits one plain "+<dial> <national number>" string — the exact
 * shape every phone field in this app already stored before this component
 * existed, so it's a drop-in replacement for a plain `<input>` with no
 * schema change on either side. */
export default function PhoneInput({ value, onChange, placeholder, className, inputClassName = "field-input" }: PhoneInputProps) {
  const { country, national } = useMemo(() => splitValue(value), [value]);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  function commit(nextCountry: CountryDialOption, nextNational: string) {
    const trimmed = nextNational.trim();
    onChange(trimmed ? `+${nextCountry.dial} ${trimmed}` : "");
  }

  return (
    <div ref={rootRef} className={className} style={{ position: "relative", display: "flex", gap: 6 }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className={inputClassName}
        title={country.name}
        style={{ width: 76, flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", gap: 4, cursor: "pointer" }}
      >
        <span style={{ fontSize: 16, lineHeight: 1 }}>{country.flag}</span>
        <span style={{ fontSize: 12, color: "var(--on-variant)" }}>+{country.dial}</span>
      </button>
      <input
        value={national}
        onChange={e => commit(country, e.target.value)}
        placeholder={placeholder}
        className={inputClassName}
        style={{ flex: 1, minWidth: 0 }}
      />
      {open && (
        <div
          role="listbox"
          style={{
            position: "absolute", top: "calc(100% + 4px)", left: 0, zIndex: 30,
            width: 230, maxHeight: 260, overflowY: "auto",
            background: "var(--surface, #fff)", border: "1px solid var(--outline-v, #e2e2e2)",
            borderRadius: 8, boxShadow: "0 8px 24px rgba(0,0,0,0.14)",
          }}
        >
          {COUNTRY_DIAL_OPTIONS.map(c => (
            <button
              key={`${c.iso}-${c.dial}`}
              type="button"
              // Prevent the input from blurring before onClick fires — a
              // plain click already handles this fine, but a fast
              // click-drag (common on a scrolling list) can otherwise lose
              // the click to the blur/close handler above.
              onMouseDown={e => e.preventDefault()}
              onClick={() => { commit(c, national); setOpen(false); }}
              style={{
                display: "flex", alignItems: "center", gap: 8, width: "100%",
                padding: "6px 10px", background: "none", border: "none", cursor: "pointer",
                fontSize: 12.5, textAlign: "left",
              }}
            >
              <span style={{ fontSize: 15 }}>{c.flag}</span>
              <span style={{ flex: 1 }}>{c.name}</span>
              <span style={{ color: "var(--on-variant)" }}>+{c.dial}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

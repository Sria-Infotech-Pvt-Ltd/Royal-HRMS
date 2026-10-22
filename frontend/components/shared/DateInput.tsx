"use client";

// A date field that is always typed as DD/MM/YYYY, whatever the browser's locale.
//
// A native <input type="date"> follows the browser's regional format, so on an en-US browser the first box is the
// MONTH: typing "30" for the 30th is read as month 03 and the "0" spills into the day box. This field types the day
// first (the order used everywhere else in the app), inserts the slashes itself, and still offers the browser's
// calendar through the icon. The value it exchanges with the page is the same ISO "YYYY-MM-DD" string a native date
// input uses, so it can replace one without touching the surrounding state ("" while the date is incomplete/invalid).

import { useEffect, useRef, useState, type CSSProperties } from "react";

interface Props {
  /** ISO "YYYY-MM-DD", or "" for no date. */
  value: string;
  onChange: (isoDate: string) => void;
  id?: string;
  className?: string;
  style?: CSSProperties;
  disabled?: boolean;
  readOnly?: boolean;
  required?: boolean;
  title?: string;
  /** ISO bounds — dates outside them are treated as invalid. */
  min?: string;
  max?: string;
  /** Displayed/typed separator — "/" everywhere by default (the app-wide
   * convention). Only override to "-" where a screen's surrounding text
   * already reads DD-MM-YYYY and a mix of the two in one place would be
   * the actual bug (e.g. the Hire modal's summary panel). */
  separator?: "/" | "-";
}

// Layout properties that belong on the outer wrapper (so a fixed-width or flex-sized date filter keeps its size),
// not on the inner text box.
const WRAPPER_STYLE_KEYS = [
  "width", "minWidth", "maxWidth", "flex", "flexGrow", "flexShrink", "flexBasis", "alignSelf", "gridColumn",
  "margin", "marginTop", "marginRight", "marginBottom", "marginLeft",
] as const;

function splitStyle(style: CSSProperties | undefined): { wrapper: CSSProperties; input: CSSProperties } {
  const wrapper: Record<string, unknown> = {};
  const input: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(style ?? {})) {
    if ((WRAPPER_STYLE_KEYS as readonly string[]).includes(key)) wrapper[key] = value;
    else input[key] = value;
  }
  if (wrapper.width !== undefined) input.width = "100%";
  return { wrapper: wrapper as CSSProperties, input: input as CSSProperties };
}

const MIN_YEAR = 1900;
const MAX_YEAR = 2100;

function isoToText(iso: string, sep: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return match ? `${match[3]}${sep}${match[2]}${sep}${match[1]}` : "";
}

function textToIso(text: string, sep: string): string {
  const match = new RegExp(`^(\\d{2})\\${sep}(\\d{2})\\${sep}(\\d{4})$`).exec(text);
  if (!match) return "";
  const day = Number(match[1]);
  const month = Number(match[2]);
  const year = Number(match[3]);
  if (year < MIN_YEAR || year > MAX_YEAR) return "";
  // Reject days the calendar rolls over (31/02 becomes 03/03 in Date).
  const parsed = new Date(year, month - 1, day);
  if (parsed.getFullYear() !== year || parsed.getMonth() !== month - 1 || parsed.getDate() !== day) return "";
  return `${match[3]}-${match[2]}-${match[1]}`;
}

/** Keeps digits only and re-inserts the separator, so typing "30031995" or "30/03/1995" both give 30/03/1995. */
function formatDigits(raw: string, sep: string): string {
  const digits = raw.replace(/\D/g, "").slice(0, 8);
  let formatted = digits.slice(0, 2);
  if (digits.length > 2) formatted += `${sep}${digits.slice(2, 4)}`;
  if (digits.length > 4) formatted += `${sep}${digits.slice(4)}`;
  return formatted;
}

export default function DateInput({ value, onChange, id, className, style, disabled = false, readOnly = false, required = false, title, min, max, separator = "/" }: Props) {
  const { wrapper: wrapperStyle, input: inputStyle } = splitStyle(style);
  const isLocked = disabled || readOnly;
  const [text, setText] = useState(() => isoToText(value, separator));
  const lastEmitted = useRef(value);
  const calendarRef = useRef<HTMLInputElement | null>(null);

  // Follow the page when it changes the value (a resumed draft, a scan-and-fill) — but not for our own echoes.
  useEffect(() => {
    if (value !== lastEmitted.current) {
      lastEmitted.current = value;
      setText(isoToText(value, separator));
    }
  }, [value, separator]);

  function emit(isoDate: string) {
    const withinBounds = isoDate !== "" && (!min || isoDate >= min) && (!max || isoDate <= max);
    const next = withinBounds ? isoDate : "";
    if (next !== lastEmitted.current) {
      lastEmitted.current = next;
      onChange(next);
    }
  }

  function handleTyped(raw: string) {
    const formatted = formatDigits(raw, separator);
    setText(formatted);
    emit(textToIso(formatted, separator));
  }

  function handlePicked(isoDate: string) {
    setText(isoToText(isoDate, separator));
    emit(isoDate);
  }

  function openCalendar() {
    const calendar = calendarRef.current;
    if (!calendar || isLocked) return;
    if (typeof calendar.showPicker === "function") calendar.showPicker();
    else calendar.focus();
  }

  return (
    <div style={{ position: "relative", ...wrapperStyle }}>
      <input
        id={id}
        type="text"
        inputMode="numeric"
        autoComplete="off"
        placeholder={`DD${separator}MM${separator}YYYY`}
        maxLength={10}
        value={text}
        disabled={disabled}
        readOnly={readOnly}
        required={required}
        title={title}
        onChange={event => handleTyped(event.target.value)}
        className={className}
        style={{ ...inputStyle, paddingRight: 36 }}
        suppressHydrationWarning
      />
      <button
        type="button"
        aria-label="Pick a date from the calendar"
        onClick={openCalendar}
        disabled={isLocked}
        tabIndex={-1}
        suppressHydrationWarning
        style={{
          position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", border: 0, background: "none",
          padding: 4, display: "flex", color: "var(--on-variant)", cursor: isLocked ? "not-allowed" : "pointer",
        }}
      >
        <i className="ti ti-calendar" style={{ fontSize: 16 }} />
      </button>
      {/* Hidden native control: only here to supply the browser's calendar popup. */}
      <input
        ref={calendarRef}
        type="date"
        tabIndex={-1}
        aria-hidden="true"
        min={min}
        max={max}
        value={value}
        disabled={disabled}
        onChange={event => handlePicked(event.target.value)}
        style={{ position: "absolute", right: 0, bottom: 0, width: 0, height: 0, opacity: 0, pointerEvents: "none" }}
        suppressHydrationWarning
      />
    </div>
  );
}

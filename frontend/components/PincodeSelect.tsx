"use client";

import { useEffect, useRef, useState } from "react";

export interface PincodeOption {
  pincode: string;
  /** The post-office area the PIN code serves, e.g. "Cyberabad". */
  area: string;
}

interface PincodeSelectProps {
  value: string;
  /** `area` is set when the PIN code was picked from the list, so a caller can use it (for example to fill in the city). */
  onChange: (pincode: string, area?: string) => void;
  /** Every PIN code in the chosen district. Empty until a state and district are chosen (or when none are known). */
  options: PincodeOption[];
  isLoading?: boolean;
  placeholder?: string;
  inputClassName?: string;
}

const isSixDigits = (text: string) => /^\d{6}$/.test(text);

/**
 * A PIN code box. Once a state and district are chosen it becomes a searchable drop-down of that district's PIN codes (each with its
 * area); a PIN code that is not in the list can still be entered. Until then it is a plain 6-digit box.
 */
export default function PincodeSelect({ value, onChange, options, isLoading = false, placeholder, inputClassName = "field-input" }: PincodeSelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [search, setSearch] = useState("");
  const rootRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!isOpen) return;
    function onDocumentClick(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setIsOpen(false);
    }
    document.addEventListener("mousedown", onDocumentClick);
    return () => document.removeEventListener("mousedown", onDocumentClick);
  }, [isOpen]);

  if (options.length === 0) {
    return (
      <input
        value={value} onChange={event => onChange(event.target.value.replace(/\D/g, "").slice(0, 6))}
        placeholder={isLoading ? "Loading PIN codes…" : placeholder ?? "6-digit PIN code"}
        maxLength={6} inputMode="numeric" className={inputClassName}
      />
    );
  }

  const needle = search.trim().toLowerCase();
  const shown = options.filter(option => option.pincode.includes(needle) || option.area.toLowerCase().includes(needle));
  const canUseTyped = isSixDigits(needle) && !options.some(option => option.pincode === needle);
  const chosenArea = options.find(option => option.pincode === value)?.area;

  function pick(pincode: string, area?: string) {
    onChange(pincode, area);
    setSearch("");
    setIsOpen(false);
  }

  return (
    <div ref={rootRef} style={{ position: "relative" }}>
      <button
        type="button" className={inputClassName} aria-haspopup="listbox" aria-expanded={isOpen}
        onClick={() => setIsOpen(open => !open)}
        style={{ width: "100%", textAlign: "left", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}
      >
        <span style={{ color: value ? "inherit" : "var(--on-variant, #7c8aa3)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {value ? `${value}${chosenArea ? ` · ${chosenArea}` : ""}` : placeholder ?? "Select PIN code"}
        </span>
        <i className="ti ti-chevron-down" style={{ fontSize: 14, color: "var(--on-variant)", flexShrink: 0 }} />
      </button>
      {isOpen && (
        <div className="pin-pop" role="listbox">
          <input autoFocus value={search} onChange={event => setSearch(event.target.value)} placeholder={`Search ${options.length} PIN codes or areas…`} className={inputClassName} style={{ margin: 6, width: "calc(100% - 12px)" }} />
          <div style={{ overflowY: "auto" }}>
            {canUseTyped && <div role="option" aria-selected={false} className="pin-row use-typed" onClick={() => pick(needle)}>Use PIN code {needle}</div>}
            {shown.length === 0 && !canUseTyped && <div style={{ padding: "8px 12px", fontSize: 12, color: "var(--on-variant)" }}>No match. Type all 6 digits to use a PIN code that is not listed.</div>}
            {shown.map(option => (
              <div key={option.pincode} role="option" aria-selected={option.pincode === value} className={`pin-row${option.pincode === value ? " is-selected" : ""}`} onClick={() => pick(option.pincode, option.area)}>
                <strong>{option.pincode}</strong>{option.area && <span> · {option.area}</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

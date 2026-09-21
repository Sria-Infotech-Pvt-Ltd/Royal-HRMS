"use client";

import { useEffect, useRef, useState } from "react";

export interface ScrollableSelectOption {
  value: string;
  label: string;
}

interface Props {
  value: string;
  onChange: (value: string) => void;
  options: ScrollableSelectOption[];
  placeholder: string;
  disabled?: boolean;
  hasError?: boolean;
  maxListHeight?: number;
}

// Presentation-only replacement for a plain <select> wherever its option
// list is long enough to dominate the page. A native <select>'s open popup
// can't be height-capped or made to scroll via CSS in any browser — this
// renders the same value/onChange contract as a styled button + absolutely
// positioned, height-capped, scrollable list instead, so callers don't
// change their state model or validation at all, only how the picker opens.
export default function ScrollableSelect({
  value, onChange, options, placeholder, disabled, hasError, maxListHeight = 280,
}: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onClickOutside);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onClickOutside);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  const selected = options.find(o => o.value === value);

  return (
    <div ref={rootRef} style={{ position: "relative" }}>
      <button
        type="button"
        className={`field-input${hasError ? " field-error" : ""}`}
        disabled={disabled}
        onClick={() => setOpen(o => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        style={{
          display: "flex", alignItems: "center", justifyContent: "space-between",
          width: "100%", textAlign: "left",
          cursor: disabled ? "default" : "pointer",
          background: disabled ? "var(--bg-low)" : undefined,
        }}
      >
        <span style={{
          color: selected ? "var(--on-bg)" : "var(--on-variant)",
          overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
        }}>
          {selected ? selected.label : placeholder}
        </span>
        <i className={`ti ti-chevron-${open ? "up" : "down"}`} style={{ fontSize: 14, flexShrink: 0, marginLeft: 8, color: "var(--on-variant)" }} />
      </button>

      {open && !disabled && (
        <div
          role="listbox"
          style={{
            position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 50,
            background: "#fff", border: "1.5px solid var(--outline-v)", borderRadius: "var(--radius)",
            boxShadow: "0 4px 16px rgba(0,0,0,0.12)",
            maxHeight: maxListHeight, overflowY: "auto",
          }}
        >
          {options.length === 0 ? (
            <div style={{ padding: "10px 12px", fontSize: 13, color: "var(--on-variant)" }}>No options</div>
          ) : options.map(o => {
            const isSelected = o.value === value;
            return (
              <div
                key={o.value}
                role="option"
                aria-selected={isSelected}
                onClick={() => { onChange(o.value); setOpen(false); }}
                style={{
                  padding: "9px 12px", fontSize: 13, cursor: "pointer",
                  background: isSelected ? "rgba(30,78,140,0.08)" : "transparent",
                  color: "var(--on-bg)",
                }}
                onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = "var(--bg-low)"; }}
                onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLDivElement).style.background = "transparent"; }}
              >
                {o.label}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

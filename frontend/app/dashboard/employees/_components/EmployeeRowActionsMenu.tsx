"use client";

// The table row's "···" action menu — replaces three separate icon buttons
// with the single overflow-menu button the reference layout uses. Options
// shown depend on the same permissions/status checks the old inline buttons
// used, just collected into one dropdown.

import { useEffect, useRef, useState } from "react";

export interface RowAction {
  label: string;
  icon: string;
  onClick: () => void;
  tone?: "default" | "warn" | "danger" | "success";
}

interface Props {
  actions: RowAction[];
}

const TONE_COLOR: Record<NonNullable<RowAction["tone"]>, string> = {
  default: "var(--on-bg)",
  warn:    "var(--warn)",
  danger:  "var(--error)",
  success: "var(--success)",
};

export default function EmployeeRowActionsMenu({ actions }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  return (
    <div ref={ref} style={{ position: "relative", display: "inline-block" }}>
      <button
        onClick={() => setOpen(v => !v)}
        title="Actions"
        suppressHydrationWarning
        className="actbtn"
      >
        <i className="ti ti-dots-vertical text-[16px]" />
      </button>
      {open && (
        <div
          style={{
            position: "absolute", right: 0, top: "calc(100% + 4px)", zIndex: 20,
            background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: 10,
            boxShadow: "var(--shadow-md)", minWidth: 180, padding: 6,
          }}
        >
          {actions.map((a, i) => (
            <button
              key={i}
              onClick={() => { setOpen(false); a.onClick(); }}
              suppressHydrationWarning
              style={{
                display: "flex", alignItems: "center", gap: 8, width: "100%", textAlign: "left",
                padding: "8px 10px", borderRadius: 8, border: "none", background: "none",
                fontSize: 13, fontWeight: 500, color: TONE_COLOR[a.tone ?? "default"], cursor: "pointer",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--bg-low)")}
              onMouseLeave={e => (e.currentTarget.style.background = "none")}
            >
              <i className={`ti ${a.icon}`} style={{ fontSize: 15 }} />
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

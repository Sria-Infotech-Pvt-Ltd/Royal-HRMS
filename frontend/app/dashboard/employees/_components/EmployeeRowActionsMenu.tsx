"use client";

// The table row's "···" action menu — replaces three separate icon buttons
// with the single overflow-menu button the reference layout uses. Options
// shown depend on the same permissions/status checks the old inline buttons
// used, just collected into one dropdown.

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

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
  const btnRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  // The table's own scroll container (.tbl-wrap / .overflow-x-auto) clips
  // any absolutely-positioned descendant to its bounds — that's what cut
  // off the last couple of options (and the entire last row's menu). Portal
  // to <body> with fixed coordinates from the trigger button's own rect so
  // the menu escapes that clipping/scrolling ancestor entirely.
  const [coords, setCoords] = useState<{ top: number; right: number } | null>(null);

  useEffect(() => {
    if (!open || !btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setCoords({ top: rect.bottom + 4, right: window.innerWidth - rect.right });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      const target = e.target as Node;
      if (btnRef.current?.contains(target)) return;
      if (menuRef.current?.contains(target)) return;
      setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <button
        ref={btnRef}
        onClick={() => setOpen(v => !v)}
        title="Actions"
        suppressHydrationWarning
        className="actbtn"
      >
        <i className="ti ti-dots-vertical text-[16px]" />
      </button>
      {open && coords && createPortal(
        <div
          ref={menuRef}
          style={{
            position: "fixed", top: coords.top, right: coords.right, zIndex: 1000,
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
        </div>,
        document.body,
      )}
    </div>
  );
}

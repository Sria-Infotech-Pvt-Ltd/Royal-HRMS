"use client";

// A .card whose header toggles its body. The body stays mounted while
// collapsed (only hidden), so inputs, selections, chosen files and previews
// survive collapsing and reopening. Used by Monthly Leave Management.

import type { ReactNode } from "react";
import { useId } from "react";

export default function CollapsibleCard({ icon, title, open, onToggle, children }: {
  icon: string; title: string; open: boolean; onToggle: () => void; children: ReactNode;
}) {
  const bodyId = useId();
  return (
    <div className="card mb-24">
      <button
        type="button"
        className="card-header collapsible-card-header"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={bodyId}
        style={{
          width: "100%", background: "none", border: "none", cursor: "pointer", textAlign: "left", font: "inherit",
          borderBottom: open ? "1px solid var(--outline-v)" : "none",
        }}
      >
        <span className="card-title"><i className={`ti ${icon}`} /> {title}</span>
        <i
          className={`ti ${open ? "ti-chevron-down" : "ti-chevron-right"}`}
          aria-hidden="true"
          style={{ fontSize: 18, color: "var(--on-variant)" }}
        />
      </button>
      <div id={bodyId} hidden={!open}>{children}</div>
      <style>{`.collapsible-card-header:hover { background: var(--bg-low, #f6f8fb) !important; }`}</style>
    </div>
  );
}

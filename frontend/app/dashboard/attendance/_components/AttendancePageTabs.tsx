"use client";

// The tab bar of the Attendance & Time page. The active tab is brand purple with a purple indicator that slides to the new tab (instead
// of the theme's plain black underline), each tab has an icon, hovering tints it, and a count shows as a coloured badge. Arrow keys
// move between tabs, and on a narrow screen the bar scrolls sideways.

import { useEffect, useRef } from "react";
import { PALETTE, tint } from "./attendancePalette";

export interface AttendanceTabItem {
  id: string;
  label: string;
  icon: string;
  /** A count to show on the tab; hidden when 0 or missing. */
  badge?: number;
}

interface Props {
  tabs: AttendanceTabItem[];
  active: string;
  onSelect: (id: string) => void;
}

export default function AttendancePageTabs({ tabs, active, onSelect }: Props) {
  const buttons = useRef<Record<string, HTMLButtonElement | null>>({});
  const indicator = useRef<HTMLSpanElement | null>(null);

  // Slide the indicator under the active tab. Done directly on the element (not through state) so moving it never re-renders the page.
  useEffect(() => {
    const place = () => {
      const button = buttons.current[active];
      const bar = indicator.current;
      if (!button || !bar) return;
      bar.style.width = `${button.offsetWidth}px`;
      bar.style.transform = `translateX(${button.offsetLeft}px)`;
    };
    place();
    window.addEventListener("resize", place);
    return () => window.removeEventListener("resize", place);
  }, [active, tabs]);

  function onKeyDown(event: React.KeyboardEvent, index: number) {
    const last = tabs.length - 1;
    const target = event.key === "ArrowRight" ? (index === last ? 0 : index + 1) : event.key === "ArrowLeft" ? (index === 0 ? last : index - 1) : event.key === "Home" ? 0 : event.key === "End" ? last : -1;
    if (target < 0) return;
    event.preventDefault();
    onSelect(tabs[target].id);
    buttons.current[tabs[target].id]?.focus();
  }

  return (
    <div role="tablist" aria-label="Attendance sections" style={{ position: "relative", display: "flex", gap: 2, overflowX: "auto", borderBottom: "1px solid var(--outline-v)", marginBottom: 20, scrollbarWidth: "none" }}>
      {tabs.map((tab, index) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id} ref={element => { buttons.current[tab.id] = element; }} type="button" role="tab" aria-selected={selected} tabIndex={selected ? 0 : -1}
            onClick={() => onSelect(tab.id)} onKeyDown={event => onKeyDown(event, index)}
            onMouseEnter={event => { if (!selected) event.currentTarget.style.background = tint(PALETTE.brand, 0.06); }}
            onMouseLeave={event => { event.currentTarget.style.background = "transparent"; }}
            style={{
              display: "flex", alignItems: "center", gap: 8, padding: "13px 16px", border: 0, borderRadius: "10px 10px 0 0", background: "transparent", cursor: "pointer", whiteSpace: "nowrap", flexShrink: 0,
              fontSize: 13.5, fontWeight: selected ? 700 : 600, color: selected ? PALETTE.brand : "var(--on-variant)", transition: "color .18s ease, background .18s ease",
            }}
          >
            <i className={`ti ${tab.icon}`} aria-hidden="true" style={{ fontSize: 17, opacity: selected ? 1 : 0.75 }} />
            {tab.label}
            {!!tab.badge && (
              <span style={{ minWidth: 20, height: 20, padding: "0 6px", borderRadius: 10, display: "inline-grid", placeItems: "center", fontSize: 11, fontWeight: 800, background: PALETTE.absent, color: "#fff", fontVariantNumeric: "tabular-nums" }}>{tab.badge}</span>
            )}
          </button>
        );
      })}
      <span ref={indicator} aria-hidden="true" style={{ position: "absolute", left: 0, bottom: -1, height: 3, width: 0, borderRadius: 3, background: `linear-gradient(90deg, ${PALETTE.brand}, #A78BFA)`, transition: "transform .28s cubic-bezier(.4,0,.2,1), width .28s cubic-bezier(.4,0,.2,1)" }} />
    </div>
  );
}

"use client";

// The rows inside a top-bar dropdown: an icon tile, the page name, and its path. Shared by the section dropdowns,
// the profile menu and the narrow-screen menu.

import type { NavItem } from "@/lib/navConfig";

interface Props {
  items: NavItem[];
  activeNavId: string | undefined;
  onSelect: (item: NavItem) => void;
  /** Two columns, for a long list or a wide panel. */
  isTwoColumn?: boolean;
}

export default function NavMenuItems({ items, activeNavId, onSelect, isTwoColumn = false }: Props) {
  return (
    <div className={`grid gap-0.5 ${isTwoColumn ? "grid-cols-2" : "grid-cols-1"}`} role="none">
      {items.map(item => {
        const isActive = item.id === activeNavId;
        return (
          <button
            key={item.id}
            type="button"
            role="menuitem"
            aria-current={isActive ? "page" : undefined}
            className="flex items-center gap-3 rounded-xl px-3 py-2 text-left transition-colors hover:bg-[var(--bg)]"
            style={isActive ? { background: "color-mix(in srgb, var(--brand) 10%, var(--surface))" } : undefined}
            onClick={() => onSelect(item)}
          >
            <span
              className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[var(--muted)]"
              style={{ background: isActive ? "color-mix(in srgb, var(--brand) 14%, var(--surface))" : "var(--bg)" }}
            >
              <i className={`ti ${item.icon}`} style={{ fontSize: 16, color: isActive ? "var(--brand)" : undefined }} />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-[13px] font-semibold" style={{ color: isActive ? "var(--brand)" : "var(--ink)" }}>{item.label}</span>
              <span className="block truncate text-[11px] text-[var(--faint)]">{item.path}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

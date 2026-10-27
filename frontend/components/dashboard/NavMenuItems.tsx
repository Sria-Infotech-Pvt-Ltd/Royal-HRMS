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
          <button key={item.id} type="button" role="menuitem" aria-current={isActive ? "page" : undefined} className={`nm-item${isActive ? " on" : ""}`} onClick={() => onSelect(item)}>
            <span className="nm-tile"><i className={`ti ${item.icon}`} style={{ fontSize: 16 }} /></span>
            <span className="min-w-0">
              <span className="nm-label">{item.label}</span>
              <span className="nm-path">{item.path}</span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

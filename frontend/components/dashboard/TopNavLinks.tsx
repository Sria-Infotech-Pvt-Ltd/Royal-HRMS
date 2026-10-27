"use client";

// The top bar's page links: direct links plus one dropdown per section. Below 940px everything collapses into a
// single menu button. Which page is "current" underlines its section and highlights it inside the dropdown.

import { MENU_ATTRIBUTE, type OpenMenu } from "@/hooks/useOpenMenu";
import type { BarEntry, NavItem } from "@/lib/navConfig";
import NavMenuItems from "@/components/dashboard/NavMenuItems";

interface Props {
  bar: BarEntry[];
  activeNavId: string | undefined;
  menu: OpenMenu;
  onNavigate: (path: string) => void;
}

const MOBILE_MENU_KEY = "mobile-menu";
// With more pages than this a dropdown uses two columns instead of a tall list.
const TWO_COLUMN_THRESHOLD = 4;
const PANEL_CLASS = "absolute top-full z-50 mt-1 rounded-2xl border p-2";
// Colours and shadow as inline styles: the project's Tailwind (v2) does not resolve var() inside arbitrary values reliably.
const PANEL_STYLE = { background: "var(--surface)", borderColor: "var(--line)", boxShadow: "0 18px 50px rgba(24,20,48,.16)" } as const;

function PanelHeader({ title, count }: { title: string; count: number }) {
  return (
    <div className="nm-head">
      <span className="nm-title">{title}</span>
      <span className="nm-pill">{count} {count === 1 ? "page" : "pages"}</span>
    </div>
  );
}

export default function TopNavLinks({ bar, activeNavId, menu, onNavigate }: Props) {
  function select(item: NavItem) {
    menu.close();
    onNavigate(item.path);
  }

  return (
    <>
      <nav className="nav-desktop h-full min-w-0 flex-1 items-center gap-0.5" aria-label="Main">
        {bar.map(entry => {
          if (entry.kind === "link") {
            const { item } = entry;
            return (
              <button key={item.id} type="button" className={`navlink${item.id === activeNavId ? " on" : ""}`} onClick={() => select(item)} suppressHydrationWarning>
                {item.topNavLabel ?? item.label}
              </button>
            );
          }
          const isOpen = menu.openKey === entry.id;
          const isCurrent = entry.items.some(item => item.id === activeNavId);
          const isTwoColumn = entry.items.length > TWO_COLUMN_THRESHOLD;
          return (
            <div key={entry.id} className="relative flex h-full items-center" {...{ [MENU_ATTRIBUTE]: "" }} onMouseEnter={() => menu.switchTo(entry.id)}>
              <button
                type="button"
                className={`navlink${isCurrent ? " on" : ""}`}
                aria-haspopup="menu"
                aria-expanded={isOpen}
                onClick={() => menu.toggle(entry.id)}
                suppressHydrationWarning
              >
                {entry.title}
                <i className={`ti ${isOpen ? "ti-chevron-up" : "ti-chevron-down"}`} style={{ fontSize: 12 }} />
              </button>
              {isOpen && (
                <div className={`${PANEL_CLASS} left-0 ${isTwoColumn ? "w-[520px]" : "w-[300px]"}`} role="menu" aria-label={entry.title} style={PANEL_STYLE}>
                  <PanelHeader title={entry.title} count={entry.items.length} />
                  <NavMenuItems items={entry.items} activeNavId={activeNavId} onSelect={select} isTwoColumn={isTwoColumn} />
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div className="nav-mobile relative" {...{ [MENU_ATTRIBUTE]: "" }}>
        <button
          type="button"
          className="who-chip"
          aria-haspopup="menu"
          aria-expanded={menu.openKey === MOBILE_MENU_KEY}
          onClick={() => menu.toggle(MOBILE_MENU_KEY)}
          suppressHydrationWarning
        >
          <i className="ti ti-menu-2" style={{ fontSize: 16 }} /> Menu
        </button>
        {menu.openKey === MOBILE_MENU_KEY && (
          <div className={`${PANEL_CLASS} left-0 max-h-[70vh] w-[min(92vw,360px)] overflow-y-auto`} role="menu" aria-label="Menu" style={PANEL_STYLE}>
            {bar.map(entry => (
              <div key={entry.kind === "link" ? entry.item.id : entry.id} className="mb-1">
                {entry.kind === "menu" && <PanelHeader title={entry.title} count={entry.items.length} />}
                <NavMenuItems items={entry.kind === "link" ? [entry.item] : entry.items} activeNavId={activeNavId} onSelect={select} />
              </div>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

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
const PANEL_CLASS = "absolute top-full z-50 mt-1 rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-2 shadow-[0_18px_50px_rgba(24,20,48,.16)]";

function PanelHeader({ title, count }: { title: string; count: number }) {
  return (
    <div className="flex items-center justify-between px-3 pb-1.5 pt-1">
      <span className="text-[10.5px] font-bold uppercase tracking-[0.08em] text-[var(--muted)]">{title}</span>
      <span className="rounded-full bg-[var(--bg)] px-2 py-0.5 text-[10px] font-semibold text-[var(--muted)]">{count} {count === 1 ? "page" : "pages"}</span>
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
      <nav className="hidden h-full min-w-0 flex-1 items-center gap-0.5 min-[940px]:flex" aria-label="Main">
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
                <div className={`${PANEL_CLASS} left-0 ${isTwoColumn ? "w-[520px]" : "w-[300px]"}`} role="menu" aria-label={entry.title}>
                  <PanelHeader title={entry.title} count={entry.items.length} />
                  <NavMenuItems items={entry.items} activeNavId={activeNavId} onSelect={select} isTwoColumn={isTwoColumn} />
                </div>
              )}
            </div>
          );
        })}
      </nav>

      <div className="relative min-[940px]:hidden" {...{ [MENU_ATTRIBUTE]: "" }}>
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
          <div className={`${PANEL_CLASS} left-0 max-h-[70vh] w-[min(92vw,360px)] overflow-y-auto`} role="menu" aria-label="Menu">
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

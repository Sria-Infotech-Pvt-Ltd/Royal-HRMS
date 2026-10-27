"use client";

// The avatar button: opens the "My" pages (workspace, attendance, requests, payslips, assessments, referrals,
// profile) and Sign out.

import Avatar from "@/app/dashboard/employees/_components/Avatar";
import { MENU_ATTRIBUTE, type OpenMenu } from "@/hooks/useOpenMenu";
import type { NavItem } from "@/lib/navConfig";
import NavMenuItems from "@/components/dashboard/NavMenuItems";

const PROFILE_MENU_KEY = "profile";

interface Props {
  name: string;
  subtitle: string;
  photoUrl: string | null | undefined;
  items: NavItem[];
  activeNavId: string | undefined;
  menu: OpenMenu;
  onNavigate: (path: string) => void;
  onLogout: () => void;
}

function initials(name: string) {
  return name.split(" ").map(part => part[0]).join("").toUpperCase().slice(0, 2);
}

export default function ProfileMenu({ name, subtitle, photoUrl, items, activeNavId, menu, onNavigate, onLogout }: Props) {
  const isOpen = menu.openKey === PROFILE_MENU_KEY;

  return (
    <div className="relative" {...{ [MENU_ATTRIBUTE]: "" }} onMouseEnter={() => menu.switchTo(PROFILE_MENU_KEY)}>
      <button type="button" className="who-chip" aria-haspopup="menu" aria-expanded={isOpen} onClick={() => menu.toggle(PROFILE_MENU_KEY)} title="My account" suppressHydrationWarning>
        <Avatar text={initials(name)} size={24} photoUrl={photoUrl} />
        <span className="hidden whitespace-nowrap lg:inline">{name}</span>
        <i className={`ti ${isOpen ? "ti-chevron-up" : "ti-chevron-down"}`} style={{ fontSize: 12 }} />
      </button>
      {isOpen && (
        <div
          className="absolute right-0 top-full z-50 mt-2 w-[min(92vw,440px)] rounded-2xl border border-[var(--line)] bg-[var(--surface)] p-2 shadow-[0_18px_50px_rgba(24,20,48,.16)]"
          role="menu"
          aria-label="My account"
        >
          <div className="flex items-center gap-3 border-b border-[var(--line)] px-3 pb-3 pt-2">
            <Avatar text={initials(name)} size={36} photoUrl={photoUrl} />
            <div className="min-w-0">
              <div className="truncate text-[14px] font-bold text-[var(--ink)]">{name}</div>
              <div className="truncate text-[11.5px] text-[var(--muted)]">{subtitle}</div>
            </div>
          </div>
          {items.length > 0 && (
            <>
              <div className="px-3 pb-1 pt-3 text-[10.5px] font-bold uppercase tracking-[0.08em] text-[var(--muted)]">My</div>
              <NavMenuItems items={items} activeNavId={activeNavId} isTwoColumn onSelect={item => { menu.close(); onNavigate(item.path); }} />
            </>
          )}
          <button
            type="button"
            role="menuitem"
            className="mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-[13px] font-semibold text-[var(--crit,#c0392b)] transition-colors hover:bg-[var(--bg)]"
            onClick={() => { menu.close(); onLogout(); }}
          >
            <i className="ti ti-logout" style={{ fontSize: 16 }} /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

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
          className="absolute right-0 top-full z-50 mt-2 w-[min(92vw,500px)] rounded-2xl border p-2"
          style={{ background: "var(--surface)", borderColor: "var(--line)", boxShadow: "0 18px 50px rgba(24,20,48,.16)" }}
          role="menu"
          aria-label="My account"
        >
          <div className="nm-who">
            <Avatar text={initials(name)} size={36} photoUrl={photoUrl} />
            <div className="min-w-0">
              <div className="nm-who-name">{name}</div>
              <div className="nm-who-sub">{subtitle}</div>
            </div>
          </div>
          {items.length > 0 && (
            <>
              <div className="nm-section">My</div>
              <NavMenuItems items={items} activeNavId={activeNavId} isTwoColumn onSelect={item => { menu.close(); onNavigate(item.path); }} />
            </>
          )}
          <button
            type="button"
            role="menuitem"
            className="nm-signout"
            onClick={() => { menu.close(); onLogout(); }}
          >
            <i className="ti ti-logout" style={{ fontSize: 16 }} /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

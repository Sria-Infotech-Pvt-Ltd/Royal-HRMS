"use client";

import { useEffect, useRef } from "react";
import { useRouter, usePathname } from "next/navigation";
import type { SessionPayload } from "@/lib/session";
import { clearAuth } from "@/lib/auth";
import clientApi, { markIntentionalLogout } from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import {
  buildNav, isSection,
  type NavItem,
} from "@/lib/navConfig";
import { NotificationBell } from "@/components/NotificationBell";
import GlobalSearch from "@/components/dashboard/GlobalSearch";
import DarkModeToggle from "@/components/dashboard/DarkModeToggle";
import DashboardFooter from "@/components/dashboard/DashboardFooter";
import { useFetch } from "@/hooks/useFetch";
import Avatar from "@/app/dashboard/employees/_components/Avatar";
import { NAV_ICONS } from "@/components/dashboard/NavIcons";
import { PROFILE_PHOTO_UPDATED_EVENT } from "@/hooks/useProfilePhotoUpload";

function initials(name: string) {
  return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
}

export default function DashboardShell({
  session,
  children,
}: {
  session: SessionPayload;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();

  // Fetched independently of the server-rendered session cookie (name/role
  // only) so a photo change shows up immediately, without needing to log in
  // again for the cookie to refresh.
  const { data: myProfile, refetch: refetchMyProfile } = useFetch<{ profile_photo_url: string | null }>(API.employees.me);

  useEffect(() => {
    function onPhotoUpdated() { refetchMyProfile(); }
    window.addEventListener(PROFILE_PHOTO_UPDATED_EVENT, onPhotoUpdated);
    return () => window.removeEventListener(PROFILE_PHOTO_UPDATED_EVENT, onPhotoUpdated);
  }, [refetchMyProfile]);

  // The nav row scrolls horizontally with its scrollbar hidden — on a
  // narrow/zoomed viewport with ~28 items, the active page's own link could
  // sit off-screen with no indication where it went. Scrolls it into view
  // whenever the active page changes, instead of always landing back at
  // the (possibly unrelated) leftmost item.
  const activeLinkRef = useRef<HTMLButtonElement | null>(null);
  useEffect(() => {
    activeLinkRef.current?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [pathname]);


  const visibleNav = buildNav(session.permissions ?? []);
  // Top-nav layout (matching the AIRA mockup's single-row navlinks) has no
  // room for the sidebar's section subheadings — every entry renders as one
  // flat, horizontally scrollable strip, section labels dropped, order kept.
  const navItems = visibleNav.filter((entry): entry is NavItem => !isSection(entry));
  const canSearchEmployees = (session.permissions ?? []).includes("employees.view");

  // Nested paths (e.g. "/dashboard/settings/audit") match more than one nav
  // item's path prefix (both "audit" and its parent "settings"). Only the
  // item with the longest — i.e. most specific — matching path should light up.
  const activeNavId = navItems
    .filter(item => !item.comingSoon && (pathname === item.path || (item.path !== "/dashboard" && pathname.startsWith(item.path + "/"))))
    .sort((a, b) => b.path.length - a.path.length)[0]?.id;

  async function handleLogout() {
    markIntentionalLogout(); // suppress session:expired overlay for in-flight 401s
    try {
      // The httpOnly refresh token cookie is sent automatically via withCredentials.
      await clientApi.post(API.auth.logout, {});
    } catch { /* proceed */ }
    clearAuth();
    router.push("/login");
    router.refresh();
  }

  function navigate(path: string) {
    router.push(path);
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden">

      {/* ══════════════════ TOP NAV ══════════════════ */}
      <header className="topnav flex-wrap md:flex-nowrap">
        {/* Brand */}
        <div className="brandmark">
          <span className="sq">
            <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
              <path d="M12 3 21 8v8l-9 5-9-5V8z" />
            </svg>
          </span>
          <div className="brandcopy">
            <strong>AIRA</strong>
            <small>Artificial Intelligence Resources Assistance</small>
          </div>
        </div>

        {/* Horizontal scrollable nav links — hidden on the ESS shell, which
            has its own complete tab bar (Home/My profile/Attendance/...);
            showing both stacked one above the other is redundant. */}
        {!pathname.startsWith("/dashboard/ess") && (
        <nav
          className={[
            "navlinks",
            "flex",
            "order-3 md:order-none basis-full md:basis-auto",
          ].join(" ")}
        >
          {navItems.map(item => {
            const isActive = !item.comingSoon && item.id === activeNavId;
            if (item.comingSoon) {
              return (
                <div
                  key={item.id}
                  className="navlink"
                  style={{ cursor: "not-allowed", opacity: 0.6 }}
                  title={`${item.label} — Coming Soon`}
                >
                  {NAV_ICONS[item.id] ?? <i className={`ti ${item.icon}`} style={{ fontSize: 14 }} />}
                  {item.topNavLabel ?? item.label}
                  <span style={{ fontSize: 8.5, fontWeight: 700, background: "var(--line)", color: "var(--faint)", padding: "1px 5px", borderRadius: 99, letterSpacing: "0.04em" }}>
                    SOON
                  </span>
                </div>
              );
            }
            return (
              <button
                key={item.id}
                ref={isActive ? activeLinkRef : undefined}
                className={`navlink${isActive ? " on" : ""}`}
                onClick={() => navigate(item.path)}
                suppressHydrationWarning
              >
                {NAV_ICONS[item.id] ?? <i className={`ti ${item.icon}`} style={{ fontSize: 14 }} />}
                {item.topNavLabel ?? item.label}
                {item.badge && (
                  <span className="text-[9.5px] font-bold bg-[var(--brand)] text-white px-1.5 py-px rounded-full flex-shrink-0">
                    {item.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
        )}

        {/* Right-side utilities */}
        <div className="navright order-2 md:order-none">
          <GlobalSearch navItems={navItems} canSearchEmployees={canSearchEmployees} />
          <DarkModeToggle />
          <NotificationBell />
          <button
            className="who-chip"
            onClick={() => navigate(
              pathname.startsWith("/dashboard/ess") ? "/dashboard/ess?tab=profile" : "/dashboard/profile",
            )}
            title="My Profile"
            suppressHydrationWarning
          >
            <Avatar text={initials(session.name)} size={24} photoUrl={myProfile?.profile_photo_url} />
            <span className="whitespace-nowrap hidden lg:inline">{session.name}</span>
          </button>
          <button
            className="iconbtn"
            onClick={handleLogout}
            title="Sign out"
            suppressHydrationWarning
          >
            <i className="ti ti-logout text-[16px]" />
          </button>
        </div>
      </header>

      {/* ══════════════════ CONTENT ══════════════════ */}
      <main className="flex-1 overflow-y-auto bg-[var(--bg)]">
        <div className="px-6 py-4 md:px-10 md:py-6">
          {children}
        </div>
      </main>

      {/* Footer is a sibling of <main>, not a child inside its scroll area —
          it stays put at the bottom of the viewport (like the header stays
          put at the top) instead of scrolling away with page content. */}
      <DashboardFooter />
    </div>
  );
}

"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import type { SessionPayload } from "@/lib/session";
import { clearAuth } from "@/lib/auth";
import clientApi, { markIntentionalLogout } from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { buildNav, groupNav, isSection, type NavItem } from "@/lib/navConfig";
import { NotificationBell } from "@/components/NotificationBell";
import GlobalSearch from "@/components/dashboard/GlobalSearch";
import DarkModeToggle from "@/components/dashboard/DarkModeToggle";
import DashboardFooter from "@/components/dashboard/DashboardFooter";
import { useFetch } from "@/hooks/useFetch";
import TopNavLinks from "@/components/dashboard/TopNavLinks";
import ProfileMenu from "@/components/dashboard/ProfileMenu";
import { useOpenMenu } from "@/hooks/useOpenMenu";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { PROFILE_PHOTO_UPDATED_EVENT } from "@/hooks/useProfilePhotoUpload";

export default function DashboardShell({
  session,
  children,
}: {
  session: SessionPayload;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const isFitPage = pathname === "/dashboard/employees";

  // Fetched independently of the server-rendered session cookie (name/role
  // only) so a photo change shows up immediately, without needing to log in
  // again for the cookie to refresh. Cached (5 min TTL): DashboardShell wraps
  // every /dashboard page, so without `cache: true` this re-hit MyProfileView
  // (a serializer with several SerializerMethodFields, each its own query —
  // current placement, reporting manager, position title) on EVERY page
  // navigation, which is both slow and showed the initials fallback flash
  // back in on each nav while the photo re-fetched. The explicit
  // PROFILE_PHOTO_UPDATED_EVENT listener below still calls refetch(), which
  // always bypasses the cache — so an actual photo change still shows up
  // immediately, this just stops the redundant refetch on ordinary navigation.
  const { data: myProfile, refetch: refetchMyProfile } = useFetch<{ profile_photo_url: string | null }>(API.employees.me, { cache: true });

  useEffect(() => {
    function onPhotoUpdated() { refetchMyProfile(); }
    window.addEventListener(PROFILE_PHOTO_UPDATED_EVENT, onPhotoUpdated);
    return () => window.removeEventListener(PROFILE_PHOTO_UPDATED_EVENT, onPhotoUpdated);
  }, [refetchMyProfile]);

  const visibleNav = buildNav(session.permissions ?? []);
  // The bar groups the pages into dropdowns by section (groupNav); the flat list still feeds global search and
  // the active-page lookup below.
  const navGroups = groupNav(visibleNav);
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

  const isEssPage = pathname.startsWith("/dashboard/ess");
  const menu = useOpenMenu(pathname);
  const currentUser = useCurrentUser();
  // The workspace shell has its own profile tab; keep sending "My Profile" there from inside it.
  const navigateFromMenu = (path: string) => navigate(isEssPage && path === "/dashboard/profile" ? "/dashboard/ess?tab=profile" : path);

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
          </div>
        </div>

        {/* Page links grouped into dropdowns — hidden on the ESS shell, which has its own tab bar. */}
        {!isEssPage && <TopNavLinks bar={navGroups.bar} activeNavId={activeNavId} menu={menu} onNavigate={navigate} />}
        {isEssPage && <div className="flex-1" />}

        {/* Right-side utilities */}
        <div className="navright order-2 md:order-none">
          {/* Hidden on the ESS shell, as in the reference (.ess-mode .navsearch). */}
          {!isEssPage && (
            <GlobalSearch navItems={navItems} canSearchEmployees={canSearchEmployees} />
          )}
          <DarkModeToggle />
          <NotificationBell />
          <ProfileMenu
            name={session.name}
            subtitle={currentUser?.is_superuser ? "All permissions" : (session.designation || session.email)}
            photoUrl={myProfile?.profile_photo_url}
            items={navGroups.profile}
            activeNavId={activeNavId}
            menu={menu}
            onNavigate={navigateFromMenu}
            onLogout={handleLogout}
          />
        </div>
      </header>

      {/* ══════════════════ CONTENT ══════════════════ */}
      <main className={`min-h-0 flex-1 overflow-y-auto bg-[var(--bg)]${isFitPage ? " flex flex-col" : ""}`}>
        {/* The ESS shell uses the reference's .module-page spacing
            (16px 24px 40px) instead of the standard page gutter.
            The Employee Directory is a "fit" page (as in the reference): the wrapper fills <main>
            so the page header, KPIs and banner stay put and only the table body scrolls. */}
        <div className={`${pathname.startsWith("/dashboard/ess") ? "px-6 pt-4 pb-10" : isFitPage ? "px-4 py-3 md:px-5 md:pt-2 md:pb-2.5" : "px-6 py-4 md:px-10 md:py-6"}${isFitPage ? " flex-1 min-h-0 flex flex-col w-full max-w-[1400px] mx-auto" : ""}`}>
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

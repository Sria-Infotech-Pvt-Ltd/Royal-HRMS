"use client";

import { usePathname, useRouter } from "next/navigation";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";

// "Settings" groups three previously-separate top-level nav items (Audit
// Log, Email Settings, My Account) under one sidebar entry, landing on
// /platform-admin/settings — a small hub page linking to each. matchPaths
// keeps the sidebar highlighted as "Settings" while on any of their actual
// (unchanged) URLs, since they weren't moved, just no longer linked directly.
const NAV_ITEMS = [
  { href: "/platform-admin",           icon: "ti-layout-dashboard", label: "Dashboard" },
  { href: "/platform-admin/companies", icon: "ti-building",         label: "Companies" },
  { href: "/platform-admin/admins",    icon: "ti-users",            label: "Platform Admins" },
  {
    href: "/platform-admin/settings", icon: "ti-settings", label: "Settings",
    matchPaths: ["/platform-admin/settings", "/platform-admin/audit-log", "/platform-admin/email-settings", "/platform-admin/account"],
  },
];

export default function PlatformAdminLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  // The login and forgot-password flows are unauthenticated entry points —
  // they get the plain page with no sidebar/topbar chrome around them.
  const isAuthPage = pathname === "/platform-admin/login" || pathname.startsWith("/platform-admin/forgot-password");
  if (isAuthPage) return <>{children}</>;

  async function handleLogout() {
    try {
      await platformAdminApi.post(API.platformAdmin.logout);
    } finally {
      router.push("/platform-admin/login");
    }
  }

  return (
    <div style={{ display: "flex", minHeight: "100vh" }}>
      <aside
        style={{
          width: 240, flexShrink: 0, background: "var(--surface)", borderRight: "1px solid var(--outline-v)",
          display: "flex", flexDirection: "column", position: "sticky", top: 0, height: "100vh",
        }}
      >
        <div style={{ padding: "20px 20px 16px" }}>
          {/* Same sizing convention as the tenant dashboard sidebar's own logo
              (see components/dashboard/DashboardShell.tsx / .sidebar-logo-expanded
              in globals.css) — contained within a max-height, not squished into
              a square, since the real logo is a wordmark, not an icon glyph. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.png" alt="Royal HRMS" className="sidebar-logo-expanded" style={{ maxHeight: 36 }} />
          <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>Platform Admin</div>
        </div>

        <nav style={{ flex: 1, padding: "8px 12px", display: "flex", flexDirection: "column", gap: 2 }}>
          {NAV_ITEMS.map(item => {
            const active = item.matchPaths
              ? item.matchPaths.some(p => pathname.startsWith(p))
              : item.href === "/platform-admin"
                ? pathname === "/platform-admin"
                : pathname.startsWith(item.href);
            return (
              <a
                key={item.href}
                href={item.href}
                style={{
                  display: "flex", alignItems: "center", gap: 10, padding: "9px 12px", borderRadius: 8,
                  fontSize: 13.5, fontWeight: active ? 600 : 500, textDecoration: "none",
                  color: active ? "var(--primary)" : "var(--on-bg)",
                  background: active ? "rgba(30, 78, 140, 0.1)" : "transparent",
                }}
              >
                <i className={`ti ${item.icon}`} style={{ fontSize: 17, width: 18 }} />
                {item.label}
              </a>
            );
          })}
        </nav>

        <div style={{ padding: 12, borderTop: "1px solid var(--outline-v)" }}>
          <button
            type="button"
            className="btn btn-ghost"
            style={{ width: "100%", justifyContent: "flex-start", gap: 10 }}
            onClick={handleLogout}
            suppressHydrationWarning
          >
            <i className="ti ti-logout" /> Sign out
          </button>
        </div>
      </aside>

      <main style={{ flex: 1, minWidth: 0 }}>{children}</main>
    </div>
  );
}

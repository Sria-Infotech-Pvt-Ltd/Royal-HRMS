"use client";

import { useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import type { SessionPayload } from "@/lib/session";
import { clearAuth } from "@/lib/auth";
import clientApi, { markIntentionalLogout } from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import {
  buildNav, isSection,
  type NavItem,
} from "@/lib/navConfig";

function initials(name: string) {
  return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
}

const PAGE_TITLES: Record<string, string> = {
  "/dashboard":                          "Dashboard",
  "/dashboard/settings":                 "Settings",
  "/dashboard/profile":                  "My Profile",
  "/dashboard/settings/permissions":     "Roles & Permissions",
  "/dashboard/employees":                "Employees",
  "/dashboard/employees/new":            "Add New Employee",
  "/dashboard/attendance":               "Attendance & Time",
  "/dashboard/payroll":                  "Payroll Management",
  "/dashboard/leave":                    "Leave Management",
  "/dashboard/expenses":                 "Expense Claims",
  "/dashboard/documents":                "Document Center",
  "/dashboard/separation":               "Separation & FnF",
  "/dashboard/interview-list":           "Interview List",
  "/dashboard/candidate-review":         "Candidate Review & Onboarding",
  "/dashboard/email-logs":               "Email Logs",
  "/dashboard/org-chart":               "Organisation Chart",
  "/dashboard/announcements":            "Announcements",
  "/dashboard/my-payslip":              "My Payslips",
  "/dashboard/my-requests":             "My Requests",
  "/dashboard/approvals":               "Team Approvals",
  "/dashboard/branches":                "Branch Management",
};


export default function DashboardShell({
  session,
  children,
}: {
  session: SessionPayload;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();

  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [searchVal, setSearchVal] = useState("");

  const pageTitle = PAGE_TITLES[pathname]
    ?? (pathname.startsWith("/dashboard/employees/") ? "Employee Profile" : "Royal HRMS");
  const visibleNav = buildNav(session.permissions ?? []);

  function toggleTheme() {
    document.body.classList.toggle("dark-mode");
    setDarkMode(v => !v);
  }

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
    setMobileOpen(false);
  }

  return (
    <div className="flex h-screen overflow-hidden">

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-[150] md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* ══════════════════ SIDEBAR ══════════════════ */}
      <aside
        className={[
          "bg-white flex flex-col overflow-hidden z-[200] h-screen",
          "border-r border-[var(--outline-v)]",
          // Mobile: fixed overlay drawer, slides in/out via transform
          "fixed left-0 top-0 w-[220px]",
          "transition-transform duration-200",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
          // Desktop: part of the normal flow, width-transitions
          "md:relative md:translate-x-0 md:flex-shrink-0 md:transition-[width]",
          collapsed ? "md:w-14" : "md:w-[220px]",
        ].join(" ")}
      >
        {/* Sidebar header */}
        <div className="h-14 px-3 flex items-center gap-2.5 border-b border-[var(--outline-v)] flex-shrink-0">
          <div className="flex items-center gap-2 flex-1 overflow-hidden">
            {collapsed ? (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src="/logo.png"
                alt="Royal HRMS"
                style={{
                  width: 36, height: 36, flexShrink: 0,
                  objectFit: "cover", objectPosition: "45% center",
                  borderRadius: 6,
                }}
              />
            ) : (
              /* eslint-disable-next-line @next/next/no-img-element */
              <img
                src="/logo.png"
                alt="Royal HRMS"
                style={{
                  height: 44, width: "auto", maxWidth: 170,
                  objectFit: "contain", objectPosition: "left center",
                  flexShrink: 0,
                }}
              />
            )}
          </div>
          <button
            className="w-7 h-7 rounded-[6px] flex items-center justify-center bg-transparent text-[var(--outline)] cursor-pointer hover:bg-[var(--bg-mid)] flex-shrink-0 text-sm border-none"
            onClick={() => setCollapsed(v => !v)}
            title={collapsed ? "Expand" : "Collapse"}
            suppressHydrationWarning
          >
            <i className={`ti ${collapsed ? "ti-layout-sidebar-right" : "ti-layout-sidebar-left-collapse"}`} />
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-2">
          {visibleNav.map((entry, idx) => {
            if (isSection(entry)) {
              return (
                <div key={`section-${idx}`} className="px-2 mt-3 mb-1">
                  {!collapsed && (
                    <span className="text-[10px] font-semibold text-[var(--outline)] tracking-[0.06em] uppercase px-2">
                      {entry.section}
                    </span>
                  )}
                  {collapsed && <div className="border-t border-[var(--outline-v)] mx-1" />}
                </div>
              );
            }
            const item = entry as NavItem;
            const isActive = pathname === item.path || (item.path !== "/dashboard" && pathname.startsWith(item.path + "/"));
            return (
              <div key={item.id} className="px-2 mb-px">
                <button
                  className={[
                    "flex items-center gap-2.5 px-2 py-2 rounded-lg cursor-pointer w-full text-left border-none font-[inherit] text-[13px] whitespace-nowrap transition-all duration-[0.12s]",
                    isActive
                      ? "font-medium text-[var(--primary)] bg-[rgba(30,78,140,0.10)]"
                      : "text-[var(--on-variant)] bg-transparent hover:bg-[var(--bg-low)] hover:text-[var(--on-bg)]",
                  ].join(" ")}
                  onClick={() => navigate(item.path)}
                  title={collapsed ? item.label : undefined}
                  suppressHydrationWarning
                >
                  <i className={`ti ${item.icon} text-[18px] flex-shrink-0`} />
                  {!collapsed && (
                    <>
                      <span className="overflow-hidden text-ellipsis whitespace-nowrap flex-1">{item.label}</span>
                      {item.badge && (
                        <span className="text-[10px] font-semibold bg-[var(--primary)] text-white px-1.5 py-px rounded-full flex-shrink-0">
                          {item.badge}
                        </span>
                      )}
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </nav>

        {/* Footer — user card */}
        <div className="border-t border-[var(--outline-v)] p-2 flex-shrink-0">
          <button
            className="flex items-center gap-2 p-2 rounded-lg cursor-pointer w-full bg-transparent border-none font-[inherit] text-left hover:bg-[var(--bg-low)] transition-all duration-[0.12s]"
            onClick={() => navigate("/dashboard/profile")}
            title="My Profile"
            suppressHydrationWarning
          >
            <div className="w-[30px] h-[30px] rounded-full flex items-center justify-center text-xs font-semibold flex-shrink-0 text-white bg-[var(--primary)]">
              {initials(session.name)}
            </div>
            {!collapsed && (
              <div className="flex-1 overflow-hidden text-left">
                <div className="text-xs font-medium whitespace-nowrap overflow-hidden text-ellipsis text-[var(--on-bg)]">
                  {session.name}
                </div>
                <div className="text-[10px] text-[var(--on-variant)]">{session.role}</div>
              </div>
            )}
          </button>
        </div>
      </aside>

      {/* ══════════════════ MAIN AREA ══════════════════ */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">

        {/* Top header */}
        <header className="h-14 px-3 md:px-6 flex items-center gap-2 md:gap-4 bg-white border-b border-[var(--outline-v)] flex-shrink-0">

          {/* Mobile menu toggle */}
          <button
            className="md:hidden flex items-center justify-center w-8 h-8 bg-transparent border-none text-[var(--on-variant)] text-xl cursor-pointer rounded-lg hover:bg-[var(--bg-mid)]"
            onClick={() => setMobileOpen(v => !v)}
            suppressHydrationWarning
          >
            <i className="ti ti-menu-2" />
          </button>

          {/* Page title */}
          <h1 className="text-base font-semibold text-[var(--on-bg)] flex-1">{pageTitle}</h1>

          <div className="flex items-center gap-2">
            {/* Search bar */}
            <div className="hidden md:flex items-center gap-2 px-3 py-2 border-[1.5px] border-[var(--outline-v)] rounded-lg bg-[var(--bg)] min-w-[240px]">
              <i className="ti ti-search text-base text-[var(--outline)]" />
              <input
                type="text"
                placeholder="Search anything..."
                className="border-none bg-transparent text-[var(--on-bg)] text-[13px] flex-1 outline-none"
                value={searchVal}
                onChange={e => setSearchVal(e.target.value)}
                suppressHydrationWarning
              />
            </div>

            {/* Theme toggle */}
            <button
              className="w-[34px] h-[34px] rounded-lg flex items-center justify-center bg-transparent text-[var(--outline)] border-none cursor-pointer hover:bg-[var(--bg-mid)]"
              onClick={toggleTheme}
              title="Toggle theme"
              suppressHydrationWarning
            >
              <i className={`ti ${darkMode ? "ti-sun" : "ti-moon"} text-[18px]`} />
            </button>

            {/* Notifications */}
            <button
              className="relative w-[34px] h-[34px] rounded-lg flex items-center justify-center bg-transparent text-[var(--outline)] border-none cursor-pointer hover:bg-[var(--bg-mid)]"
              title="Notifications"
              suppressHydrationWarning
            >
              <i className="ti ti-bell text-[18px]" />
              <span className="absolute top-[6px] right-[6px] w-[7px] h-[7px] rounded-full border-[1.5px] border-white bg-[var(--error)]" />
            </button>

            {/* Logout */}
            <button
              className="w-[34px] h-[34px] rounded-lg flex items-center justify-center bg-transparent text-[var(--outline)] border-none cursor-pointer hover:bg-[var(--bg-mid)]"
              onClick={handleLogout}
              title="Sign out"
              suppressHydrationWarning
            >
              <i className="ti ti-logout text-[18px]" />
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6 bg-[var(--bg)]">
          {children}
        </main>
      </div>
    </div>
  );
}

// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: { access_seats: 5, audit_events_30d: 102 }, loading: false, error: null, refetch: vi.fn() }) }));
vi.mock("@/lib/api/endpoints", () => ({ API: { dashboard: { settingsOverview: "/dashboard/settings-overview/" } } }));
vi.mock("@/components/dashboard/ModuleOverviewKit", () => ({ KpiTile: ({ label, value }: { label: string; value: number | string }) => <div data-testid="kpi">{label}:{value}</div> }));

import { SETTINGS_ITEMS, countByCategory, filterSettings } from "./_components/settingsItems";
import SettingsPage from "./page";

afterEach(() => { cleanup(); window.localStorage.clear(); });

describe("settings list", () => {
  it("keeps all fifteen settings and the pages they open", () => {
    expect(SETTINGS_ITEMS).toHaveLength(15);
    expect(SETTINGS_ITEMS.find(item => item.id === "leave-policy")?.route).toBe("/dashboard/settings/leave-policy");
    expect(SETTINGS_ITEMS.find(item => item.id === "access")?.route).toBe("/dashboard/settings/access");
    expect(new Set(SETTINGS_ITEMS.map(item => item.route)).size).toBe(15);
  });
  it("finds by every typed word in the name or the description, within a category", () => {
    expect(filterSettings(SETTINGS_ITEMS, "email", "all").map(item => item.id).sort()).toEqual(["email-templates", "notifications", "smtp"]);
    expect(filterSettings(SETTINGS_ITEMS, "email", "comm")).toHaveLength(3);
    expect(filterSettings(SETTINGS_ITEMS, "email", "system")).toHaveLength(0);
    expect(filterSettings(SETTINGS_ITEMS, "leave types", "all").map(item => item.id)).toEqual(["leave-policy"]);
  });
  it("counts what is left in each category after a search", () => {
    expect(countByCategory(SETTINGS_ITEMS, "")).toEqual({ all: 15, company: 3, modules: 8, comm: 3, system: 1 });
    expect(countByCategory(SETTINGS_ITEMS, "smtp").all).toBe(1);
  });
});

describe("the Settings page", () => {
  it("shows the four numbers and every setting, grouped under a heading for each category", () => {
    render(<SettingsPage />);
    expect(screen.getAllByTestId("kpi").map(node => node.textContent)).toEqual(["CONFIGURED:15", "ACCESS SEATS:5", "AUTOMATIONS:—", "AUDIT EVENTS:102"]);
    for (const heading of ["Company", "Modules", "Communication", "System"]) expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
    expect(screen.getAllByRole("link")).toHaveLength(15);
    expect(within(screen.getByRole("region", { name: "Modules" })).getAllByRole("link")).toHaveLength(8);
  });

  it("makes each card a real link to its page", () => {
    render(<SettingsPage />);
    expect(screen.getByRole("link", { name: /Leave Policy/ }).getAttribute("href")).toBe("/dashboard/settings/leave-policy");
  });

  it("keeps the audit log button", () => {
    render(<SettingsPage />);
    fireEvent.click(screen.getByRole("button", { name: "View audit log" }));
    expect(push).toHaveBeenCalledWith("/dashboard/settings/audit");
  });


  it("shows one plain grid, without headings, when a single category is picked", () => {
    render(<SettingsPage />);
    const pill = screen.getByRole("button", { name: /^Modules/ });
    fireEvent.click(pill);
    expect(pill.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getAllByRole("link")).toHaveLength(8);
    expect(screen.queryByRole("heading", { name: "Modules" })).toBeNull();
  });

});

describe("no search box", () => {
  it("shows the categories and the layout switch, and no search field", () => {
    render(<SettingsPage />);
    expect(screen.queryByRole("searchbox")).toBeNull();
    expect(screen.queryByLabelText("Search settings")).toBeNull();
    expect(screen.getByRole("group", { name: "Setting categories" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "Layout" })).toBeTruthy();
  });
});

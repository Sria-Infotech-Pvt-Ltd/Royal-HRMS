// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));
vi.mock("next/link", () => ({ default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => <a href={href} {...rest}>{children}</a> }));
vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: { access_seats: 5, audit_events_30d: 102 }, loading: false, error: null, refetch: vi.fn() }) }));
vi.mock("@/lib/api/endpoints", () => ({ API: { dashboard: { settingsOverview: "/dashboard/settings-overview/" } } }));

import SettingsPage from "./page";

beforeEach(() => { window.localStorage.clear(); push.mockReset(); });
afterEach(cleanup);

const grid = (name: string) => screen.getByRole("region", { name }).querySelector(".settings-cards-grid") as HTMLElement;

describe("pins, recent, layout and shortcuts on the Settings page", () => {
  it("pins a setting to a Pinned block at the top, and remembers it after a reload", () => {
    render(<SettingsPage />);
    expect(screen.queryByRole("region", { name: "Pinned" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Pin Payroll Rules" }));
    expect(within(screen.getByRole("region", { name: "Pinned" })).getByRole("link", { name: /Payroll Rules/ })).toBeTruthy();
    cleanup();
    render(<SettingsPage />);
    const pinned = within(screen.getByRole("region", { name: "Pinned" }));
    expect(pinned.getByRole("link", { name: /Payroll Rules/ })).toBeTruthy();
    fireEvent.click(pinned.getByRole("button", { name: "Unpin Payroll Rules" }));
    expect(screen.queryByRole("region", { name: "Pinned" })).toBeNull();
  });

  it("has no Recently opened block", () => {
    render(<SettingsPage />);
    fireEvent.click(screen.getAllByRole("link", { name: /Leave Policy/ })[0]);
    expect(screen.queryByRole("region", { name: "Recently opened" })).toBeNull();
  });

  it("hides Pinned inside one category", () => {
    render(<SettingsPage />);
    fireEvent.click(screen.getByRole("button", { name: "Pin Payroll Rules" }));
    fireEvent.click(screen.getByRole("button", { name: /^Modules/ }));
    expect(screen.queryByRole("region", { name: "Pinned" })).toBeNull();
  });

  it("switches between grid and list and remembers the choice", () => {
    render(<SettingsPage />);
    expect(grid("Company").style.gridAutoRows).toBe("112px");
    fireEvent.click(screen.getByRole("button", { name: "List view" }));
    expect(grid("Company").style.gridAutoRows).toBe("68px");
    expect(screen.getByRole("button", { name: "List view" }).getAttribute("aria-pressed")).toBe("true");
    cleanup();
    render(<SettingsPage />);
    expect(grid("Company").style.gridAutoRows).toBe("68px");
  });

  it("gives every card in a view the same height, whatever its text", () => {
    render(<SettingsPage />);
    const heights = Array.from(document.querySelectorAll(".settings-cards-grid")).map(each => (each as HTMLElement).style.gridAutoRows);
    expect(new Set(heights).size).toBe(1);
    for (const link of screen.getAllByRole("link")) expect((link as HTMLElement).style.height).toBe("100%");
  });

  it("starts fresh when the saved choices are damaged", () => {
    window.localStorage.setItem("aira_settings_prefs", "{not json");
    render(<SettingsPage />);
    expect(screen.queryByRole("region", { name: "Pinned" })).toBeNull();
    expect(grid("Company").style.gridAutoRows).toBe("112px");
  });
});

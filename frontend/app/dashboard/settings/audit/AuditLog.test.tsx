// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

const mock = vi.hoisted(() => ({ rows: [] as Array<Record<string, unknown>>, loading: false, error: null as string | null, totalPages: 1, urls: [] as string[] }));
const push = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({ useRouter: () => ({ push }), useSearchParams: () => new URLSearchParams("module=branch") }));
vi.mock("@/lib/api/endpoints", () => ({ API: { settings: { audit: "/settings/audit/" } } }));
vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string) => {
    mock.urls.push(url);
    return mock.loading
      ? { data: null, loading: true, error: null, refetch: vi.fn() }
      : { data: { count: mock.rows.length, page: 1, page_size: 20, total_pages: mock.totalPages, results: mock.rows }, loading: false, error: mock.error, refetch: vi.fn() };
  },
}));
vi.mock("@/components/shared/DateInput", () => ({ default: ({ value }: { value: string }) => <input aria-label="Date" readOnly value={value} /> }));
vi.mock("@/lib/formatDate", () => ({ formatDate: (value: Date) => `D${value.getDate()}` }));

import { actionStyle, matchingRange, rangeDates, relativeTime } from "./_components/auditView";
import AuditLogPage from "./page";

const LOG = (overrides: Record<string, unknown> = {}) => ({
  id: 1, actor_name: "Sria Info", actor_email: "sria@example.com", actor_role: "HR Admin", action: "branch_created", description: "Created Mulugu", module: "branch",
  object_id: "B-7", ip_address: "::1", created_at: new Date(Date.now() - 5 * 60_000).toISOString(), ...overrides,
});

beforeEach(() => {
  mock.rows = [LOG(), LOG({ id: 2, action: "login", module: "accounts", actor_name: "Durga Gadde", created_at: "2026-01-02T10:00:00Z", description: undefined })];
  mock.loading = false; mock.error = null; mock.totalPages = 1; mock.urls = []; push.mockReset();
});
afterEach(cleanup);

describe("audit helpers", () => {
  it("colours what happened: created green, deleted red, updated orange, sign-in blue", () => {
    expect(actionStyle("branch_created").colour).toBe("#16A34A");
    expect(actionStyle("employee_deleted").colour).toBe("#DC2626");
    expect(actionStyle("branch_updated").colour).toBe("#EA580C");
    expect(actionStyle("login").colour).toBe("#2563EB");
    expect(actionStyle("something_else").colour).toBe("#64748B");
  });
  it("says how long ago, and gives up after a week", () => {
    const now = new Date("2026-11-18T12:00:00Z");
    expect(relativeTime("2026-11-18T11:59:50Z", now)).toBe("just now");
    expect(relativeTime("2026-11-18T11:30:00Z", now)).toBe("30 min ago");
    expect(relativeTime("2026-11-18T09:00:00Z", now)).toBe("3 h ago");
    expect(relativeTime("2026-11-16T12:00:00Z", now)).toBe("2 d ago");
    expect(relativeTime("2026-11-01T12:00:00Z", now)).toBeNull();
  });
  it("works out quick ranges from the viewer's own day and finds which one the dates match", () => {
    expect(rangeDates("30d", "2026-11-18")).toEqual({ from: "2026-10-19", to: "2026-11-18" });
    expect(rangeDates("today", "2026-11-18")).toEqual({ from: "2026-11-18", to: "2026-11-18" });
    expect(matchingRange("2026-11-11", "2026-11-18", "2026-11-18")).toBe("7d");
    expect(matchingRange("2026-11-01", "2026-11-18", "2026-11-18")).toBeNull();
  });
});

describe("the Audit Log page", () => {
  it("opens on the module in the link, for the last 30 days, 20 to a page", () => {
    render(<AuditLogPage />);
    expect(mock.urls[0]).toContain("module=branch");
    expect(mock.urls[0]).toContain("page_size=20");
    expect(mock.urls[0]).toMatch(/date_from=\d{4}-\d{2}-\d{2}/);
    expect(within(screen.getByRole("group", { name: "Module" })).getByRole("button", { name: /Company Code/ }).getAttribute("aria-pressed")).toBe("true");
    expect(within(screen.getByRole("group", { name: "Quick range" })).getByRole("button", { name: "30 days" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("shows who did what with an avatar, how long ago, and coloured pills", () => {
    render(<AuditLogPage />);
    const table = within(screen.getByRole("region", { name: "Activity" }));
    expect(table.getByText("2 entries")).toBeTruthy();
    expect(table.getByText("5 min ago")).toBeTruthy();
    expect(table.getByText("SI")).toBeTruthy();
    expect(table.getByText("branch created").style.color).toMatch(/22,\s*163,\s*74|#16A34A/i);
    expect(table.getByText("login").style.color).toMatch(/37,\s*99,\s*235|#2563EB/i);
  });

  it("opens a row to show the details, and closes it again", () => {
    render(<AuditLogPage />);
    const table = within(screen.getByRole("region", { name: "Activity" }));
    expect(table.queryByText("Created Mulugu")).toBeNull();
    fireEvent.click(table.getAllByRole("button", { name: "Show details" })[0]);
    expect(table.getByText("Created Mulugu")).toBeTruthy();
    expect(table.getByText("B-7")).toBeTruthy();
    expect(table.getByText("HR Admin")).toBeTruthy();
    fireEvent.click(table.getByRole("button", { name: "Hide details" }));
    expect(table.queryByText("Created Mulugu")).toBeNull();
  });

  it("filters by module, going back to page one", () => {
    render(<AuditLogPage />);
    fireEvent.click(within(screen.getByRole("group", { name: "Module" })).getByRole("button", { name: /Accounts/ }));
    expect(mock.urls[mock.urls.length - 1]).toContain("module=accounts");
    expect(mock.urls[mock.urls.length - 1]).toContain("page=1");
    fireEvent.click(within(screen.getByRole("group", { name: "Module" })).getByRole("button", { name: /All modules/ }));
    expect(mock.urls[mock.urls.length - 1]).not.toContain("module=");
  });

  it("applies a quick range, and searches the actor only when asked", () => {
    render(<AuditLogPage />);
    fireEvent.click(within(screen.getByRole("group", { name: "Quick range" })).getByRole("button", { name: "Today" }));
    const url = mock.urls[mock.urls.length - 1];
    expect(new URLSearchParams(url.split("?")[1]).get("date_from")).toBe(new URLSearchParams(url.split("?")[1]).get("date_to"));
    fireEvent.change(screen.getByLabelText("Actor"), { target: { value: "durga" } });
    expect(mock.urls[mock.urls.length - 1]).not.toContain("search=");
    fireEvent.click(screen.getByRole("button", { name: /^Search/ }));
    expect(mock.urls[mock.urls.length - 1]).toContain("search=durga");
  });

  it("shows Clear only when something was changed, and Clear puts the defaults back", () => {
    render(<AuditLogPage />);
    fireEvent.click(screen.getByRole("button", { name: /Clear/ }));      // module=branch from the link counts as a change
    expect(mock.urls[mock.urls.length - 1]).not.toContain("module=");
    expect(screen.queryByRole("button", { name: /Clear/ })).toBeNull();
  });

  it("shows placeholders while loading, an empty state, an error, and pages", () => {
    mock.loading = true;
    render(<AuditLogPage />);
    expect(screen.getAllByLabelText("Loading")).toHaveLength(5);
    cleanup();
    mock.loading = false; mock.rows = [];
    render(<AuditLogPage />);
    expect(screen.getByText("No audit entries found")).toBeTruthy();
    cleanup();
    mock.error = "Could not load"; mock.rows = [LOG()];
    render(<AuditLogPage />);
    expect(screen.getByRole("alert").textContent).toContain("Could not load");
    cleanup();
    mock.error = null; mock.totalPages = 3;
    render(<AuditLogPage />);
    fireEvent.click(screen.getByRole("button", { name: /Next/ }));
    expect(mock.urls[mock.urls.length - 1]).toContain("page=2");
  });

  it("goes back to Settings", () => {
    render(<AuditLogPage />);
    fireEvent.click(screen.getByRole("button", { name: /Back/ }));
    expect(push).toHaveBeenCalledWith("/dashboard/settings");
  });
});

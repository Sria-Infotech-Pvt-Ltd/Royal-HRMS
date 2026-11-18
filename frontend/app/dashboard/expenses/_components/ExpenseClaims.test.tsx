// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";

const mock = vi.hoisted(() => ({
  claims: [] as Array<Record<string, unknown>>, stats: null as Record<string, number> | null, loading: false, error: null as string | null,
}));
const refetch = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/useFetch", () => ({
  useFetch: (url: string) => url.includes("stats")
    ? { data: mock.stats, loading: false, error: null, refetch }
    : { data: mock.loading ? null : { results: mock.claims }, loading: mock.loading, error: mock.error, refetch },
}));
vi.mock("@/lib/api/endpoints", () => ({ API: { expenses: { list: "/expenses/", stats: "/expenses/stats/" } } }));
vi.mock("@/lib/formatDate", () => ({ formatDate: (iso: string) => `D(${iso})` }));
vi.mock("./ExpenseFormModal", () => ({ default: () => <div>new expense form</div> }));
vi.mock("./ExpenseDetailModal", () => ({ default: ({ initialData }: { initialData: { title: string } }) => <div>detail of {initialData.title}</div> }));

import { formatShortAmount, statusShares } from "./expenseView";
import ExpenseClaims from "./ExpenseClaims";

const CLAIM = (overrides: Record<string, unknown> = {}) => ({
  expense_number: 1, expense_ref: "EXP001", title: "Cab to client", category: "travel", amount: "1250", expense_date: "2026-11-10", description: "", status: "pending",
  receipts: [{ id: "r1", url: null }], employee_name: "Asha Rao", branch_name: "Mulugu", created_at: "2026-11-10", ...overrides,
});
const STATS = { total: 4, pending: 2, approved: 1, rejected: 1, total_amount: 150000, pending_amount: 3000, approved_amount: 1250 };

beforeEach(() => { mock.claims = []; mock.stats = null; mock.loading = false; mock.error = null; refetch.mockReset(); });
afterEach(cleanup);

const list = () => within(screen.getByRole("region", { name: "Recent expense claims" }));

describe("expense helpers", () => {
  it("writes money short for the cards", () => {
    expect(formatShortAmount(150000)).toBe("₹1.5L");
    expect(formatShortAmount("2500")).toBe("₹2.5K");
    expect(formatShortAmount(450)).toBe("₹450");
    expect(formatShortAmount("oops")).toBe("₹0");
  });
  it("splits the claims into whole percentages that always add to 100", () => {
    expect(statusShares(2, 1, 1)).toEqual({ pending: 50, approved: 25, rejected: 25 });
    const thirds = statusShares(1, 1, 1);
    expect(thirds.pending + thirds.approved + thirds.rejected).toBe(100);
    expect(statusShares(0, 0, 0)).toEqual({ pending: 0, approved: 0, rejected: 0 });
  });
});

describe("the Expenses page", () => {
  it("shows the five numbers with the money beside them, and the share bar", () => {
    mock.stats = STATS; mock.claims = [CLAIM()];
    render(<ExpenseClaims />);
    expect(screen.getByText("₹1.5L")).toBeTruthy();
    expect(screen.getByText("₹3,000 waiting")).toBeTruthy();
    expect(screen.getByText("₹1,250 approved")).toBeTruthy();
    expect(screen.getByRole("img", { name: "25% approved, 50% pending, 25% rejected" })).toBeTruthy();
  });

  it("shows zeros, not dashes, before there is anything, and a way to start", () => {
    mock.stats = { total: 0, pending: 0, approved: 0, rejected: 0, total_amount: 0, pending_amount: 0, approved_amount: 0 };
    render(<ExpenseClaims />);
    expect(screen.getByRole("img", { name: "No claims yet" })).toBeTruthy();
    expect(list().getByText("No expense claims yet")).toBeTruthy();
    fireEvent.click(list().getByRole("button", { name: /Submit your first expense/ }));
    expect(screen.getByText("new expense form")).toBeTruthy();
  });

  it("lists each claim with its category, title, date, receipts, amount and a coloured status", () => {
    mock.stats = STATS; mock.claims = [CLAIM(), CLAIM({ expense_number: 2, title: "Lunch", category: "meals", status: "approved", amount: 300, receipts: [] })];
    render(<ExpenseClaims />);
    expect(list().getByText("Travel")).toBeTruthy();
    expect(list().getByText(/Cab to client · D\(2026-11-10\)/).textContent).toContain("1 receipt");
    expect(list().getByText("₹1,250")).toBeTruthy();
    expect(list().getByText("pending").style.color).toMatch(/234,\s*88,\s*12|#EA580C/i);
    expect(list().getByText("approved").style.color).toMatch(/22,\s*163,\s*74|#16A34A/i);
  });

  it("opens a claim by click or by keyboard", () => {
    mock.stats = STATS; mock.claims = [CLAIM()];
    render(<ExpenseClaims />);
    fireEvent.click(list().getByRole("button", { name: /Travel/ }));
    expect(screen.getByText("detail of Cab to client")).toBeTruthy();
    cleanup();
    render(<ExpenseClaims />);
    fireEvent.keyDown(list().getByRole("button", { name: /Travel/ }), { key: "Enter" });
    expect(screen.getByText("detail of Cab to client")).toBeTruthy();
  });

  it("filters the claims by status, and says so when none match", () => {
    mock.stats = STATS; mock.claims = [CLAIM(), CLAIM({ expense_number: 2, title: "Lunch", category: "meals", status: "approved" })];
    render(<ExpenseClaims />);
    const group = within(screen.getByRole("group", { name: "Show claims" }));
    expect(group.getByRole("button", { name: /All 2/ })).toBeTruthy();
    fireEvent.click(group.getByRole("button", { name: /Approved 1/ }));
    expect(list().queryByText(/Cab to client/)).toBeNull();
    expect(list().getByText(/Lunch/)).toBeTruthy();
    fireEvent.click(group.getByRole("button", { name: /Rejected 0/ }));
    expect(list().getByText("No rejected claims among your recent ones.")).toBeTruthy();
  });

  it("shows only the latest five, placeholders while loading, and the error", () => {
    mock.stats = STATS; mock.claims = Array.from({ length: 7 }, (_, index) => CLAIM({ expense_number: index + 1, title: `Claim ${index + 1}` }));
    render(<ExpenseClaims />);
    expect(list().getAllByRole("button", { name: /Travel/ })).toHaveLength(5);
    cleanup();
    mock.loading = true;
    render(<ExpenseClaims />);
    expect(list().getAllByLabelText("Loading")).toHaveLength(3);
    cleanup();
    mock.loading = false; mock.error = "Could not load";
    render(<ExpenseClaims />);
    expect(screen.getByRole("alert").textContent).toContain("Could not load");
  });

  it("has no Submit button in the page header; the form opens from the list, and straight away when sent from a link", () => {
    mock.stats = STATS;
    render(<ExpenseClaims />);
    expect(screen.queryByRole("button", { name: /Submit Expense/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Submit your first expense/ }));
    expect(screen.getByText("new expense form")).toBeTruthy();
    cleanup();
    render(<ExpenseClaims autoOpenNew />);
    expect(screen.getByText("new expense form")).toBeTruthy();
  });
});

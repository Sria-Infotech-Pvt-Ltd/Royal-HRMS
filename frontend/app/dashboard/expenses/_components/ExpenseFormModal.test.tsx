// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";

const post = vi.hoisted(() => vi.fn());
vi.mock("@/lib/clientApi", () => ({ default: { post } }));
vi.mock("@/lib/api/endpoints", () => ({ API: { expenses: { list: "/expenses/" }, settings: { financialYear: "/settings/fy/" } } }));
vi.mock("@/hooks/useFetch", () => ({ useFetch: () => ({ data: { financial_year_start_month: "April" }, loading: false, error: null, refetch: vi.fn() }) }));
vi.mock("@/lib/formatDate", () => ({ formatDateSlash: (value: Date | string) => (value instanceof Date ? `${value.getDate()}/${value.getMonth() + 1}/${value.getFullYear()}` : String(value)) }));
vi.mock("@/app/dashboard/my-payslip/_components/types", () => ({
  currentFinancialYearStart: () => new Date(2026, 3, 1),
  financialYearLabel: () => "FY 2026-27",
}));
vi.mock("@/components/shared/DateInput", () => ({
  default: ({ value, onChange }: { value: string; onChange: (iso: string) => void }) => <input aria-label="Expense Date" value={value} onChange={event => onChange(event.target.value)} />,
}));
vi.mock("@/components/RequestModal", () => ({
  default: ({ children, onSubmit, error }: { children: React.ReactNode; onSubmit: () => void; error?: string }) => (
    <div>{error && <div role="alert">{error}</div>}{children}<button onClick={onSubmit}>Submit request</button></div>
  ),
}));

import ExpenseFormModal from "./ExpenseFormModal";

const onSaved = vi.fn();
const preview = () => within(screen.getByRole("complementary", { name: "Your claim" }));
const receipt = (name = "bill.pdf", type = "application/pdf", size = 1000) => {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size });
  return file;
};
const attach = (file: File) => fireEvent.change(document.querySelector('input[type="file"]') as HTMLInputElement, { target: { files: [file] } });

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 18, 12, 0));
  post.mockReset(); post.mockResolvedValue({}); onSaved.mockReset();
});
afterEach(() => { cleanup(); vi.useRealTimers(); });

const fillAll = () => {
  fireEvent.click(screen.getByRole("radio", { name: "Travel" }));
  fireEvent.change(screen.getByLabelText("Expense Date"), { target: { value: "2026-11-10" } });
  fireEvent.change(screen.getByPlaceholderText("0"), { target: { value: "1250" } });
  fireEvent.change(screen.getByPlaceholderText("Describe the business purpose"), { target: { value: "Cab to client site" } });
  attach(receipt());
};

describe("the expense claim form", () => {
  it("has four numbered steps and a claim card that starts empty", () => {
    render(<ExpenseFormModal onClose={vi.fn()} onSaved={onSaved} />);
    for (const title of ["What was it for?", "When and how much?", "Why was it needed?", "Attach your receipts"]) expect(screen.getByRole("region", { name: title })).toBeTruthy();
    expect(preview().getByText("No category yet")).toBeTruthy();
    expect(preview().getByText("4 required parts left")).toBeTruthy();
  });

  it("fills the claim card as the person types, and says when it is ready", () => {
    render(<ExpenseFormModal onClose={vi.fn()} onSaved={onSaved} />);
    fillAll();
    expect(preview().getByText("Travel")).toBeTruthy();
    expect(preview().getByText("₹1,250")).toBeTruthy();
    expect(preview().getByText("Cab to client site")).toBeTruthy();
    expect(preview().getByText("Ready to submit")).toBeTruthy();
    expect(screen.getByRole("radio", { name: "Travel" }).getAttribute("aria-checked")).toBe("true");
  });

  it("ticks a step off when its part is done", () => {
    render(<ExpenseFormModal onClose={vi.fn()} onSaved={onSaved} />);
    expect(within(screen.getByRole("region", { name: "What was it for?" })).queryByText("1")).toBeTruthy();
    fireEvent.click(screen.getByRole("radio", { name: "Meals" }));
    expect(within(screen.getByRole("region", { name: "What was it for?" })).queryByText("1")).toBeNull();
  });

  it("asks for everything that is missing, in the long-standing words, and sends nothing", () => {
    render(<ExpenseFormModal onClose={vi.fn()} onSaved={onSaved} />);
    fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
    expect(screen.getByText("Please select a category.")).toBeTruthy();
    expect(screen.getByText("Amount is required.")).toBeTruthy();
    expect(screen.getByText(/Enter a date between/)).toBeTruthy();
    expect(screen.getByText("At least one receipt is required.")).toBeTruthy();
    expect(post).not.toHaveBeenCalled();
  });

  it("refuses a receipt that is too big or the wrong kind", () => {
    render(<ExpenseFormModal onClose={vi.fn()} onSaved={onSaved} />);
    attach(receipt("huge.pdf", "application/pdf", 6 * 1024 * 1024));
    expect(screen.getByText('"huge.pdf" exceeds 5 MB.')).toBeTruthy();
    attach(receipt("note.txt", "text/plain"));
    expect(screen.getByText('"note.txt" must be PDF, JPG, or PNG.')).toBeTruthy();
    expect(preview().getByText("Receipts").nextSibling?.textContent).toBe("0");
  });

  it("sends the claim exactly as before and tells the page it was saved", async () => {
    render(<ExpenseFormModal onClose={vi.fn()} onSaved={onSaved} />);
    fillAll();
    fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    const [url, body] = post.mock.calls[0] as [string, FormData];
    expect(url).toBe("/expenses/");
    expect(body.get("title")).toBe("Cab to client site");
    expect(body.get("amount")).toBe("1250");
    expect(body.get("category")).toBe("travel");
    expect(body.get("expense_date")).toBe("2026-11-10");
    expect((body.getAll("receipts") as File[]).map(file => file.name)).toEqual(["bill.pdf"]);
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it("shows the server's message when it refuses", async () => {
    post.mockRejectedValueOnce({ response: { data: { message: "Claim window closed." } } });
    render(<ExpenseFormModal onClose={vi.fn()} onSaved={onSaved} />);
    fillAll();
    fireEvent.click(screen.getByRole("button", { name: "Submit request" }));
    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("Claim window closed."));
    expect(onSaved).not.toHaveBeenCalled();
  });
});

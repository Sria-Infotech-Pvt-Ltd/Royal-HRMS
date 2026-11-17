// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import LinkCard from "./LinkCard";

beforeEach(() => push.mockClear());
afterEach(cleanup);

describe("LinkCard", () => {
  it("opens its page when clicked", () => {
    render(<LinkCard href="/dashboard/employees" label="Open employees"><p>Headcount</p></LinkCard>);
    fireEvent.click(screen.getByText("Headcount"));
    expect(push).toHaveBeenCalledWith("/dashboard/employees");
  });

  it("opens its page with Enter or Space from the keyboard", () => {
    render(<LinkCard href="/dashboard/leave" label="Open leave"><p>Leave</p></LinkCard>);
    const card = screen.getByRole("link", { name: "Open leave" });
    fireEvent.keyDown(card, { key: "Enter" });
    fireEvent.keyDown(card, { key: " " });
    expect(push).toHaveBeenCalledTimes(2);
    expect(push).toHaveBeenCalledWith("/dashboard/leave");
  });

  it("is reachable by keyboard and named for screen readers", () => {
    render(<LinkCard href="/dashboard/payroll" label="Open payroll"><p>Payroll</p></LinkCard>);
    const card = screen.getByRole("link", { name: "Open payroll" });
    expect(card.getAttribute("tabindex")).toBe("0");
  });

  it("ignores other keys", () => {
    render(<LinkCard href="/dashboard/payroll" label="Open payroll"><p>Payroll</p></LinkCard>);
    fireEvent.keyDown(screen.getByRole("link", { name: "Open payroll" }), { key: "a" });
    expect(push).not.toHaveBeenCalled();
  });
});

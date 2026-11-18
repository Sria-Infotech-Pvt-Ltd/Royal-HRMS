// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import AttendanceDatePicker from "./AttendanceDatePicker";

afterEach(() => cleanup());

const TODAY = "2026-11-18";

describe("AttendanceDatePicker", () => {
  it("says which weekday the date is and how long ago", () => {
    render(<AttendanceDatePicker date="2026-11-14" todayISO={TODAY} onChange={vi.fn()} />);
    expect(screen.getByText("Saturday")).toBeTruthy();
    expect(screen.getByText(/4 days ago/)).toBeTruthy();
  });

  it("the arrows move exactly one day, not two and not none", () => {
    const onChange = vi.fn();
    render(<AttendanceDatePicker date="2026-11-14" todayISO={TODAY} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Previous day" }));
    fireEvent.click(screen.getByRole("button", { name: "Next day" }));
    expect(onChange.mock.calls.map(call => call[0])).toEqual(["2026-11-13", "2026-11-15"]);
  });

  it("cannot go past today", () => {
    render(<AttendanceDatePicker date={TODAY} todayISO={TODAY} onChange={vi.fn()} />);
    expect((screen.getByRole("button", { name: "Next day" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("jumps to Today or Yesterday in one click, and marks the one that is showing", () => {
    const onChange = vi.fn();
    const { rerender } = render(<AttendanceDatePicker date="2026-11-14" todayISO={TODAY} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Yesterday" }));
    fireEvent.click(screen.getByRole("button", { name: "Today" }));
    expect(onChange.mock.calls.map(call => call[0])).toEqual(["2026-11-17", "2026-11-18"]);
    rerender(<AttendanceDatePicker date="2026-11-17" todayISO={TODAY} onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Yesterday" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Today" }).getAttribute("aria-pressed")).toBe("false");
  });

  it("does not repeat Today or Yesterday in the caption when the highlighted button already says it", () => {
    const { rerender } = render(<AttendanceDatePicker date={TODAY} todayISO={TODAY} onChange={vi.fn()} />);
    const caption = () => screen.getByText("Wednesday", { selector: "strong" }).parentElement?.textContent;
    expect(caption()).toBe("Wednesday");
    rerender(<AttendanceDatePicker date="2026-11-17" todayISO={TODAY} onChange={vi.fn()} />);
    expect(screen.getByText("Tuesday", { selector: "strong" }).parentElement?.textContent).toBe("Tuesday");
    rerender(<AttendanceDatePicker date="2026-11-14" todayISO={TODAY} onChange={vi.fn()} />);
    expect(screen.getByText("Saturday", { selector: "strong" }).parentElement?.textContent).toBe("Saturday · 4 days ago");
  });
});

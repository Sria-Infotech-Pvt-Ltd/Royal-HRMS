// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";

import AttendancePageTabs, { type AttendanceTabItem } from "./AttendancePageTabs";

afterEach(() => cleanup());

const TABS: AttendanceTabItem[] = [
  { id: "attendance", label: "Attendance", icon: "ti-calendar-stats" },
  { id: "ot", label: "OT Entry", icon: "ti-clock-plus" },
  { id: "invalid", label: "Invalid Punches", icon: "ti-alert-triangle", badge: 3 },
  { id: "corrections", label: "Corrections", icon: "ti-file-description", badge: 0 },
];

describe("AttendancePageTabs", () => {
  it("marks the active tab and shows the brand colour (it follows the theme), not black", () => {
    render(<AttendancePageTabs tabs={TABS} active="ot" onSelect={vi.fn()} />);
    const active = screen.getByRole("tab", { name: /OT Entry/ });
    expect(active.getAttribute("aria-selected")).toBe("true");
    expect(active.style.color).toMatch(/var\(--brand\)/);
    expect(active.style.borderBottomWidth).toBe("0px");                         // no plain black underline on the tab itself: the purple indicator slides instead
    const other = screen.getByRole("tab", { name: /Attendance/ });
    expect(other.getAttribute("aria-selected")).toBe("false");
    expect(other.style.color).not.toMatch(/var\(--brand\)/);
    expect(other.tabIndex).toBe(-1);                                            // only the active tab is in the tab order
  });

  it("selects a tab on click", () => {
    const onSelect = vi.fn();
    render(<AttendancePageTabs tabs={TABS} active="attendance" onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("tab", { name: /Corrections/ }));
    expect(onSelect).toHaveBeenCalledWith("corrections");
  });

  it("shows a coloured count only when there is one", () => {
    render(<AttendancePageTabs tabs={TABS} active="attendance" onSelect={vi.fn()} />);
    const badge = screen.getByText("3");
    expect(badge.style.background).toMatch(/220,\s*38,\s*38|#DC2626/i);
    expect(screen.queryByText("0")).toBeNull();
  });

  it("moves between tabs with the arrow keys, wrapping at the ends, and with Home and End", () => {
    const onSelect = vi.fn();
    render(<AttendancePageTabs tabs={TABS} active="attendance" onSelect={onSelect} />);
    const first = screen.getByRole("tab", { name: /^Attendance/ });
    fireEvent.keyDown(first, { key: "ArrowRight" });
    expect(onSelect).toHaveBeenLastCalledWith("ot");
    fireEvent.keyDown(first, { key: "ArrowLeft" });                              // from the first, wraps to the last
    expect(onSelect).toHaveBeenLastCalledWith("corrections");
    fireEvent.keyDown(first, { key: "End" });
    expect(onSelect).toHaveBeenLastCalledWith("corrections");
    fireEvent.keyDown(screen.getByRole("tab", { name: /Corrections/ }), { key: "Home" });
    expect(onSelect).toHaveBeenLastCalledWith("attendance");
    fireEvent.keyDown(first, { key: "a" });
    expect(onSelect).toHaveBeenCalledTimes(4);                                   // other keys do nothing
  });

  it("has a sliding indicator that is hidden from screen readers, and tints a tab on hover", () => {
    const { container } = render(<AttendancePageTabs tabs={TABS} active="attendance" onSelect={vi.fn()} />);
    const indicator = container.querySelector('span[aria-hidden="true"]') as HTMLElement;
    expect(indicator.style.transition).toContain("transform");
    expect(indicator.style.background).toContain("linear-gradient");
    const tab = screen.getByRole("tab", { name: /OT Entry/ });
    fireEvent.mouseEnter(tab);
    expect(tab.style.background).toMatch(/var\(--brand\)/);
    fireEvent.mouseLeave(tab);
    expect(tab.style.background).toBe("transparent");
  });

  it("scrolls sideways on a narrow screen instead of wrapping", () => {
    render(<AttendancePageTabs tabs={TABS} active="attendance" onSelect={vi.fn()} />);
    expect(screen.getByRole("tablist").style.overflowX).toBe("auto");
  });
});

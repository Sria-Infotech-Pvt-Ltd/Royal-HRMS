// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import PageBackButton from "./PageBackButton";

const back = vi.fn();
const push = vi.fn();
let pathname = "/dashboard/branches";
vi.mock("next/navigation", () => ({ useRouter: () => ({ back, push }), usePathname: () => pathname }));

beforeEach(() => { back.mockClear(); push.mockClear(); pathname = "/dashboard/branches"; });
afterEach(() => cleanup());

describe("PageBackButton", () => {
  it("goes back to the previous page when there is one", () => {
    vi.spyOn(window.history, "length", "get").mockReturnValue(3);
    render(<PageBackButton />);
    fireEvent.click(screen.getByRole("button", { name: "Go back" }));
    expect(back).toHaveBeenCalledTimes(1);
    expect(push).not.toHaveBeenCalled();
  });

  it("goes to the page above when the page was opened directly", () => {
    vi.spyOn(window.history, "length", "get").mockReturnValue(1);
    pathname = "/dashboard/reports/attendance";
    render(<PageBackButton />);
    fireEvent.click(screen.getByRole("button", { name: "Go back" }));
    expect(push).toHaveBeenCalledWith("/dashboard/reports");
  });

  it("renders nothing on the dashboard home or on a page with its own Back", () => {
    pathname = "/dashboard";
    const { container, rerender } = render(<PageBackButton />);
    expect(container.firstChild).toBeNull();
    pathname = "/dashboard/org-chart";
    rerender(<PageBackButton />);
    expect(container.firstChild).toBeNull();
  });
});

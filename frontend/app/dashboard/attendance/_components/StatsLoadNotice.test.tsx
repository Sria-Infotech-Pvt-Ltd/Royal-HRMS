// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import StatsLoadNotice from "./StatsLoadNotice";

afterEach(cleanup);

describe("StatsLoadNotice", () => {
  it("says the counts could not load and why, and offers Try again", () => {
    const onRetry = vi.fn();
    render(<StatsLoadNotice status={403} onRetry={onRetry} />);
    expect(screen.getByRole("alert").textContent).toMatch(/counts could not be loaded/i);
    expect(screen.getByRole("alert").textContent).toMatch(/permission/);
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

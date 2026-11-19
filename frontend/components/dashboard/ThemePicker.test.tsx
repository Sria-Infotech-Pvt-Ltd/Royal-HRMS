// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const choose = vi.fn();
vi.mock("@/hooks/useTheme", () => ({ useTheme: () => ({ theme: { mode: "light", accent: "royal" }, choose }) }));

import ThemePicker from "./ThemePicker";

afterEach(() => { cleanup(); choose.mockClear(); });

describe("ThemePicker", () => {
  it("opens, shows every mode and colour, and marks the current ones", () => {
    render(<ThemePicker />);
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Theme" }));
    expect(screen.getByRole("dialog", { name: "Choose a theme" })).toBeTruthy();
    for (const label of ["Match my device", "Light", "Dark", "Royal Purple", "Ocean Blue", "Forest Green", "Sunset Orange"]) {
      expect(screen.getByRole("button", { name: new RegExp(label) })).toBeTruthy();
    }
    expect(screen.getByRole("button", { name: "Light" }).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: /Royal Purple/ }).getAttribute("aria-pressed")).toBe("true");
  });

  it("passes the chosen mode or colour on, one at a time", () => {
    render(<ThemePicker />);
    fireEvent.click(screen.getByRole("button", { name: "Theme" }));
    fireEvent.click(screen.getByRole("button", { name: "Dark" }));
    fireEvent.click(screen.getByRole("button", { name: /Ocean Blue/ }));
    expect(choose.mock.calls).toEqual([[{ mode: "dark" }], [{ accent: "ocean" }]]);
  });

  it("closes on Escape", () => {
    render(<ThemePicker />);
    fireEvent.click(screen.getByRole("button", { name: "Theme" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const choose = vi.fn();
vi.mock("@/hooks/useTheme", () => ({ useTheme: () => ({ theme: { mode: "light", accent: "royal", style: "classic", custom: {} }, choose }) }));

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

  it("lets the person pick a look; the pure-black look also switches to dark", () => {
    render(<ThemePicker />);
    fireEvent.click(screen.getByRole("button", { name: "Theme" }));
    fireEvent.click(screen.getByRole("button", { name: /Soft/ }));
    fireEvent.click(screen.getByRole("button", { name: /Pure black/ }));
    expect(choose.mock.calls).toEqual([[{ style: "soft" }], [{ style: "amoled", mode: "dark" }]]);
    expect(screen.getByRole("button", { name: /Classic/ }).getAttribute("aria-pressed")).toBe("true");
  });

  it("lets the person pick their own colour", () => {
    render(<ThemePicker />);
    fireEvent.click(screen.getByRole("button", { name: "Theme" }));
    fireEvent.change(screen.getByLabelText("Main colour"), { target: { value: "#0a7b5c" } });
    expect(choose).toHaveBeenCalledWith({ custom: { brand: "#0a7b5c" } });
  });
});

import { describe, expect, it } from "vitest";
import { contrastRatio, customVariables, ensureContrast, isHexColour, mix, readableOn, wasAdjusted } from "./themeColors";

describe("colour helpers", () => {
  it("accepts only six-digit hex colours", () => {
    expect(isHexColour("#7c3aed")).toBe(true);
    for (const bad of ["7c3aed", "#7c3", "red", "#gggggg", "", null, 5]) expect(isHexColour(bad)).toBe(false);
  });

  it("measures contrast like the web standard (black on white is 21)", () => {
    expect(Math.round(contrastRatio("#000000", "#ffffff"))).toBe(21);
    expect(contrastRatio("#777777", "#ffffff")).toBeLessThan(4.5);
  });

  it("mixes colours and picks readable text", () => {
    expect(mix("#000000", "#ffffff", 0.5)).toBe("#808080");
    expect(readableOn("#ffffff")).toBe("#0b0b12");
    expect(readableOn("#111111")).toBe("#ffffff");
  });

  it("nudges a hard-to-read colour until it reaches 4.5:1, and leaves a good one alone", () => {
    expect(ensureContrast("#222222", "#ffffff")).toBe("#222222");
    const fixed = ensureContrast("#bbbbbb", "#ffffff");
    expect(contrastRatio(fixed, "#ffffff")).toBeGreaterThanOrEqual(4.5);
  });
});

describe("customVariables", () => {
  it("makes nothing when nothing is picked", () => {
    expect(customVariables({})).toEqual({});
  });

  it("keeps text readable on any card colour the person picks", () => {
    for (const card of ["#ffffff", "#000000", "#ffe9a8", "#1a237e", "#777777"]) {
      const variables = customVariables({ card, text: "#8a8a8a" });
      expect(contrastRatio(variables["--ink"], card), card).toBeGreaterThanOrEqual(4.5);
      expect(contrastRatio(variables["--muted"], card), card).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("keeps text on the main colour readable, whichever colour it is", () => {
    for (const brand of ["#ffee00", "#0a2a66", "#7c3aed", "#ffffff"]) {
      const variables = customVariables({ brand });
      expect(contrastRatio(variables["--onbrand"], brand), brand).toBeGreaterThanOrEqual(4.5);
      expect(contrastRatio(variables["--brand-ink"], "#ffffff"), brand).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("sets the top bar colour with readable text on it", () => {
    const variables = customVariables({ header: "#112233" });
    expect(variables["--header-bg"]).toBe("#112233");
    expect(contrastRatio(variables["--header-ink"], "#112233")).toBeGreaterThanOrEqual(4.5);
  });

  it("ignores values that are not colours", () => {
    expect(customVariables({ brand: "red", card: "#12" })).toEqual({});
  });

  it("says when it had to adjust a colour", () => {
    expect(wasAdjusted({ text: "#cccccc" })).toBe(true);
    expect(wasAdjusted({ text: "#111111", brand: "#0a2a66" })).toBe(false);
  });
});

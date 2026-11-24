// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_THEME, THEME_BOOT_SCRIPT, THEME_STORAGE_KEY, applyTheme, normaliseTheme, readStoredTheme, resolveMode, storeTheme,
} from "./theme";

function stubDevice(isDark: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({ matches: isDark, media: query, addEventListener: vi.fn(), removeEventListener: vi.fn() }));
}

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("style");
  document.documentElement.removeAttribute("data-style");
  document.documentElement.removeAttribute("data-header");
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-accent");
  stubDevice(false);
});
afterEach(() => vi.unstubAllGlobals());

describe("normaliseTheme", () => {
  it("keeps valid values and replaces anything else with the default", () => {
    expect(normaliseTheme({ mode: "dark", accent: "ocean" })).toEqual({ ...DEFAULT_THEME, mode: "dark", accent: "ocean" });
    expect(normaliseTheme({ mode: "neon", accent: 7 })).toEqual(DEFAULT_THEME);
    expect(normaliseTheme(null)).toEqual(DEFAULT_THEME);
  });
});

describe("stored theme", () => {
  it("round-trips through the browser", () => {
    storeTheme({ ...DEFAULT_THEME, mode: "system", accent: "forest" });
    expect(readStoredTheme()).toEqual({ ...DEFAULT_THEME, mode: "system", accent: "forest" });
  });

  it("falls back to the default on bad JSON", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "{not json");
    expect(readStoredTheme()).toEqual(DEFAULT_THEME);
  });

  it("keeps the dark mode chosen with the old button", () => {
    localStorage.setItem("aira-dark-mode", "1");
    expect(readStoredTheme()).toEqual({ ...DEFAULT_THEME, mode: "dark" });
  });
});

describe("applyTheme", () => {
  it("sets mode and accent on the page; the original purple needs no accent attribute", () => {
    applyTheme({ ...DEFAULT_THEME, mode: "dark", accent: "sunset" });
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(document.documentElement.getAttribute("data-accent")).toBe("sunset");
    applyTheme({ ...DEFAULT_THEME, mode: "light", accent: "royal" });
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(document.documentElement.hasAttribute("data-accent")).toBe(false);
  });

  it("turns 'match my device' into an explicit light or dark", () => {
    stubDevice(true);
    expect(resolveMode("system")).toBe("dark");
    stubDevice(false);
    expect(resolveMode("system")).toBe("light");
  });
});

describe("boot script (runs before the first paint)", () => {
  function boot() { new Function(THEME_BOOT_SCRIPT)(); }

  it("applies the saved choice", () => {
    storeTheme({ ...DEFAULT_THEME, mode: "dark", accent: "ocean" });
    boot();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(document.documentElement.getAttribute("data-accent")).toBe("ocean");
  });

  it("starts light with nothing saved, and follows the device for 'system'", () => {
    boot();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    storeTheme({ ...DEFAULT_THEME, mode: "system", accent: "royal" });
    stubDevice(true);
    boot();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("ignores a bad saved value instead of throwing", () => {
    localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify({ mode: "neon", accent: "pink" }));
    boot();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(document.documentElement.hasAttribute("data-accent")).toBe(false);
  });
});

describe("look and own colours", () => {
  it("keeps a valid look and valid colours, and drops anything else", () => {
    const theme = normaliseTheme({ style: "soft", custom: { brand: "#0A7B5C", text: "red", border: "#112233" } });
    expect(theme.style).toBe("soft");
    expect(theme.custom).toEqual({ brand: "#0a7b5c" });
    expect(normaliseTheme({ style: "neon", custom: "x" })).toEqual(DEFAULT_THEME);
  });

  it("puts the look and the person's own colours on the page, and removes them again", () => {
    applyTheme({ ...DEFAULT_THEME, style: "compact", custom: { brand: "#0a7b5c", header: "#112233" } });
    const root = document.documentElement;
    expect(root.getAttribute("data-style")).toBe("compact");
    expect(root.style.getPropertyValue("--brand")).toBe("#0a7b5c");
    expect(root.getAttribute("data-header")).toBe("custom");
    applyTheme(DEFAULT_THEME);
    expect(root.hasAttribute("data-style")).toBe(false);
    expect(root.style.getPropertyValue("--brand")).toBe("");
    expect(root.hasAttribute("data-header")).toBe(false);
  });

  it("the pure-black look is always dark", () => {
    applyTheme({ ...DEFAULT_THEME, mode: "light", style: "amoled" });
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });

  it("the boot script paints the look and the colours before anything loads", () => {
    storeTheme({ ...DEFAULT_THEME, style: "glass", custom: { brand: "#0a7b5c" } });
    new Function(THEME_BOOT_SCRIPT)();
    expect(document.documentElement.getAttribute("data-style")).toBe("glass");
    expect(document.documentElement.style.getPropertyValue("--brand")).toBe("#0a7b5c");
  });
});

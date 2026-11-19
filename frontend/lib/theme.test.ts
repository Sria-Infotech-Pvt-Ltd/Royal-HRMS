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
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-accent");
  stubDevice(false);
});
afterEach(() => vi.unstubAllGlobals());

describe("normaliseTheme", () => {
  it("keeps valid values and replaces anything else with the default", () => {
    expect(normaliseTheme({ mode: "dark", accent: "ocean" })).toEqual({ mode: "dark", accent: "ocean" });
    expect(normaliseTheme({ mode: "neon", accent: 7 })).toEqual(DEFAULT_THEME);
    expect(normaliseTheme(null)).toEqual(DEFAULT_THEME);
  });
});

describe("stored theme", () => {
  it("round-trips through the browser", () => {
    storeTheme({ mode: "system", accent: "forest" });
    expect(readStoredTheme()).toEqual({ mode: "system", accent: "forest" });
  });

  it("falls back to the default on bad JSON", () => {
    localStorage.setItem(THEME_STORAGE_KEY, "{not json");
    expect(readStoredTheme()).toEqual(DEFAULT_THEME);
  });

  it("keeps the dark mode chosen with the old button", () => {
    localStorage.setItem("aira-dark-mode", "1");
    expect(readStoredTheme()).toEqual({ mode: "dark", accent: "royal" });
  });
});

describe("applyTheme", () => {
  it("sets mode and accent on the page; the original purple needs no accent attribute", () => {
    applyTheme({ mode: "dark", accent: "sunset" });
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(document.documentElement.getAttribute("data-accent")).toBe("sunset");
    applyTheme({ mode: "light", accent: "royal" });
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
    storeTheme({ mode: "dark", accent: "ocean" });
    boot();
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(document.documentElement.getAttribute("data-accent")).toBe("ocean");
  });

  it("starts light with nothing saved, and follows the device for 'system'", () => {
    boot();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    storeTheme({ mode: "system", accent: "royal" });
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

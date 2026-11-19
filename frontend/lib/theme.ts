// Theme choices: a mode (light / dark / follow the device) and an accent colour. Stored in the browser (so the page can paint the right
// colours before anything loads) and on the user's profile (so the choice follows them to another device).

export const THEME_MODES = ["system", "light", "dark"] as const;
export type ThemeMode = (typeof THEME_MODES)[number];

export const THEME_ACCENTS = ["royal", "ocean", "forest", "sunset"] as const;
export type ThemeAccent = (typeof THEME_ACCENTS)[number];

export interface ThemeChoice { mode: ThemeMode; accent: ThemeAccent }

// Light by default: that is what the app has always shown until someone picks dark.
export const DEFAULT_THEME: ThemeChoice = { mode: "light", accent: "royal" };
export const THEME_STORAGE_KEY = "aira-theme";
// The key the old dark-mode button used ("1" = dark). Read once so people who chose dark before keep it.
const LEGACY_DARK_KEY = "aira-dark-mode";

export const ACCENT_LABELS: Record<ThemeAccent, { label: string; swatch: string }> = {
  royal: { label: "Royal Purple", swatch: "#7c3aed" },
  ocean: { label: "Ocean Blue", swatch: "#0369a1" },
  forest: { label: "Forest Green", swatch: "#15803d" },
  sunset: { label: "Sunset Orange", swatch: "#c2410c" },
};

export const MODE_LABELS: Record<ThemeMode, string> = { system: "Match my device", light: "Light", dark: "Dark" };

export function isThemeMode(value: unknown): value is ThemeMode {
  return typeof value === "string" && (THEME_MODES as readonly string[]).includes(value);
}

export function isThemeAccent(value: unknown): value is ThemeAccent {
  return typeof value === "string" && (THEME_ACCENTS as readonly string[]).includes(value);
}

/** Anything unknown or missing falls back to the default, so a bad saved value can never break the page. */
export function normaliseTheme(value: { mode?: unknown; accent?: unknown } | null | undefined): ThemeChoice {
  return {
    mode: isThemeMode(value?.mode) ? value.mode : DEFAULT_THEME.mode,
    accent: isThemeAccent(value?.accent) ? value.accent : DEFAULT_THEME.accent,
  };
}

export function readStoredTheme(): ThemeChoice {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (raw) return normaliseTheme(JSON.parse(raw) as { mode?: unknown; accent?: unknown });
    if (localStorage.getItem(LEGACY_DARK_KEY) === "1") return { ...DEFAULT_THEME, mode: "dark" };
  } catch {
    // Storage blocked or the value is not valid JSON: use the default.
  }
  return DEFAULT_THEME;
}

export function storeTheme(choice: ThemeChoice): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify(choice));
  } catch {
    // Storage blocked: the choice still applies for this page view.
  }
}

const DARK_QUERY = "(prefers-color-scheme: dark)";

/** "system" becomes an explicit light or dark from the device setting. The app's two colour systems only agree when data-theme is set. */
export function resolveMode(mode: ThemeMode): "light" | "dark" {
  if (mode !== "system") return mode;
  return typeof window !== "undefined" && window.matchMedia(DARK_QUERY).matches ? "dark" : "light";
}

/** Put the choice on <html>. */
export function applyTheme(choice: ThemeChoice, root: HTMLElement = document.documentElement): void {
  root.setAttribute("data-theme", resolveMode(choice.mode));
  if (choice.accent === "royal") root.removeAttribute("data-accent");
  else root.setAttribute("data-accent", choice.accent);
}

/** Calls `onChange` when the device switches between light and dark. Returns a function that stops listening. */
export function watchDeviceMode(onChange: () => void): () => void {
  const query = window.matchMedia(DARK_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

// Runs in <head> before the first paint. It repeats the logic of readStoredTheme + applyTheme in plain JS, on purpose: it cannot import.
export const THEME_BOOT_SCRIPT = `(function(){try{var m="light",a="royal",r=localStorage.getItem("${THEME_STORAGE_KEY}");
if(r){var t=JSON.parse(r);if(t&&(t.mode==="light"||t.mode==="dark"||t.mode==="system"))m=t.mode;if(t&&["ocean","forest","sunset"].indexOf(t.accent)>-1)a=t.accent;}
else if(localStorage.getItem("${LEGACY_DARK_KEY}")==="1"){m="dark";}
if(m==="system")m=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";
var e=document.documentElement;e.setAttribute("data-theme",m);if(a!=="royal")e.setAttribute("data-accent",a);}catch(x){}})();`;

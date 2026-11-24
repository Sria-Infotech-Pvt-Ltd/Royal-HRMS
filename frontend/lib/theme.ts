import { CUSTOM_COLOUR_KEYS, CUSTOM_VARIABLE_NAMES, customVariables, isHexColour, type CustomColours } from "./themeColors";

// Theme choices: a mode (light / dark / follow the device) and an accent colour. Stored in the browser (so the page can paint the right
// colours before anything loads) and on the user's profile (so the choice follows them to another device).

export const THEME_MODES = ["system", "light", "dark"] as const;
export type ThemeMode = (typeof THEME_MODES)[number];

export const THEME_ACCENTS = ["royal", "ocean", "forest", "sunset"] as const;
export type ThemeAccent = (typeof THEME_ACCENTS)[number];

// The look: shapes, spacing, shadows and type, not only colours (see app/theme-styles.css). Keep in step with THEME_STYLES in
// backend/apps/accounts/views_theme.py.
export const THEME_STYLES = ["classic", "soft", "compact", "glass", "amoled", "contrast"] as const;
export type ThemeStyle = (typeof THEME_STYLES)[number];

export const STYLE_LABELS: Record<ThemeStyle, { label: string; hint: string }> = {
  classic: { label: "Classic", hint: "The standard look" },
  soft: { label: "Soft", hint: "Rounded cards and soft shadows" },
  compact: { label: "Compact", hint: "Tighter spacing, more on screen" },
  glass: { label: "Glass", hint: "Frosted, see-through panels" },
  amoled: { label: "Pure black", hint: "True black, for OLED screens" },
  contrast: { label: "High contrast", hint: "Strong edges and larger text" },
};

export interface ThemeChoice { mode: ThemeMode; accent: ThemeAccent; style: ThemeStyle; custom: CustomColours }

// Light by default: that is what the app has always shown until someone picks dark.
export const DEFAULT_THEME: ThemeChoice = { mode: "light", accent: "royal", style: "classic", custom: {} };
export const THEME_STORAGE_KEY = "aira-theme";
// The CSS variables worked out from the person's own colours, kept so the boot script can paint them before anything loads.
export const THEME_VARS_KEY = "aira-theme-vars";
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

export function isThemeStyle(value: unknown): value is ThemeStyle {
  return typeof value === "string" && (THEME_STYLES as readonly string[]).includes(value);
}

function cleanCustom(value: unknown): CustomColours {
  const cleaned: CustomColours = {};
  if (typeof value !== "object" || value === null) return cleaned;
  for (const key of CUSTOM_COLOUR_KEYS) {
    const colour = (value as Record<string, unknown>)[key];
    if (isHexColour(colour)) cleaned[key] = colour.toLowerCase();
  }
  return cleaned;
}

export interface ThemeInput { mode?: unknown; accent?: unknown; style?: unknown; custom?: unknown }

/** Anything unknown or missing falls back to the default, so a bad saved value can never break the page. */
export function normaliseTheme(value: ThemeInput | null | undefined): ThemeChoice {
  return {
    mode: isThemeMode(value?.mode) ? value.mode : DEFAULT_THEME.mode,
    accent: isThemeAccent(value?.accent) ? value.accent : DEFAULT_THEME.accent,
    style: isThemeStyle(value?.style) ? value.style : DEFAULT_THEME.style,
    custom: cleanCustom(value?.custom),
  };
}

export function readStoredTheme(): ThemeChoice {
  try {
    const raw = localStorage.getItem(THEME_STORAGE_KEY);
    if (raw) return normaliseTheme(JSON.parse(raw) as ThemeInput);
    if (localStorage.getItem(LEGACY_DARK_KEY) === "1") return { ...DEFAULT_THEME, mode: "dark" };
  } catch {
    // Storage blocked or the value is not valid JSON: use the default.
  }
  return DEFAULT_THEME;
}

export function storeTheme(choice: ThemeChoice): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, JSON.stringify(choice));
    localStorage.setItem(THEME_VARS_KEY, JSON.stringify(customVariables(choice.custom)));
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

/** Put the choice on <html>. The pure-black look only exists in dark, so it makes the page dark. */
export function applyTheme(choice: ThemeChoice, root: HTMLElement = document.documentElement): void {
  root.setAttribute("data-theme", choice.style === "amoled" ? "dark" : resolveMode(choice.mode));
  if (choice.accent === "royal") root.removeAttribute("data-accent");
  else root.setAttribute("data-accent", choice.accent);
  if (choice.style === "classic") root.removeAttribute("data-style");
  else root.setAttribute("data-style", choice.style);
  applyCustomColours(choice.custom, root);
}

/** The person's own colours go on <html> as inline variables, which win over every theme rule. */
export function applyCustomColours(custom: CustomColours, root: HTMLElement = document.documentElement): void {
  for (const name of CUSTOM_VARIABLE_NAMES) root.style.removeProperty(name);
  const variables = customVariables(custom);
  for (const [name, value] of Object.entries(variables)) root.style.setProperty(name, value);
  if (variables["--header-bg"]) root.setAttribute("data-header", "custom");
  else root.removeAttribute("data-header");
}

/** Calls `onChange` when the device switches between light and dark. Returns a function that stops listening. */
export function watchDeviceMode(onChange: () => void): () => void {
  const query = window.matchMedia(DARK_QUERY);
  query.addEventListener("change", onChange);
  return () => query.removeEventListener("change", onChange);
}

// Runs in <head> before the first paint. It repeats the logic of readStoredTheme + applyTheme in plain JS, on purpose: it cannot import.
// The colour variables were worked out when the choice was saved (THEME_VARS_KEY), so it only has to set them.
export const THEME_BOOT_SCRIPT = `(function(){try{var m="light",a="royal",st="classic",r=localStorage.getItem("${THEME_STORAGE_KEY}");
if(r){var t=JSON.parse(r);if(t&&(t.mode==="light"||t.mode==="dark"||t.mode==="system"))m=t.mode;if(t&&["ocean","forest","sunset"].indexOf(t.accent)>-1)a=t.accent;
if(t&&["soft","compact","glass","amoled","contrast"].indexOf(t.style)>-1)st=t.style;}
else if(localStorage.getItem("${LEGACY_DARK_KEY}")==="1"){m="dark";}
if(st==="amoled")m="dark";
if(m==="system")m=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";
var e=document.documentElement;e.setAttribute("data-theme",m);if(a!=="royal")e.setAttribute("data-accent",a);if(st!=="classic")e.setAttribute("data-style",st);
var v=JSON.parse(localStorage.getItem("${THEME_VARS_KEY}")||"{}");for(var k in v){e.style.setProperty(k,v[k]);}if(v["--header-bg"])e.setAttribute("data-header","custom");}catch(x){}})();`;

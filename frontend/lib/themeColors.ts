// Turns the few colours a person picks (main, background, card, text, header) into every colour variable the app uses, and keeps text
// readable: whatever is picked, text on a surface and text on the main colour are nudged until they reach a 4.5:1 contrast ratio.
// Status colours (present / late / absent ...) are not touched: they carry meaning.

export const CUSTOM_COLOUR_KEYS = ["brand", "background", "card", "text", "header"] as const;
export type CustomColourKey = (typeof CUSTOM_COLOUR_KEYS)[number];
export type CustomColours = Partial<Record<CustomColourKey, string>>;

export const CUSTOM_COLOUR_LABELS: Record<CustomColourKey, string> = {
  brand: "Main colour", background: "Page background", card: "Cards and panels", text: "Text", header: "Top bar",
};

const HEX_COLOUR = /^#[0-9a-f]{6}$/i;
const MIN_CONTRAST = 4.5;

type Rgb = readonly [number, number, number];

export function isHexColour(value: unknown): value is string {
  return typeof value === "string" && HEX_COLOUR.test(value);
}

function toRgb(hex: string): Rgb {
  return [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
}

function toHex([red, green, blue]: Rgb): string {
  return "#" + [red, green, blue].map(channel => Math.round(Math.min(255, Math.max(0, channel))).toString(16).padStart(2, "0")).join("");
}

/** `amount` of `second` mixed into `first` (0 = first, 1 = second). */
export function mix(first: string, second: string, amount: number): string {
  const [a, b] = [toRgb(first), toRgb(second)];
  return toHex([0, 1, 2].map(index => a[index] + (b[index] - a[index]) * amount) as unknown as Rgb);
}

function luminance(hex: string): number {
  const [red, green, blue] = toRgb(hex).map(channel => {
    const unit = channel / 255;
    return unit <= 0.03928 ? unit / 12.92 : ((unit + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * red + 0.7152 * green + 0.0722 * blue;
}

export function contrastRatio(first: string, second: string): number {
  const [light, dark] = [luminance(first), luminance(second)].sort((a, b) => b - a);
  return (light + 0.05) / (dark + 0.05);
}

/** Black or white, whichever reads better on `background`. */
export function readableOn(background: string): string {
  return contrastRatio("#ffffff", background) >= contrastRatio("#0b0b12", background) ? "#ffffff" : "#0b0b12";
}

/** Moves `colour` towards black or white (whichever helps) until it reaches the minimum contrast against `background`. */
export function ensureContrast(colour: string, background: string, minimum: number = MIN_CONTRAST): string {
  if (contrastRatio(colour, background) >= minimum) return colour;
  const preferred = readableOn(background) === "#ffffff" ? "#ffffff" : "#000000";
  const other = preferred === "#ffffff" ? "#000000" : "#ffffff";
  // On a mid-grey background the preferred direction can top out just under the minimum while the other one reaches it.
  const direction = contrastRatio(preferred, background) >= minimum ? preferred : contrastRatio(other, background) >= minimum ? other : preferred;
  for (let step = 1; step <= 20; step++) {
    const candidate = mix(colour, direction, step / 20);
    if (contrastRatio(candidate, background) >= minimum) return candidate;
  }
  return contrastRatio(preferred, background) >= contrastRatio(other, background) ? preferred : other;
}

function isDarkColour(hex: string): boolean {
  return luminance(hex) < 0.18;
}

function surfaceVariables(background: string, card: string, text: string): Record<string, string> {
  const edge = isDarkColour(card) ? "#ffffff" : "#000000";
  const readable = ensureContrast(text, card);
  return {
    "--ground": background, "--bg": background, "--bg-low": mix(background, card, 0.5), "--bg-mid": mix(background, edge, 0.04),
    "--sunken": mix(background, edge, 0.04),
    "--surface": card, "--surface-2": mix(card, edge, 0.025), "--bg-high": mix(card, edge, 0.08), "--bg-highest": mix(card, edge, 0.14),
    "--line": mix(card, edge, 0.12), "--line-soft": mix(card, edge, 0.06), "--outline-v": mix(card, edge, 0.12),
    "--ink": readable, "--on-bg": readable, "--ink-2": ensureContrast(mix(readable, card, 0.2), card),
    "--muted": ensureContrast(mix(readable, card, 0.38), card), "--on-variant": ensureContrast(mix(readable, card, 0.38), card),
    "--faint": ensureContrast(mix(readable, card, 0.52), card, 3.2), "--outline": ensureContrast(mix(readable, card, 0.52), card, 3.2),
  };
}

function brandVariables(brand: string, card: string): Record<string, string> {
  const ink = ensureContrast(brand, card);
  const tint = mix(card, brand, isDarkColour(card) ? 0.16 : 0.1);
  const onBrand = readableOn(brand);
  return {
    "--brand": brand, "--primary": brand, "--brand-2": mix(brand, isDarkColour(brand) ? "#ffffff" : "#000000", 0.16),
    "--primary-c": mix(brand, isDarkColour(card) ? "#ffffff" : "#000000", 0.2), "--brand-tint": tint, "--sec-c": tint,
    "--brand-ink": ink, "--secondary": ink, "--onbrand": onBrand, "--on-primary": onBrand, "--chart-1": brand, "--purple": brand,
  };
}

/** The CSS variables for the colours a person picked. Anything they did not pick is left to the theme. */
export function customVariables(custom: CustomColours): Record<string, string> {
  const card = isHexColour(custom.card) ? custom.card : undefined;
  const background = isHexColour(custom.background) ? custom.background : undefined;
  const text = isHexColour(custom.text) ? custom.text : undefined;
  const brand = isHexColour(custom.brand) ? custom.brand : undefined;
  const header = isHexColour(custom.header) ? custom.header : undefined;
  let variables: Record<string, string> = {};
  // Text needs something to be read against; when only the text colour is picked, it is checked against white or the card.
  const surfaceBase = card ?? background;
  if (background || card || text) {
    const base = surfaceBase ?? (text && isDarkColour(text) ? "#ffffff" : "#14151f");
    variables = surfaceVariables(background ?? base, card ?? base, text ?? readableOn(card ?? base));
  }
  if (brand) variables = { ...variables, ...brandVariables(brand, card ?? "#ffffff") };
  if (header) variables = { ...variables, "--header-bg": header, "--header-ink": readableOn(header) };
  return variables;
}

/** True when the colours picked had to be adjusted to stay readable (shown to the person as a short note). */
export function wasAdjusted(custom: CustomColours): boolean {
  const card = isHexColour(custom.card) ? custom.card : "#ffffff";
  const text = isHexColour(custom.text) ? custom.text : undefined;
  const brand = isHexColour(custom.brand) ? custom.brand : undefined;
  return (text !== undefined && contrastRatio(text, card) < MIN_CONTRAST) || (brand !== undefined && contrastRatio(brand, card) < MIN_CONTRAST);
}

/** Every variable name this module can set, so they can all be cleared when the person resets. */
export const CUSTOM_VARIABLE_NAMES: readonly string[] = [
  ...Object.keys(customVariables({ brand: "#123456", background: "#abcdef", card: "#fedcba", text: "#222222", header: "#334455" })),
];

// Colour helpers shared by the screens that draw their own tints.

/**
 * A see-through version of a colour. Accepts a hex colour ("#16A34A") or a CSS colour such as a theme variable ("var(--brand)"):
 * variables follow the active theme, so the tint changes with it.
 */
export function tint(colour: string, alpha: number): string {
  if (!colour.startsWith("#")) return `color-mix(in srgb, ${colour} ${Math.round(alpha * 100)}%, transparent)`;
  const value = colour.replace("#", "");
  const [red, green, blue] = [0, 2, 4].map(start => parseInt(value.slice(start, start + 2), 16));
  return `rgba(${red},${green},${blue},${alpha})`;
}

// The colours of the attendance screens, in one place so the summary strip, status tabs, table, month calendar, day panel and summary
// cards all agree. Soft tinted backgrounds are made from these with tint(); text and indicators use the colour itself.

export const PALETTE = {
  present: "#16A34A",     // green
  late: "#EA580C",        // orange
  half_day: "#2563EB",    // blue
  on_leave: "#9333EA",    // purple
  absent: "#DC2626",      // red
  incomplete: "#DB2777",  // pink
  not_marked: "#64748B",  // slate: "no data yet", deliberately not a warning colour
  weekly_off: "#94A3B8",  // light gray
  holiday: "#0891B2",     // teal
  future: "#CBD5E1",      // pale slate: a day that has not happened
  brand: "#7C3AED",       // AIRA purple
} as const;

export type PaletteKey = keyof typeof PALETTE;

/** "#16A34A", 0.16 -> "rgba(22,163,74,0.16)". */
export function tint(hex: string, alpha: number): string {
  const value = hex.replace("#", "");
  const [red, green, blue] = [0, 2, 4].map(start => parseInt(value.slice(start, start + 2), 16));
  return `rgba(${red},${green},${blue},${alpha})`;
}

/** The colour for an attendance status key as the API sends it ("present", "late", "no_record" ...). Unknown keys are light gray. */
export function statusColour(statusKey: string): string {
  if (statusKey === "no_record") return PALETTE.not_marked;
  return (PALETTE as Record<string, string>)[statusKey] ?? PALETTE.weekly_off;
}

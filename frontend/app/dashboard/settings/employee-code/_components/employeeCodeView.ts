import { tint } from "@/lib/colour";
// Types, rules, colours and totals for the Employee ID Ranges screen, kept apart so they can be tested alone.

export interface SeriesRow {
  employment_type:         string;
  employment_type_display: string;
  range_start:              number;
  range_end:                number;
  next_sequence:            number;
  format_description:       string;
  usage_percent:            number;
  is_exhausted:             boolean;
}

export type NumericField = "range_start" | "range_end" | "next_sequence";
export type RowErrors = Partial<Record<NumericField, string>>;
export type NumberDraft = Pick<SeriesRow, NumericField>;

export const BRAND = "var(--brand)";
export const MONO_FONT = "Menlo, Consolas, monospace";

/** Checks one worker type's three numbers, in the same words as before. `text` is what was typed; `form` is its parsed numbers. */
export function validateSeries(text: Record<NumericField, string>, form: NumberDraft): RowErrors {
  const errors: RowErrors = {};
  if (!/^\d+$/.test(text.range_start)) errors.range_start = "Required — whole number.";
  if (!/^\d+$/.test(text.range_end)) errors.range_end = "Required — whole number.";
  if (!/^\d+$/.test(text.next_sequence)) errors.next_sequence = "Required — whole number.";
  if (!errors.range_start && !errors.range_end && form.range_end <= form.range_start) errors.range_end = "Must be greater than range start.";
  if (!errors.range_start && !errors.range_end && !errors.next_sequence && (form.next_sequence <= form.range_start || form.next_sequence > form.range_end + 1)) {
    errors.next_sequence = `Must be between ${form.range_start + 1} and ${form.range_end} to issue a new ID (or ${form.range_end + 1}, which marks the range as fully used up).`;
  }
  return errors;
}

/** The first digit of the range: the digit that tells you the worker type at a glance. */
export const leadingDigit = (rangeStart: number): string => String(rangeStart).charAt(0);

export type Health = "healthy" | "nearing" | "exhausted";

export function healthOf(usagePercent: number, isExhausted: boolean): Health {
  if (isExhausted) return "exhausted";
  return usagePercent >= 90 ? "nearing" : "healthy";
}

export const HEALTH_STYLE: Record<Health, { colour: string; label: string; icon: string }> = {
  healthy:   { colour: "#16A34A", label: "Healthy",       icon: "ti-circle-check" },
  nearing:   { colour: "#EA580C", label: "Nearing limit", icon: "ti-alert-triangle" },
  exhausted: { colour: "#DC2626", label: "Exhausted",     icon: "ti-circle-x" },
};

/** The colour of the usage bar: green, orange from 70%, red from 90% or when used up. */
export function usageColour(usagePercent: number, isExhausted: boolean): string {
  if (isExhausted || usagePercent >= 90) return "#DC2626";
  return usagePercent >= 70 ? "#EA580C" : "#16A34A";
}

/** How many more IDs can still be issued from this range. */
export const idsLeft = (row: NumberDraft): number => Math.max(row.range_end - row.next_sequence + 1, 0);

export function summarise(rows: SeriesRow[]) {
  return {
    types: rows.length,
    idsLeft: rows.reduce((sum, row) => sum + idsLeft(row), 0),
    nearing: rows.filter(row => healthOf(row.usage_percent, row.is_exhausted) !== "healthy").length,
  };
}

/** The worker types whose ranges overlap another type's range (an ID could then belong to two types). Uses the numbers as they are being typed. */
export function findOverlaps(ranges: { type: string; start: number; end: number }[]): Set<string> {
  const clashing = new Set<string>();
  for (let first = 0; first < ranges.length; first += 1) {
    for (let second = first + 1; second < ranges.length; second += 1) {
      const a = ranges[first], b = ranges[second];
      if (a.start <= b.end && b.start <= a.end) { clashing.add(a.type); clashing.add(b.type); }
    }
  }
  return clashing;
}

export type SortKey = "name" | "range_start" | "usage";
export type SortDirection = "asc" | "desc";

export function sortRows(rows: SeriesRow[], key: SortKey, direction: SortDirection): SeriesRow[] {
  const sign = direction === "asc" ? 1 : -1;
  const value = (row: SeriesRow): number | string => key === "name" ? row.employment_type_display.toLowerCase() : key === "usage" ? row.usage_percent : row.range_start;
  return [...rows].sort((a, b) => {
    const left = value(a), right = value(b);
    return (left < right ? -1 : left > right ? 1 : 0) * sign;
  });
}

export { tint };

// Small pure helpers for the Settings > Permissions "One person" list: initials, a steady colour per person, and the split of a
// person's permissions by where they come from (everyone, their position, given to them personally).

import type { EmployeeAccessRow } from "@/types/orgStructure";

export function initialsOf(fullName: string): string {
  const words = fullName.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  const first = words[0][0];
  const last = words.length > 1 ? words[words.length - 1][0] : "";
  return (first + last).toUpperCase();
}

/** The same name always gives the same colour, so a person is recognisable down the list. */
export function hueOf(fullName: string): number {
  let hash = 0;
  for (const character of fullName) hash = (hash * 31 + character.charCodeAt(0)) % 360;
  return hash;
}

export interface AccessShare { everyone: number; position: number; extra: number }

/** The three parts of a person's permissions as whole percentages of their total (they add up to 100, or are all 0 for nobody). */
export function accessShare(row: Pick<EmployeeAccessRow, "from_baseline" | "from_seat" | "extra">): AccessShare {
  const sum = row.from_baseline + row.from_seat + row.extra;
  if (sum <= 0) return { everyone: 0, position: 0, extra: 0 };
  const everyone = Math.round((row.from_baseline / sum) * 100);
  const position = Math.round((row.from_seat / sum) * 100);
  return { everyone, position, extra: Math.max(0, 100 - everyone - position) };
}

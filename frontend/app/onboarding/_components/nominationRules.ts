// Pure rules for the Family & nomination step: ages, nominee totals per scheme, equal split, and hints about the family list.
// No React and no network, so every rule is unit-tested on its own. None of these rules blocks saving: the totals are guidance
// (the Review step is what refuses a scheme over 100%).

import { MINOR_AGE_YEARS, type FamilyEntry, type NomineeEntry } from "./familyNominationTypes";

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;

/** Whole years between a yyyy-mm-dd date of birth and `today`; null when the date is missing, malformed or in the future. */
export function ageInYears(isoDate: string, today: Date = new Date()): number | null {
  const match = ISO_DATE.exec(isoDate ?? "");
  if (!match) return null;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  let age = today.getFullYear() - year;
  if (today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day)) age -= 1;
  return age >= 0 ? age : null;
}

export function isMinor(isoDate: string, today: Date = new Date()): boolean {
  const age = ageInYears(isoDate, today);
  return age !== null && age < MINOR_AGE_YEARS;
}

/** "Asha Rao" -> "AR", "meera" -> "M", "" -> "?". */
export function initialsOf(name: string): string {
  const letters = name.trim().split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0].toUpperCase());
  return letters.length > 0 ? letters.join("") : "?";
}

export type SchemeState = "empty" | "short" | "complete" | "over";

export function sharesIn(nominees: NomineeEntry[], scheme: string): NomineeEntry[] {
  return nominees.filter(nominee => (nominee.scheme || "epf_eps") === scheme);
}

export function schemeTotal(nominees: NomineeEntry[], scheme: string): number {
  return sharesIn(nominees, scheme).reduce((sum, nominee) => sum + (Number(nominee.share_percentage) || 0), 0);
}

export function schemeState(total: number, nomineeCount: number): SchemeState {
  if (nomineeCount === 0) return "empty";
  if (total > 100) return "over";
  return total === 100 ? "complete" : "short";
}

/** Shares for `count` nominees that add up to exactly 100: 3 -> [34, 33, 33], with the extra points going to the first ones. */
export function equalShares(count: number): number[] {
  if (count <= 0) return [];
  const base = Math.floor(100 / count);
  const extra = 100 - base * count;
  return Array.from({ length: count }, (_, index) => base + (index < extra ? 1 : 0));
}

/** What is still unassigned in a scheme once this nominee's own share is left out (never negative). */
export function remainingFor(nominees: NomineeEntry[], scheme: string, excludingId: string): number {
  const others = sharesIn(nominees, scheme).filter(nominee => nominee.id !== excludingId);
  return Math.max(0, 100 - others.reduce((sum, nominee) => sum + (Number(nominee.share_percentage) || 0), 0));
}

/** Starting values for a quick-add button. A father is male and a mother is female; nothing else is guessed. */
export function presetFor(relationship: string): Partial<FamilyEntry> {
  if (relationship === "father") return { relationship, gender: "male" };
  if (relationship === "mother") return { relationship, gender: "female" };
  return { relationship };
}

const SINGLE_ROLES = new Set(["father", "mother"]);

/** Ids of the second and later "father" / "mother" entries, so the card can say another one is already listed. */
export function duplicateRoleIds(entries: FamilyEntry[]): Set<string> {
  const seen = new Set<string>();
  const duplicates = new Set<string>();
  for (const entry of entries) {
    if (!SINGLE_ROLES.has(entry.relationship)) continue;
    if (seen.has(entry.relationship)) duplicates.add(entry.id);
    seen.add(entry.relationship);
  }
  return duplicates;
}

/** People who can be picked as a nominee: anyone in the list who has been given a name. */
export function namedMembers(entries: FamilyEntry[]): FamilyEntry[] {
  return entries.filter(entry => entry.name.trim() !== "");
}

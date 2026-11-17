import type { OrgUnit, Position } from "@/types/orgStructure";

// Headcount figures for the Organization Management screen. Only ACTIVE positions count: a deactivated seat is neither
// filled nor vacant, so it must not make a unit look understaffed.

export interface UnitRollup {
  /** Seats directly in this unit. */
  ownTotal: number;
  ownFilled: number;
  /** Seats in this unit and every unit beneath it. */
  total: number;
  filled: number;
  /** The unit's chief seat (the head), if one is marked. */
  chief: Position | null;
}

export function vacantOf(rollup: UnitRollup): number {
  return rollup.total - rollup.filled;
}

export function rollupUnits(units: OrgUnit[], positions: Position[]): Map<string, UnitRollup> {
  const childrenOf = new Map<string | null, OrgUnit[]>();
  for (const unit of units) {
    const siblings = childrenOf.get(unit.parent) ?? [];
    siblings.push(unit);
    childrenOf.set(unit.parent, siblings);
  }
  const seatsOf = new Map<string, Position[]>();
  for (const position of positions) {
    if (!position.is_active) continue;
    const seats = seatsOf.get(position.org_unit) ?? [];
    seats.push(position);
    seatsOf.set(position.org_unit, seats);
  }

  const result = new Map<string, UnitRollup>();
  const visiting = new Set<string>();

  function compute(unit: OrgUnit): UnitRollup {
    const done = result.get(unit.id);
    if (done) return done;
    const seats = seatsOf.get(unit.id) ?? [];
    const own: UnitRollup = {
      ownTotal: seats.length,
      ownFilled: seats.filter(seat => seat.holder).length,
      total: seats.length,
      filled: seats.filter(seat => seat.holder).length,
      chief: seats.find(seat => seat.is_chief) ?? null,
    };
    // A parent loop in bad data must not recurse forever.
    if (visiting.has(unit.id)) return own;
    visiting.add(unit.id);
    for (const child of childrenOf.get(unit.id) ?? []) {
      const below = compute(child);
      own.total += below.total;
      own.filled += below.filled;
    }
    visiting.delete(unit.id);
    result.set(unit.id, own);
    return own;
  }

  for (const unit of units) compute(unit);
  return result;
}

export interface OrgAttention {
  /** Units that have seats but no seat marked as chief. */
  withoutChief: OrgUnit[];
  /** Units whose chief seat has nobody in it. */
  chiefVacant: OrgUnit[];
  /** Units with no seats and no sub-units. */
  empty: OrgUnit[];
  /** The units with the most vacant seats of their own, most first. */
  mostVacant: { unit: OrgUnit; vacant: number }[];
}

export function findAttention(units: OrgUnit[], rollups: Map<string, UnitRollup>, mostVacantLimit = 6): OrgAttention {
  const live = units.filter(unit => unit.is_active);
  const hasChildren = new Set(live.map(unit => unit.parent).filter((parent): parent is string => parent !== null));
  const withoutChief: OrgUnit[] = [];
  const chiefVacant: OrgUnit[] = [];
  const empty: OrgUnit[] = [];
  const vacantCounts: { unit: OrgUnit; vacant: number }[] = [];

  for (const unit of live) {
    const rollup = rollups.get(unit.id);
    if (!rollup) continue;
    if (rollup.ownTotal === 0 && !hasChildren.has(unit.id)) empty.push(unit);
    if (rollup.ownTotal > 0 && !rollup.chief) withoutChief.push(unit);
    if (rollup.chief && !rollup.chief.holder) chiefVacant.push(unit);
    const ownVacant = rollup.ownTotal - rollup.ownFilled;
    if (ownVacant > 0) vacantCounts.push({ unit, vacant: ownVacant });
  }
  vacantCounts.sort((first, second) => second.vacant - first.vacant || first.unit.name.localeCompare(second.unit.name));
  return { withoutChief, chiefVacant, empty, mostVacant: vacantCounts.slice(0, mostVacantLimit) };
}

/** Two-letter initials for an avatar. */
export function initialsOf(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0]).join("").toUpperCase();
}

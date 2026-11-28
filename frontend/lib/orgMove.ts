// Moving several employees to another org unit: each person needs a vacant seat (position) in the target unit.
// suggestSeats() pre-fills a sensible match so HR only has to review it: a seat with the person's own title first,
// then any vacant seat left over. Nobody gets the same seat twice; people left without a seat stay unmatched ("").

// The reason is saved as each new placement's note on the server, a 255-character column.
export const MOVE_REASON_MAX_LENGTH = 255;

export interface MovePerson { employeeId: string; title: string }
export interface VacantSeat { id: string; title: string }

const sameTitle = (left: string, right: string) => left.trim().toLowerCase() === right.trim().toLowerCase();

export function suggestSeats(people: MovePerson[], seats: VacantSeat[]): Record<string, string> {
  const taken = new Set<string>();
  const result: Record<string, string> = {};
  for (const person of people) {
    const match = seats.find(seat => !taken.has(seat.id) && sameTitle(seat.title, person.title));
    if (match) { taken.add(match.id); result[person.employeeId] = match.id; }
  }
  for (const person of people) {
    if (result[person.employeeId]) continue;
    const spare = seats.find(seat => !taken.has(seat.id));
    if (spare) taken.add(spare.id);
    result[person.employeeId] = spare?.id ?? "";
  }
  return result;
}

/** Today's date in the browser's own time zone as YYYY-MM-DD (what a date input and the server expect). */
export function todayIsoDate(now: Date = new Date()): string {
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

export interface UnitLike { id: string; name: string; is_active: boolean }
export interface SeatLike { org_unit: string; is_active: boolean; holder: string | null }

/** Org units a person could be moved into (not the one they are in), each labelled with its vacant-position count;
 *  units with a vacancy come first. Used by Perform Action > Org assignment. */
export function unitMoveOptions(units: UnitLike[], seats: SeatLike[], currentUnitId: string): { value: string; label: string; vacant: number }[] {
  return units
    .filter(unit => unit.is_active && unit.id !== currentUnitId)
    .map(unit => ({ unit, vacant: seats.filter(seat => seat.org_unit === unit.id && seat.is_active && !seat.holder).length }))
    .sort((left, right) => Number(right.vacant > 0) - Number(left.vacant > 0) || left.unit.name.localeCompare(right.unit.name))
    .map(({ unit, vacant }) => ({ value: unit.id, label: unit.name, vacant }));
}

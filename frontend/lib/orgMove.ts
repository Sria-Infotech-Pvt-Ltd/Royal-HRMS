// Moving several employees to another org unit: each person needs a vacant seat (position) in the target unit.
// suggestSeats() pre-fills a sensible match so HR only has to review it: a seat with the person's own title first,
// then any vacant seat left over. Nobody gets the same seat twice; people left without a seat stay unmatched ("").

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

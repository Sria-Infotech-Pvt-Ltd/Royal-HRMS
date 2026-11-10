// Subscription dates — calendar-month addition, the same rule as the backend
// (apps/tenants/pricing.py add_months / period_end): keep the day of the
// month, or use the last day of the target month when it is shorter.
// 31 Jan + 1 month → 28 Feb (29 Feb in a leap year). Never "+30 days".
// Dates are plain "YYYY-MM-DD" strings, so no time zone can shift them.

const MONTHS_IN_PERIOD: Record<string, number> = { monthly: 1, yearly: 12 };

function parse(iso: string): [number, number, number] | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return null;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  if (mo < 1 || mo > 12 || d < 1 || d > daysInMonth(y, mo)) return null;
  return [y, mo, d];
}

const pad = (n: number) => String(n).padStart(2, "0");

/** Days in `month` (1–12) of `year`, leap years included. */
export function daysInMonth(year: number, month: number): number {
  return new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/** "YYYY-MM-DD" plus `months` calendar months; "" for an invalid date. */
export function addMonths(iso: string, months: number): string {
  const p = parse(iso);
  if (!p) return "";
  const [y, mo, d] = p;
  const index = mo - 1 + months;
  const year = y + Math.floor(index / 12);
  const month = ((index % 12) + 12) % 12 + 1;
  return `${year}-${pad(month)}-${pad(Math.min(d, daysInMonth(year, month)))}`;
}

/** End of one billing period from `startsOn`; "" when no period is chosen. */
export function periodEnd(startsOn: string, billingPeriod: string): string {
  const months = MONTHS_IN_PERIOD[billingPeriod];
  return months ? addMonths(startsOn, months) : "";
}

/** Today's date on this computer (not UTC) as "YYYY-MM-DD". */
export function localToday(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

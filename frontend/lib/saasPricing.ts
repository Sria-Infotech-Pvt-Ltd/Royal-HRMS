// Subscription charge for one billing period — the same maths as the backend
// (apps/tenants/pricing.charge): price per employee × employees × months,
// rounded to paise, then GST added on top (or worked out of a GST-inclusive
// price), each rounded half-up. Integer paise with BigInt, so the browser
// estimate never differs from the server's figure by a paisa.

export interface Charge {
  months: number;
  subtotal: number;
  gst: number;
  total: number;
}

const MONTHS: Record<string, number> = { monthly: 1, yearly: 12 };

/** a / b rounded half-up, for non-negative a and positive b. */
const TWO = BigInt(2), BP = BigInt(10000);
const divRound = (a: bigint, b: bigint) => (TWO * a + b) / (TWO * b);

export function chargeFor(price: string | number, gstRate: string | number, gstInclusive: boolean,
  employees: number, billingPeriod: string): Charge {
  const months = MONTHS[billingPeriod || "monthly"] ?? 1;
  const priceP = BigInt(Math.round(Number(price) * 100));          // paise
  const rateBp = BigInt(Math.round(Number(gstRate) * 100));        // basis points (18% = 1800)
  const subtotal = priceP * BigInt(Math.max(Math.trunc(employees), 0)) * BigInt(months);
  const gst = gstInclusive ? divRound(subtotal * rateBp, BP + rateBp) : divRound(subtotal * rateBp, BP);
  const total = gstInclusive ? subtotal : subtotal + gst;
  return { months, subtotal: Number(subtotal) / 100, gst: Number(gst) / 100, total: Number(total) / 100 };
}

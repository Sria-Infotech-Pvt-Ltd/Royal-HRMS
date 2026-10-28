// Rupee amounts for settlement screens: Indian digit grouping, and a negative amount reads "-Rs 1,50,000" (never "₹-150000").

export function formatRupees(value: string | number): string {
  const amount = Math.round(Number(value));
  if (!Number.isFinite(amount)) return "—";
  const digits = Math.abs(amount).toLocaleString("en-IN", { maximumFractionDigits: 0 });
  return `${amount < 0 ? "-" : ""}Rs ${digits}`;
}

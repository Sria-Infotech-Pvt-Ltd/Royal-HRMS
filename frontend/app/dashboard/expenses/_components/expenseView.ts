import { tint } from "@/lib/colour";
// Colours, icons and small helpers for the Expenses page, kept apart from the screens so they can be tested alone.

export type ExpenseStatusKey = "pending" | "approved" | "rejected";

export const EXPENSE_COLOUR = {
  brand: "var(--brand)",
  pending: "#EA580C",
  approved: "#16A34A",
  rejected: "#DC2626",
  amount: "#2563EB",
} as const;

export const CATEGORY_STYLE: Record<string, { icon: string; colour: string }> = {
  travel:    { icon: "ti-plane",        colour: "#2563EB" },
  meals:     { icon: "ti-tools-kitchen-2", colour: "#EA580C" },
  equipment: { icon: "ti-device-laptop", colour: "var(--brand)" },
  other:     { icon: "ti-receipt",      colour: "#64748B" },
};

export const categoryStyle = (category: string) => CATEGORY_STYLE[category] ?? CATEGORY_STYLE.other;

/** "rgba" tint of a #RRGGBB colour. */
export { tint };

/** Short money for the stat cards: 1,50,000 -> "₹1.5L", 2,500 -> "₹2.5K". */
export function formatShortAmount(amount: number | string): string {
  const value = typeof amount === "string" ? parseFloat(amount) : amount;
  if (!Number.isFinite(value)) return "₹0";
  if (value >= 100_000) return `₹${(value / 100_000).toFixed(1)}L`;
  if (value >= 1_000) return `₹${(value / 1_000).toFixed(1)}K`;
  return `₹${value.toLocaleString("en-IN")}`;
}

export const formatFullAmount = (amount: number | string): string => {
  const value = typeof amount === "string" ? parseFloat(amount) : amount;
  return `₹${(Number.isFinite(value) ? value : 0).toLocaleString("en-IN")}`;
};

/** How many of the claims are in each state, as whole-number percentages that add to 100 (or all 0 when there are no claims). */
export function statusShares(pending: number, approved: number, rejected: number): Record<ExpenseStatusKey, number> {
  const total = pending + approved + rejected;
  if (total <= 0) return { pending: 0, approved: 0, rejected: 0 };
  const approvedShare = Math.round((approved / total) * 100);
  const rejectedShare = Math.round((rejected / total) * 100);
  const pendingShare = Math.max(100 - approvedShare - rejectedShare, 0);
  return { pending: pendingShare, approved: approvedShare, rejected: rejectedShare };
}

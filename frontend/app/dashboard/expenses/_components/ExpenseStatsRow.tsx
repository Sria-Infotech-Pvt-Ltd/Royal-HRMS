"use client";

// The five summary cards of the Expenses page and the bar showing how the claims split between pending, approved and rejected.

import { EXPENSE_COLOUR, formatFullAmount, formatShortAmount, statusShares, tint } from "./expenseView";

export interface ExpenseStatsData {
  total: number;
  pending: number;
  approved: number;
  rejected: number;
  total_amount: number;
  pending_amount: number;
  approved_amount: number;
}

interface Props { stats: ExpenseStatsData | null; loading: boolean }

interface CardSpec { label: string; icon: string; colour: string; value: string; sub?: string }

function StatCard({ spec, loading }: { spec: CardSpec; loading: boolean }) {
  return (
    <div className="card" style={{ padding: "16px 18px", position: "relative", overflow: "hidden", display: "flex", flexDirection: "column", gap: 4 }}>
      <span aria-hidden="true" style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: spec.colour }} />
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--on-variant)" }}>{spec.label}</span>
        <span aria-hidden="true" style={{ width: 34, height: 34, borderRadius: 10, display: "grid", placeItems: "center", fontSize: 18, background: tint(spec.colour, 0.14), color: spec.colour }}><i className={`ti ${spec.icon}`} /></span>
      </div>
      {loading
        ? <div aria-label="Loading" style={{ height: 28, width: 70, borderRadius: 8, marginTop: 4, background: "linear-gradient(90deg, #eceff6 25%, #f7f8fc 50%, #eceff6 75%)", backgroundSize: "300% 100%", animation: "ann-shimmer 1.4s linear infinite" }} />
        : <div style={{ fontSize: 28, fontWeight: 800, color: "var(--on-bg)", lineHeight: 1.15, fontVariantNumeric: "tabular-nums" }}>{spec.value}</div>}
      <div style={{ fontSize: 12, color: "var(--on-variant)", minHeight: 16 }}>{spec.sub ?? ""}</div>
    </div>
  );
}

export default function ExpenseStatsRow({ stats, loading }: Props) {
  const pending = stats?.pending ?? 0, approved = stats?.approved ?? 0, rejected = stats?.rejected ?? 0;
  const cards: CardSpec[] = [
    { label: "Total Claims", icon: "ti-file-invoice", colour: EXPENSE_COLOUR.brand, value: String(stats?.total ?? 0), sub: "All time" },
    { label: "Pending", icon: "ti-clock", colour: EXPENSE_COLOUR.pending, value: String(pending), sub: stats && stats.pending_amount > 0 ? `${formatFullAmount(stats.pending_amount)} waiting` : "Nothing waiting" },
    { label: "Approved", icon: "ti-check", colour: EXPENSE_COLOUR.approved, value: String(approved), sub: stats && stats.approved_amount > 0 ? `${formatFullAmount(stats.approved_amount)} approved` : "None yet" },
    { label: "Rejected", icon: "ti-x", colour: EXPENSE_COLOUR.rejected, value: String(rejected), sub: rejected ? "See the reason in each claim" : "None" },
    { label: "Total Claimed", icon: "ti-cash", colour: EXPENSE_COLOUR.amount, value: formatShortAmount(stats?.total_amount ?? 0), sub: stats ? formatFullAmount(stats.total_amount) : "" },
  ];
  const shares = statusShares(pending, approved, rejected);
  const hasClaims = pending + approved + rejected > 0;

  return (
    <>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 14, marginBottom: 14 }}>
        {cards.map(spec => <StatCard key={spec.label} spec={spec} loading={loading && !stats} />)}
      </div>
      <div className="card" style={{ padding: "14px 18px", marginBottom: 18 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8, marginBottom: 10 }}>
          <span style={{ fontSize: 13.5, fontWeight: 700, color: "var(--on-bg)" }}>How your claims stand</span>
          <span style={{ display: "flex", gap: 14, fontSize: 12, color: "var(--on-variant)" }}>
            {(["approved", "pending", "rejected"] as const).map(key => (
              <span key={key} style={{ display: "inline-flex", alignItems: "center", gap: 6, textTransform: "capitalize" }}>
                <span aria-hidden="true" style={{ width: 9, height: 9, borderRadius: "50%", background: EXPENSE_COLOUR[key] }} />{key} {shares[key]}%
              </span>
            ))}
          </span>
        </div>
        <div role="img" aria-label={hasClaims ? `${shares.approved}% approved, ${shares.pending}% pending, ${shares.rejected}% rejected` : "No claims yet"} style={{ display: "flex", height: 10, borderRadius: 999, overflow: "hidden", background: "var(--bg-low)" }}>
          {(["approved", "pending", "rejected"] as const).map(key => shares[key] > 0 && <span key={key} style={{ width: `${shares[key]}%`, background: EXPENSE_COLOUR[key], transition: "width .4s ease" }} />)}
        </div>
      </div>
    </>
  );
}

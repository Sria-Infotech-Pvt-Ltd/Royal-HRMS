"use client";

// "Recent Expense Claims": the latest claims as rows with a coloured category icon, the title, date, receipt count, amount and a status
// pill, with buttons to show only one status. Clicking a row opens the claim.

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import { EXPENSE_COLOUR, categoryStyle, formatFullAmount, tint, type ExpenseStatusKey } from "./expenseView";
import type { Expense } from "./ExpenseClaims";

interface Props {
  claims: Expense[];
  loading: boolean;
  categoryLabel: Record<string, string>;
  formatDate: (iso: string) => string;
  onOpen: (expense: Expense) => void;
  onNew: () => void;
  /** How many to show at most. */
  limit: number;
}

type Filter = "all" | ExpenseStatusKey;
const FILTERS: { key: Filter; label: string; colour: string }[] = [
  { key: "all", label: "All", colour: EXPENSE_COLOUR.brand },
  { key: "pending", label: "Pending", colour: EXPENSE_COLOUR.pending },
  { key: "approved", label: "Approved", colour: EXPENSE_COLOUR.approved },
  { key: "rejected", label: "Rejected", colour: EXPENSE_COLOUR.rejected },
];
const SHIMMER = { background: "linear-gradient(90deg, #eceff6 25%, #f7f8fc 50%, #eceff6 75%)", backgroundSize: "300% 100%", animation: "ann-shimmer 1.4s linear infinite" } as const;

export default function ExpenseRecentList({ claims, loading, categoryLabel, formatDate, onOpen, onNew, limit }: Props) {
  const t = useT();
  const [filter, setFilter] = useState<Filter>("all");
  const visible = claims.filter(claim => filter === "all" || claim.status === filter).slice(0, limit);
  const countOf = (key: Filter) => key === "all" ? claims.length : claims.filter(claim => claim.status === key).length;

  return (
    <section aria-label={t("Recent expense claims")} className="card" style={{ padding: 0, overflow: "hidden" }}>
      <header style={{ padding: "14px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 10, borderBottom: "1px solid var(--outline-v)" }}>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "var(--on-bg)", display: "flex", alignItems: "center", gap: 8 }}>
          <i className="ti ti-receipt" aria-hidden="true" style={{ color: EXPENSE_COLOUR.brand }} /> {t("Recent Expense Claims")}
        </h3>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {/* The page header no longer has a Submit button, so claims already on the list still need a way to start a new one. */}
          {claims.length > 0 && <button className="btn btn-filled btn-sm" type="button" onClick={onNew}><i className="ti ti-plus" /> {t("New expense")}</button>}
          <a href="/dashboard/my-requests?tab=expense" className="btn btn-ghost btn-sm">{t("View All Expense Claims")} <i className="ti ti-arrow-right" /></a>
        </div>
      </header>

      {claims.length > 0 && (
        <div role="group" aria-label={t("Show claims")} style={{ display: "flex", gap: 6, flexWrap: "wrap", padding: "12px 20px", background: "var(--bg-low)", borderBottom: "1px solid var(--outline-v)" }}>
          {FILTERS.map(option => {
            const selected = filter === option.key;
            return (
              <button key={option.key} type="button" aria-pressed={selected} onClick={() => setFilter(option.key)}
                style={{ padding: "6px 13px", borderRadius: 999, fontSize: 12.5, fontWeight: 700, cursor: "pointer", transition: "all .15s ease", border: `1.5px solid ${selected ? option.colour : "var(--outline-v)"}`, background: selected ? tint(option.colour, 0.12) : "var(--surface)", color: selected ? option.colour : "var(--on-variant)" }}>
                {t(option.label)} <span style={{ opacity: 0.75 }}>{countOf(option.key)}</span>
              </button>
            );
          })}
        </div>
      )}

      {loading && (
        <div>{[0, 1, 2].map(row => <div key={row} aria-label={t("Loading")} style={{ display: "flex", gap: 14, alignItems: "center", padding: "14px 20px", borderBottom: "1px solid var(--outline-v)" }}>
          <div style={{ ...SHIMMER, width: 42, height: 42, borderRadius: 12 }} /><div style={{ flex: 1 }}><div style={{ ...SHIMMER, height: 13, width: "40%", borderRadius: 6 }} /><div style={{ ...SHIMMER, height: 11, width: "25%", borderRadius: 6, marginTop: 8 }} /></div><div style={{ ...SHIMMER, height: 16, width: 70, borderRadius: 6 }} />
        </div>)}</div>
      )}

      {!loading && claims.length === 0 && (
        <div style={{ padding: "44px 20px", textAlign: "center" }}>
          <span aria-hidden="true" style={{ width: 64, height: 64, borderRadius: 20, display: "inline-grid", placeItems: "center", fontSize: 32, background: tint(EXPENSE_COLOUR.brand, 0.1), color: EXPENSE_COLOUR.brand }}><i className="ti ti-wallet" /></span>
          <h3 style={{ margin: "12px 0 4px", fontSize: 16, fontWeight: 800, color: "var(--on-bg)" }}>{t("No expense claims yet")}</h3>
          <p style={{ margin: "0 0 16px", fontSize: 13, color: "var(--on-variant)" }}>{t("Submit a new expense to get started. Attach your receipt for faster approval.")}</p>
          <button className="btn btn-filled" type="button" onClick={onNew}><i className="ti ti-plus" /> {t("Submit your first expense")}</button>
        </div>
      )}

      {!loading && claims.length > 0 && visible.length === 0 && (
        <div style={{ padding: "32px 20px", textAlign: "center", fontSize: 13.5, color: "var(--on-variant)" }}>{t("No {status} claims among your recent ones.", { status: t(filter) })}</div>
      )}

      {!loading && visible.map(claim => {
        const category = categoryStyle(claim.category);
        const status = EXPENSE_COLOUR[claim.status] ?? EXPENSE_COLOUR.pending;
        const receipts = claim.receipts?.length ?? 0;
        return (
          <div key={claim.expense_number} role="button" tabIndex={0} onClick={() => onOpen(claim)}
            onKeyDown={event => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onOpen(claim); } }}
            onMouseEnter={event => { event.currentTarget.style.background = tint(EXPENSE_COLOUR.brand, 0.04); }} onMouseLeave={event => { event.currentTarget.style.background = "transparent"; }}
            style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 20px", borderBottom: "1px solid var(--outline-v)", cursor: "pointer", transition: "background .15s ease" }}>
            <span aria-hidden="true" style={{ width: 42, height: 42, borderRadius: 12, flexShrink: 0, display: "grid", placeItems: "center", fontSize: 21, background: tint(category.colour, 0.14), color: category.colour }}><i className={`ti ${category.icon}`} /></span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: "var(--on-bg)" }}>{t(categoryLabel[claim.category] ?? claim.category)}</div>
              <div style={{ fontSize: 12.5, color: "var(--on-variant)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {claim.title} · {formatDate(claim.expense_date)}{receipts > 0 && <> · <i className="ti ti-paperclip" aria-hidden="true" /> {receipts === 1 ? t("{count} receipt", { count: receipts }) : t("{count} receipts", { count: receipts })}</>}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontWeight: 800, fontSize: 15, color: "var(--on-bg)", fontVariantNumeric: "tabular-nums" }}>{formatFullAmount(claim.amount)}</div>
              <span style={{ display: "inline-block", marginTop: 3, fontSize: 11.5, fontWeight: 700, padding: "2px 10px", borderRadius: 999, textTransform: "capitalize", background: tint(status, 0.14), color: status }}>{t(claim.status)}</span>
            </div>
            <i className="ti ti-chevron-right" aria-hidden="true" style={{ color: "var(--outline)" }} />
          </div>
        );
      })}
    </section>
  );
}

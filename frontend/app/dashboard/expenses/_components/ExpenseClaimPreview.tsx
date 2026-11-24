"use client";

// The live "Your claim" card beside the form: what the claim will look like, and which required parts are still missing.

import { useT } from "@/hooks/useI18n";
import { EXPENSE_COLOUR, categoryStyle, formatFullAmount, tint } from "./expenseView";

interface Props {
  categoryLabel: string | null;
  category: string;
  amount: number;
  dateLabel: string | null;
  purpose: string;
  receiptCount: number;
}

export default function ExpenseClaimPreview({ categoryLabel, category, amount, dateLabel, purpose, receiptCount }: Props) {
  const t = useT();
  const style = categoryStyle(category);
  const colour = category ? style.colour : EXPENSE_COLOUR.brand;
  const checks = [
    { label: t("Category"), ok: Boolean(categoryLabel) },
    { label: t("Date"), ok: Boolean(dateLabel) },
    { label: t("Amount"), ok: amount > 0 },
    { label: t("Receipt"), ok: receiptCount > 0 },
  ];
  const missing = checks.filter(check => !check.ok).length;

  return (
    <aside aria-label={t("Your claim")} aria-live="polite" style={{ borderRadius: 18, overflow: "hidden", border: `1px solid ${tint(colour, 0.3)}`, background: "var(--surface)", boxShadow: `0 8px 24px ${tint(colour, 0.12)}` }}>
      <div style={{ padding: "18px 18px 16px", background: `linear-gradient(135deg, ${tint(colour, 0.16)} 0%, ${tint(colour, 0.04)} 100%)` }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span aria-hidden="true" style={{ width: 46, height: 46, borderRadius: 14, display: "grid", placeItems: "center", fontSize: 24, color: "#fff", background: colour, transition: "background .2s ease" }}>
            <i className={`ti ${category ? style.icon : "ti-receipt-2"}`} />
          </span>
          <div>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--on-variant)" }}>{t("Your claim")}</div>
            <div style={{ fontSize: 15, fontWeight: 800, color: "var(--on-bg)" }}>{categoryLabel ?? t("No category yet")}</div>
          </div>
        </div>
        <div style={{ fontSize: 32, fontWeight: 800, color: colour, marginTop: 14, fontVariantNumeric: "tabular-nums", lineHeight: 1.1 }}>{amount > 0 ? formatFullAmount(amount) : "₹0"}</div>
      </div>
      <dl style={{ margin: 0, padding: "14px 18px", display: "grid", gridTemplateColumns: "auto 1fr", gap: "8px 14px", fontSize: 13 }}>
        <dt style={{ color: "var(--on-variant)" }}>{t("Date")}</dt><dd style={{ margin: 0, fontWeight: 600, color: "var(--on-bg)", textAlign: "right" }}>{dateLabel ?? "—"}</dd>
        <dt style={{ color: "var(--on-variant)" }}>{t("Receipts")}</dt><dd style={{ margin: 0, fontWeight: 600, color: "var(--on-bg)", textAlign: "right" }}>{receiptCount}</dd>
        <dt style={{ color: "var(--on-variant)" }}>{t("Purpose")}</dt><dd style={{ margin: 0, fontWeight: 500, color: "var(--on-bg)", textAlign: "right", overflow: "hidden", textOverflow: "ellipsis", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical" }}>{purpose.trim() || "—"}</dd>
      </dl>
      <div style={{ padding: "12px 18px 16px", borderTop: "1px solid var(--outline-v)" }}>
        <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 8, color: missing === 0 ? EXPENSE_COLOUR.approved : "var(--on-variant)" }}>
          {missing === 0 ? t("Ready to submit") : missing === 1 ? t("{count} required part left", { count: missing }) : t("{count} required parts left", { count: missing })}
        </div>
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexWrap: "wrap", gap: 6 }}>
          {checks.map(check => (
            <li key={check.label} data-done={check.ok} style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, fontWeight: 700, padding: "3px 10px", borderRadius: 999, background: tint(check.ok ? EXPENSE_COLOUR.approved : "#64748B", 0.12), color: check.ok ? EXPENSE_COLOUR.approved : "#64748B" }}>
              <i className={`ti ${check.ok ? "ti-circle-check" : "ti-circle-dashed"}`} aria-hidden="true" />{check.label}
            </li>
          ))}
        </ul>
        <p style={{ margin: "12px 0 0", fontSize: 11.5, color: "var(--on-variant)" }}><i className="ti ti-info-circle" aria-hidden="true" /> {t("Sent for approval. Approved expenses are reimbursed in the next payroll cycle.")}</p>
      </div>
    </aside>
  );
}

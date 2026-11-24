"use client";

// The four summary cards above the leave types.

import { useT } from "@/hooks/useI18n";
import { summarise, tint, type LeavePolicy } from "./leaveTypeView";

export default function LeaveTypeStats({ list, loading }: { list: LeavePolicy[]; loading: boolean }) {
  const t = useT();
  const totals = summarise(list);
  const cards = [
    { icon: "ti-beach", colour: "var(--brand)", label: t("Total Types"), value: totals.total, sub: t("Configured") },
    { icon: "ti-circle-check", colour: "#16A34A", label: t("Active"), value: totals.active, sub: totals.total - totals.active > 0 ? t("{count} inactive", { count: totals.total - totals.active }) : t("All in use") },
    { icon: "ti-repeat", colour: "#EA580C", label: t("Carry Forward"), value: totals.carryForward, sub: t("Can roll over") },
    { icon: "ti-calendar-stats", colour: "#2563EB", label: t("Days a Year"), value: totals.annualDays, sub: t("Across active types") },
  ];
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 14, marginBottom: 20 }}>
      {cards.map(card => (
        <div key={card.label} className="card" style={{ padding: "16px 18px", position: "relative", overflow: "hidden" }}>
          <span aria-hidden="true" style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: card.colour }} />
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <span style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--on-variant)" }}>{card.label}</span>
            <span aria-hidden="true" style={{ width: 34, height: 34, borderRadius: 10, display: "grid", placeItems: "center", fontSize: 18, background: tint(card.colour, 0.14), color: card.colour }}><i className={`ti ${card.icon}`} /></span>
          </div>
          <div style={{ fontSize: 28, fontWeight: 800, color: "var(--on-bg)", marginTop: 4, lineHeight: 1.15, fontVariantNumeric: "tabular-nums", minHeight: 32 }}>
            {loading ? <span aria-label={t("Loading")} style={{ display: "inline-block", height: 26, width: 56, borderRadius: 8, background: "linear-gradient(90deg, #eceff6 25%, #f7f8fc 50%, #eceff6 75%)", backgroundSize: "300% 100%", animation: "ann-shimmer 1.4s linear infinite" }} /> : card.value}
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{card.sub}</div>
        </div>
      ))}
    </div>
  );
}

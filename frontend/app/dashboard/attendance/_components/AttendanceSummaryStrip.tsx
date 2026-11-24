"use client";

// One slim strip with today's five numbers, in place of four tall cards. Each number is a button that jumps to the matching rows.

import type { StatCards } from "@/types/attendance";
import { useT } from "@/hooks/useI18n";
import { PALETTE } from "./attendancePalette";
import { describeStatsFailure } from "./statsFailure";

interface Props {
  cards: StatCards | undefined;
  onJump: (status: string) => void;
  /** Set when the request for the numbers failed: the HTTP status (null = no answer). Shows the reason and a Try again button. */
  failure?: { status: number | null; onRetry: () => void } | null;
}

interface Item { status: string; label: string; value: number | undefined; sub: string; colour: string }

export default function AttendanceSummaryStrip({ cards, onJump, failure }: Props) {
  const t = useT();
  if (failure && !cards) {
    return (
      <div className="card" role="alert" style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", padding: "14px 20px", marginBottom: 20 }}>
        <i className="ti ti-alert-triangle" aria-hidden="true" style={{ color: PALETTE.late, fontSize: 20 }} />
        <span style={{ flex: 1, minWidth: 220 }}>
          <span style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{t("Could not load today's numbers")}</span>
          <span style={{ display: "block", fontSize: 12, color: "var(--on-variant)" }}>{describeStatsFailure(failure.status, t)}</span>
        </span>
        <button type="button" className="btn btn-ghost btn-sm" onClick={failure.onRetry}>{t("Try again")}</button>
      </div>
    );
  }
  const total = cards?.total_employees ?? 0;
  const items: Item[] = [
    { status: "present", label: t("Present"), value: cards?.present_today, sub: t("of {total} employees, incl. late", { total }), colour: PALETTE.present },
    { status: "wfh", label: t("Work from home"), value: cards?.wfh, sub: t("Present, working remotely"), colour: PALETTE.wfh },
    { status: "late", label: t("Late"), value: cards?.late_arrivals, sub: t("{full} full day · {short} short hours", { full: cards?.late_full_day ?? 0, short: cards?.late_short ?? 0 }), colour: PALETTE.late },
    { status: "absent", label: t("Absent"), value: cards?.absent, sub: t("No check-in recorded"), colour: PALETTE.absent },
    { status: "on_leave", label: t("On leave"), value: cards?.on_leave, sub: t("Approved leave"), colour: PALETTE.on_leave },
  ];
  return (
    <div className="card" role="group" aria-label={t("Today at a glance")} style={{ display: "flex", flexWrap: "wrap", marginBottom: 20 }}>
      {items.map((item, index) => (
        <button
          key={item.status} type="button" onClick={() => onJump(item.status)} title={t("Show {label}", { label: item.label.toLowerCase() })}
          style={{
            flex: "1 1 180px", display: "flex", alignItems: "center", gap: 14, padding: "14px 20px", textAlign: "left", background: "none", border: 0, cursor: "pointer",
            borderLeft: index === 0 ? "none" : "1px solid var(--outline-v)",
          }}
        >
          <span style={{ fontSize: 28, fontWeight: 800, lineHeight: 1, color: item.colour, fontVariantNumeric: "tabular-nums" }}>{item.value ?? "—"}</span>
          <span>
            <span style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{item.label}</span>
            <span style={{ display: "block", fontSize: 11.5, color: "var(--on-variant)" }}>{item.sub}</span>
          </span>
        </button>
      ))}
    </div>
  );
}

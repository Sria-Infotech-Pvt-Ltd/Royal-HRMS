"use client";

// This is the one screen allowed its own dark accent treatment, distinct
// from the bright purple gradient used on the ESS Home banner (HomeBanner.tsx
// uses `linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%)`,
// which adapts with the theme) — a darker navy-to-purple gradient specifically
// for the payslip hero, per the strict-replication spec for this screen only.
// Unlike the Home banner, this gradient is intentionally NOT theme-driven, so
// the literal white text below is correct here — var(--on-primary) would
// flip to near-black in dark mode and disappear against this fixed-dark card.
// Do not copy this gradient onto other screens.
const HERO_GRADIENT = "linear-gradient(135deg, #1e1b3a 0%, #4c1d95 100%)";

import type { ApiPayslip } from "./types";
import { INR, fmtMonth } from "./types";

interface Props {
  slip: ApiPayslip;
  bankName: string | null;
  bankMasked: string;
  pfNumber: string | null;
  gross: number;
  deductions: number;
  paidDays: number;
  totalDays: number;
  net: number;
  payDateLabel: string;
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl p-3" style={{ background: "rgba(255,255,255,0.08)" }}>
      <div className="text-[10px] uppercase tracking-wider" style={{ color: "rgba(255,255,255,0.6)" }}>{label}</div>
      <div className="text-sm font-bold mt-1" style={{ color: "#fff" }}>{value}</div>
    </div>
  );
}

export default function PayslipHero({
  slip, bankName, bankMasked, pfNumber, gross, deductions, paidDays, totalDays, net, payDateLabel,
}: Props) {
  const creditedParts = [`Credited on ${payDateLabel}`, bankName, bankMasked !== "—" ? `A/c ${bankMasked}` : null]
    .filter(Boolean);

  return (
    <div className="rounded-2xl p-6" style={{ background: HERO_GRADIENT }}>
      <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "rgba(255,255,255,0.65)" }}>
        Net pay · {fmtMonth(slip.cycle_start)}
      </div>
      <div className="text-4xl font-extrabold mt-1" style={{ color: "#fff" }}>{INR(net)}</div>
      <div className="text-xs mt-2" style={{ color: "rgba(255,255,255,0.7)" }}>{creditedParts.join(" · ")}</div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
        <StatTile label="Gross earnings" value={INR(gross)} />
        <StatTile label="Total deductions" value={INR(deductions)} />
        <StatTile label="Paid days" value={`${paidDays}/${totalDays}`} />
        <StatTile label="PF number" value={pfNumber || "—"} />
      </div>
    </div>
  );
}

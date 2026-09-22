"use client";

import { INR } from "./types";

function YtdTile({ label, value, caption }: { label: string; value: string; caption: string }) {
  return (
    <div className="rounded-xl px-4 py-3 border" style={{ borderColor: "var(--outline-v)", background: "var(--bg-low)" }}>
      <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--outline)" }}>{label}</div>
      <div className="text-lg font-extrabold mt-1" style={{ color: "var(--on-bg)" }}>{value}</div>
      <div className="text-[11px] mt-0.5" style={{ color: "var(--on-variant)" }}>{caption}</div>
    </div>
  );
}

interface Props {
  monthRangeLabel: string;
  ytdGross: number;
  ytdNet: number;
  ytdIncomeTax: number;
  periodCount: number;
}

export default function PayslipYtdSummary({ monthRangeLabel, ytdGross, ytdNet, ytdIncomeTax, periodCount }: Props) {
  return (
    <div className="card">
      <div className="px-4 py-3 border-b" style={{ borderColor: "var(--outline-v)" }}>
        <div className="text-sm font-bold" style={{ color: "var(--on-bg)" }}>Year-to-date summary</div>
        <div className="text-xs mt-0.5" style={{ color: "var(--on-variant)" }}>{monthRangeLabel} cumulative payroll.</div>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 p-4">
        <YtdTile label="Gross earnings" value={INR(ytdGross)} caption={`${periodCount} payroll period${periodCount === 1 ? "" : "s"}`} />
        <YtdTile label="Income tax" value={INR(ytdIncomeTax)} caption="Deducted to date" />
        <YtdTile label="Net pay" value={INR(ytdNet)} caption="Credited to date" />
      </div>
    </div>
  );
}

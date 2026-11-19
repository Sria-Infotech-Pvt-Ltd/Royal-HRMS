"use client";

// The right-hand side of the Home hero once the day is finished: a "Today completed" panel with the day's summary,
// instead of a big Punch in button. Punching in again (back from a break, a late shift) stays one small link away.
import type { ReactNode } from "react";
import { tr } from "@/lib/i18n/tr";
import { formatWorked } from "./dayComplete";

interface Props {
  clockInTime: string | null;
  clockOutTime: string | null;
  /** Worked time as the server sends it, "HH:MM". */
  workedHours: string;
  /** "Next shift starts 09:00", or null when no shift is configured. */
  nextShift: string | null;
  /** The small "Punch in again" control; omitted when someone else is viewing this workspace. */
  punchAgain?: ReactNode;
}

const DONE_CSS = `
.ess-done{display:flex;flex-direction:column;align-items:flex-end;gap:8px;text-align:right}
.ess-done-card{display:flex;align-items:center;gap:12px;padding:10px 14px;border-radius:14px;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.28);animation:essDonePop .45s cubic-bezier(.2,.9,.3,1.2)}
.ess-done-tick{flex:none;display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;border-radius:50%;font-size:20px;color:#fff;background:#16a34a;box-shadow:0 0 0 4px rgba(22,163,74,.28)}
.ess-done-card b{display:block;font-size:15px;color:#fff}
.ess-done-card span{display:block;margin-top:2px;font-size:11.5px;color:#ddd6fe;white-space:nowrap}
.ess-done-total{font-size:20px!important;font-weight:800;color:#fff!important;margin-top:0!important}
.ess-done-note{font-size:11px;color:#ddd6fe}
.ess-done-again{border:none;background:none;padding:0;font:inherit;font-size:11px;color:#ddd6fe;text-decoration:underline;text-underline-offset:2px;cursor:pointer}
.ess-done-again:hover{color:#fff}
@keyframes essDonePop{0%{transform:scale(.92);opacity:0}100%{transform:scale(1);opacity:1}}
@media(prefers-reduced-motion:reduce){.ess-done-card{animation:none}}
@media(max-width:700px){.ess-done{align-items:flex-start;text-align:left}.ess-done-card span{white-space:normal}}
`;

export default function HomeDayComplete({ clockInTime, clockOutTime, workedHours, nextShift, punchAgain }: Props) {
  return (
    <div className="ess-done" role="status">
      <style>{DONE_CSS}</style>
      <div className="ess-done-card">
        <span className="ess-done-tick" aria-hidden="true"><i className="ti ti-check" /></span>
        <div>
          <b>{tr("Today completed")}</b>
          <span>{tr("In {in} · Out {out}", { in: clockInTime ?? "—", out: clockOutTime ?? "—" })}</span>
        </div>
        <div style={{ paddingLeft: 6 }}>
          <span className="ess-done-total">{formatWorked(workedHours)}</span>
          <span>{tr("worked today")}</span>
        </div>
      </div>
      <div className="ess-done-note">{nextShift ? `${tr("See you tomorrow")} · ${nextShift}` : tr("See you tomorrow")}</div>
      {punchAgain}
    </div>
  );
}

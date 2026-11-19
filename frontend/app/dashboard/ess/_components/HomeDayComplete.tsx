"use client";

// The right-hand side of the Home hero once the day is finished: a "Day Complete" button in the same white style as the Punch button,
// and one quiet line with the day's times. Just after a punch-out a small sparkle plays once. There is one punch in and one
// punch out a day, so nothing here offers another punch.
import type { CSSProperties } from "react";
import { tr } from "@/lib/i18n/tr";

interface Props {
  /** "09:02 → 18:10 · 8h 52m", shown as a muted line; omitted when the times are not known. */
  summary?: string | null;
  /** True only right after the employee punched out in this visit: plays the sparkle once. */
  celebrate?: boolean;
}

// Ten sparks flying out of the pill: [x, y] end offsets in px and a colour each.
const SPARKS: { x: number; y: number; colour: string }[] = [
  { x: -70, y: -34, colour: "#a7f3d0" }, { x: -40, y: -52, colour: "#ddd6fe" }, { x: -8, y: -58, colour: "#ffffff" },
  { x: 30, y: -54, colour: "#a7f3d0" }, { x: 66, y: -38, colour: "#ddd6fe" }, { x: 84, y: -6, colour: "#ffffff" },
  { x: -86, y: -4, colour: "#ddd6fe" }, { x: 52, y: 40, colour: "#a7f3d0" }, { x: -52, y: 42, colour: "#ffffff" },
  { x: 8, y: 52, colour: "#ddd6fe" },
];

const DONE_CSS = `
.ess-done{display:flex;flex-direction:column;align-items:flex-end;gap:9px}
.ess-done-stage{position:relative}
.ess-done .ess-done-btn{cursor:default;animation:essDonePop .4s cubic-bezier(.2,.9,.3,1.2)}
.ess-done .ess-done-btn:active{transform:none}
.ess-done-btn i{font-size:18px;color:#16a34a;animation:essTickPop .5s cubic-bezier(.2,1.4,.4,1) .15s both}
.ess-done-summary{font-size:11px;color:#c4b5fd;font-variant-numeric:tabular-nums;letter-spacing:.01em}
.ess-spark{position:absolute;left:50%;top:50%;width:7px;height:7px;margin:-3px 0 0 -3px;border-radius:50%;background:var(--spark);pointer-events:none;opacity:0;animation:essSpark .95s ease-out forwards}
@keyframes essDonePop{0%{transform:scale(.92);opacity:0}100%{transform:scale(1);opacity:1}}
@keyframes essTickPop{0%{transform:scale(0) rotate(-40deg)}100%{transform:scale(1) rotate(0)}}
@keyframes essSpark{0%{transform:translate(0,0) scale(.4);opacity:1}100%{transform:translate(var(--sx),var(--sy)) scale(1);opacity:0}}
@media(prefers-reduced-motion:reduce){.ess-done .ess-done-btn,.ess-done-btn i{animation:none}.ess-spark{display:none}}
@media(max-width:900px){.ess-done{align-items:flex-start}}
`;

export default function HomeDayComplete({ summary, celebrate = false }: Props) {
  return (
    <div className="ess-done" role="status">
      <style>{DONE_CSS}</style>
      <div className="ess-done-stage">
        <div className="btn ess-done-btn" title={summary ?? undefined}><i className="ti ti-circle-check-filled" aria-hidden="true" /> {tr("Day Complete")}</div>
        {celebrate && SPARKS.map((spark, index) => (
          <span key={index} className="ess-spark" aria-hidden="true" style={{ "--spark": spark.colour, "--sx": `${spark.x}px`, "--sy": `${spark.y}px`, animationDelay: `${index * 25}ms` } as CSSProperties} />
        ))}
      </div>
      {summary && <div className="ess-done-summary">{summary}</div>}
    </div>
  );
}

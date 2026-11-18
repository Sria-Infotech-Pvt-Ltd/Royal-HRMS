"use client";

// The month at a glance as eight cards: the attendance percentage (with a progress ring and a bar of how the working days were spent),
// then present, absent, late, half-day and leave days, total hours and average hours. Counts and hours are the backend's own month
// numbers; the percentage and the average are worked out from the same days the calendar shows.

import { PALETTE, tint } from "./attendancePalette";
import { STATUS_META, type BarSegment, type MonthInsights, type MonthStats } from "./monthView";

interface Props {
  insights: MonthInsights;
  stats: MonthStats;
  segments: BarSegment[];
}

interface CardSpec { label: string; value: string; unit?: string; icon: string; colour: string; hint?: string }

function StatCard({ spec }: { spec: CardSpec }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", borderRadius: 14, border: `1px solid ${tint(spec.colour, 0.22)}`,
      background: `linear-gradient(135deg, ${tint(spec.colour, 0.12)} 0%, var(--surface) 70%)`,
    }}>
      <span aria-hidden="true" style={{ width: 38, height: 38, borderRadius: 11, display: "grid", placeItems: "center", background: tint(spec.colour, 0.18), color: spec.colour, fontSize: 19, flexShrink: 0 }}>
        <i className={`ti ${spec.icon}`} />
      </span>
      <span style={{ minWidth: 0 }}>
        <span style={{ display: "block", fontSize: 22, fontWeight: 800, lineHeight: 1.1, color: "var(--on-bg)", fontVariantNumeric: "tabular-nums" }}>
          {spec.value}{spec.unit && <span style={{ fontSize: 13, fontWeight: 700, color: spec.colour, marginLeft: 2 }}>{spec.unit}</span>}
        </span>
        <span style={{ display: "block", fontSize: 12, fontWeight: 600, color: "var(--on-variant)", marginTop: 2 }}>{spec.label}</span>
        {spec.hint && <span style={{ display: "block", fontSize: 11, color: "var(--outline)" }}>{spec.hint}</span>}
      </span>
    </div>
  );
}

function Ring({ percent, colour }: { percent: number | null; colour: string }) {
  const filled = percent ?? 0;
  return (
    <div role="img" aria-label={percent === null ? "No attendance rate yet" : `Attendance ${percent} percent`} style={{ width: 84, height: 84, borderRadius: "50%", flexShrink: 0, display: "grid", placeItems: "center", background: `conic-gradient(${colour} ${filled * 3.6}deg, ${tint(colour, 0.15)} 0)`, transition: "background .3s" }}>
      <div style={{ width: 64, height: 64, borderRadius: "50%", background: "var(--surface)", display: "grid", placeItems: "center", fontSize: 18, fontWeight: 800, color: colour, fontVariantNumeric: "tabular-nums" }}>
        {percent === null ? "—" : `${percent}%`}
      </div>
    </div>
  );
}

export default function MonthSummary({ insights, stats, segments }: Props) {
  const total = segments.reduce((sum, segment) => sum + segment.count, 0);
  const rate = insights.attendancePercent;
  const rateColour = rate === null ? PALETTE.not_marked : rate >= 90 ? PALETTE.present : rate >= 75 ? PALETTE.late : PALETTE.absent;
  const cards: CardSpec[] = [
    { label: "Present days", value: String(stats.present), icon: "ti-user-check", colour: PALETTE.present },
    { label: "Absent days", value: String(stats.absent), icon: "ti-user-off", colour: PALETTE.absent },
    { label: "Late days", value: String(stats.late), icon: "ti-clock-exclamation", colour: PALETTE.late },
    { label: "Half days", value: String(stats.half_day), icon: "ti-circle-half-2", colour: PALETTE.half_day },
    { label: "Leave days", value: String(stats.on_leave), icon: "ti-plane", colour: PALETTE.on_leave },
    { label: "Total hours", value: String(stats.total_hours), unit: "h", icon: "ti-clock-hour-4", colour: PALETTE.holiday },
    { label: "Average hours", value: insights.averageHours === null ? "—" : String(insights.averageHours), unit: insights.averageHours === null ? undefined : "h", icon: "ti-chart-line", colour: PALETTE.brand, hint: "per day worked" },
    { label: "LOP days", value: String(stats.lop_days), icon: "ti-calendar-minus", colour: PALETTE.incomplete },
  ];
  return (
    <section aria-label="Month at a glance" style={{ display: "flex", flexDirection: "column", gap: 10, flex: 1 }}>
      <div className="card" style={{ padding: "16px 18px", display: "flex", alignItems: "center", gap: 16, background: `linear-gradient(135deg, ${tint(rateColour, 0.1)} 0%, var(--surface) 65%)` }}>
        <Ring percent={rate} colour={rateColour} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11.5, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: ".05em" }}>Attendance</div>
          <div style={{ fontSize: 13.5, fontWeight: 600, color: "var(--on-bg)", marginTop: 2 }}>{insights.worked} of {insights.workingDays} working days</div>
          {insights.unrecorded > 0 && <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 1 }}>{insights.unrecorded} past {insights.unrecorded === 1 ? "day" : "days"} not marked</div>}
          {total > 0 && (
            <div role="img" aria-label="How the working days so far were spent" style={{ display: "flex", height: 8, borderRadius: 999, overflow: "hidden", background: "var(--outline-v)", marginTop: 10 }}>
              {segments.map(segment => (
                <div key={segment.status} title={`${STATUS_META[segment.status]?.label ?? segment.status}: ${segment.count}`} style={{ width: `${(segment.count / total) * 100}%`, background: STATUS_META[segment.status]?.colour ?? "var(--outline)" }} />
              ))}
            </div>
          )}
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(165px, 1fr))", gridAutoRows: "1fr", gap: 10, flex: 1 }}>
        {cards.map(card => <StatCard key={card.label} spec={card} />)}
      </div>
    </section>
  );
}

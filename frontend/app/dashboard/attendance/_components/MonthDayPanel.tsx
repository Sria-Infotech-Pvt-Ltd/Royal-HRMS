"use client";

// The side panel beside the calendar: the picked day in full. A date badge and the status in colour, one plain sentence, check-in,
// check-out and hours as three cards, a note for a late arrival or a flag, and the two actions: open the full detail (when there is a
// record) or mark attendance (a past day with no record).

import { useT } from "@/hooks/useI18n";
import { PALETTE, tint } from "./attendancePalette";
import { LATE_LOGIN_LABEL } from "@/lib/lateLogin";
import { dateCaption, longDate } from "./detailView";
import { STATUS_META, canMark, daySentence, effectiveStatus, type DayRecord } from "./monthView";
import { tr } from "@/lib/i18n/tr";

interface Props {
  day: DayRecord | null;
  todayISO: string;
  /** Whether the viewer may mark attendance at all. */
  mayMark: boolean;
  onViewDetail: (day: DayRecord) => void;
  onMark: (day: DayRecord) => void;
}

function InfoCard({ label, value, icon, colour }: { label: string; value: string | null; icon: string; colour: string }) {
  return (
    <div style={{ flex: "1 1 0", minWidth: 0, padding: "10px 12px", borderRadius: 12, border: `1px solid ${value ? tint(colour, 0.25) : "var(--outline-v)"}`, background: value ? tint(colour, 0.09) : "var(--bg-low)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, fontWeight: 700, color: value ? colour : "var(--outline)", textTransform: "uppercase", letterSpacing: ".04em" }}>
        <i className={`ti ${icon}`} aria-hidden="true" />{label}
      </div>
      <div style={{ fontFamily: "Menlo, Consolas, monospace", fontWeight: 800, fontSize: 16, marginTop: 4, color: value ? "var(--on-bg)" : "var(--outline)" }}>{value ?? "—"}</div>
    </div>
  );
}

const monthShort = (dateISO: string) => new Date(`${dateISO}T00:00:00`).toLocaleDateString("en-IN", { month: "short" }).toUpperCase();

export default function MonthDayPanel({ day, todayISO, mayMark, onViewDetail, onMark }: Props) {
  const t = useT();
  if (!day) return null;
  const status = effectiveStatus(day, todayISO);
  const meta = STATUS_META[status] ?? STATUS_META.future;
  const markable = mayMark && canMark(day, todayISO);
  const hasHours = day.total_hours > 0;
  const pillStyle = status === "no_record"
    ? { background: "transparent", color: meta.colour, border: `1px dashed ${meta.colour}` }
    : { background: meta.colour, color: "#fff", border: "1px solid transparent" };
  return (
    <section aria-label={t("Selected day")} className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div style={{ padding: "16px 18px", display: "flex", alignItems: "center", gap: 14, background: `linear-gradient(135deg, ${tint(meta.colour, 0.16)} 0%, var(--surface) 80%)`, borderBottom: "1px solid var(--outline-v)" }}>
        <div aria-hidden="true" style={{ width: 56, borderRadius: 14, overflow: "hidden", textAlign: "center", border: `1px solid ${tint(meta.colour, 0.3)}`, background: "var(--surface)", flexShrink: 0 }}>
          <div style={{ background: meta.colour, color: "#fff", fontSize: 10.5, fontWeight: 800, letterSpacing: ".08em", padding: "3px 0" }}>{monthShort(day.date)}</div>
          <div style={{ fontSize: 24, fontWeight: 800, color: "var(--on-bg)", lineHeight: "34px" }}>{day.day_num}</div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 15, color: "var(--on-bg)" }}>{longDate(day.date)}</div>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 1 }}>{dateCaption(day.date, todayISO).split(" · ")[1]}</div>
        </div>
        <span style={{ fontSize: 12, fontWeight: 700, padding: "4px 12px", borderRadius: 999, whiteSpace: "nowrap", ...pillStyle }}>{t(meta.label)}</span>
      </div>

      <div style={{ padding: "14px 18px 18px" }}>
        <p style={{ margin: "0 0 12px", fontSize: 13, color: "var(--on-variant)" }}>{daySentence(day, status)}</p>
        {status !== "future" && (
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <InfoCard label={t("Check-in")} value={day.clock_in} icon="ti-login-2" colour={PALETTE.present} />
            <InfoCard label={t("Check-out")} value={day.clock_out} icon="ti-logout-2" colour={PALETTE.half_day} />
            <InfoCard label={t("Hours")} value={hasHours ? `${day.total_hours}h` : null} icon="ti-clock-hour-4" colour={PALETTE.holiday} />
          </div>
        )}
        {status === "late" && (
          <div role="note" style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 12.5, padding: "9px 12px", borderRadius: 12, background: tint(PALETTE.late, 0.1), border: `1px solid ${tint(PALETTE.late, 0.3)}`, marginBottom: 12 }}>
            <i className="ti ti-clock-exclamation" aria-hidden="true" style={{ color: PALETTE.late, fontSize: 18 }} />
            <span><strong>{t("Late arrival")}</strong>{day.clock_in ? t(": clocked in at {time}.", { time: day.clock_in }) : "."}</span>
          </div>
        )}
        {day.late_forgiven && (
          <div role="note" style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 12.5, padding: "9px 12px", borderRadius: 12, background: tint(PALETTE.late, 0.1), border: `1px solid ${tint(PALETTE.late, 0.3)}`, marginBottom: 12 }}>
            <i className="ti ti-clock-exclamation" aria-hidden="true" style={{ color: PALETTE.late, fontSize: 18 }} />
            <span><strong>{tr(LATE_LOGIN_LABEL)}</strong>{day.clock_in ? t(": clocked in at {time}, after the grace time.", { time: day.clock_in }) : "."}</span>
          </div>
        )}
        {day.is_wfh && (
          <div role="note" style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 12.5, padding: "9px 12px", borderRadius: 12, background: tint(PALETTE.wfh, 0.1), border: `1px solid ${tint(PALETTE.wfh, 0.3)}`, marginBottom: 12 }}>
            <i className="ti ti-home-2" aria-hidden="true" style={{ color: PALETTE.wfh, fontSize: 18 }} />
            <span><strong>{tr("Work from home")}</strong></span>
          </div>
        )}
        {day.is_flagged && (
          <div role="note" style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 12.5, padding: "9px 12px", borderRadius: 12, background: tint(meta.colour, 0.1), border: `1px solid ${tint(meta.colour, 0.3)}`, marginBottom: 12 }}>
            <i className="ti ti-flag-3-filled" aria-hidden="true" style={{ color: meta.colour, fontSize: 17 }} /> {t("Flagged for review")}
          </div>
        )}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {day.record_id && <button className="btn btn-filled btn-sm" onClick={() => onViewDetail(day)}><i className="ti ti-eye" /> {t("View full details")}</button>}
          {markable && <button className={day.record_id ? "btn btn-ghost btn-sm" : "btn btn-filled btn-sm"} onClick={() => onMark(day)}><i className="ti ti-pencil-plus" /> {t("Mark attendance")}</button>}
        </div>
      </div>
    </section>
  );
}

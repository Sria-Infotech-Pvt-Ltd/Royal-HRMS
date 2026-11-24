"use client";

// The same month as a plain list, newest day last: easier to scan and to copy from than a calendar. Days still in the future are left out.

import { useT } from "@/hooks/useI18n";
import { STATUS_META, canMark, dayTiming, effectiveStatus, timeRangeLabel, type DayRecord } from "./monthView";

interface Props {
  days: DayRecord[];
  todayISO: string;
  highlight: string;
  /** Whether the viewer may mark attendance at all. */
  mayMark: boolean;
  onDayClick: (day: DayRecord) => void;
}

const weekday = (dateISO: string) => new Date(`${dateISO}T00:00:00`).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });

export default function MonthDayList({ days, todayISO, highlight, mayMark, onDayClick }: Props) {
  const t = useT();
  const shown = days.filter(day => dayTiming(day.date, todayISO) !== "future" && (highlight === "" || effectiveStatus(day, todayISO) === highlight));
  return (
    <div className="card">
      <div className="table-wrap">
        <table>
          <thead>
            <tr><th>{t("Date")}</th><th>{t("Status")}</th><th>{t("Time")}</th><th>{t("Hours")}</th><th aria-label={t("Action")} /></tr>
          </thead>
          <tbody>
            {shown.length === 0 && <tr><td colSpan={5} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>{t("No days match.")}</td></tr>}
            {shown.map(day => {
              const meta = STATUS_META[effectiveStatus(day, todayISO)] ?? STATUS_META.no_record;
              const markable = mayMark && canMark(day, todayISO);
              return (
                <tr key={day.date} style={{ boxShadow: `inset 4px 0 0 ${meta.colour}` }}>
                  <td style={{ fontWeight: 600 }}>{weekday(day.date)}{day.date === todayISO && <span style={{ marginLeft: 8, fontSize: 10.5, fontWeight: 700, color: "var(--primary)" }}>{t("TODAY")}</span>}</td>
                  <td>
                    <span style={{ fontSize: 12, fontWeight: 700, padding: "2px 10px", borderRadius: 999, ...(effectiveStatus(day, todayISO) === "no_record" ? { background: "transparent", color: meta.colour, border: `1px dashed ${meta.colour}` } : { background: meta.colour, color: "#fff", border: "1px solid transparent" }) }}>{t(meta.label)}</span>
                    {day.is_flagged && <i className="ti ti-flag-3-filled" role="img" aria-label={t("Flagged")} title={t("Flagged for review")} style={{ marginLeft: 8, color: meta.colour }} />}
                  </td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12.5, color: "var(--on-variant)" }}>{timeRangeLabel(day) || "—"}</td>
                  <td style={{ fontFamily: "Menlo, Consolas, monospace", fontSize: 12.5 }}>{day.total_hours > 0 ? `${day.total_hours}h` : "—"}</td>
                  <td style={{ textAlign: "right" }}>
                    {(day.record_id || markable) && (
                      <button className="btn btn-ghost btn-sm" onClick={() => onDayClick(day)} aria-label={markable ? t("Mark {date}", { date: weekday(day.date) }) : t("View {date}", { date: weekday(day.date) })}>{markable ? t("Mark") : t("View")}</button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

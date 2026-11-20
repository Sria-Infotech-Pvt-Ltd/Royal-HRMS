"use client";

// The month as a colour-coded calendar. Days with a real status get a soft tint and a coloured left edge; a past day with nothing
// recorded stays white with a dashed slate "Not marked" label and an upcoming day is plain, so the grid is never a wall of colour.
// The picked day has a clear purple ring and glow, today a purple number with a "Today" tag, weekends a faint tint and holidays and
// week offs a calm treatment. Cells lift on hover. Clicking a day PICKS it (the side panel shows it). When a status is chosen in the
// legend, the other days fade. On a narrow screen the cells switch to a compact form (short label, no times).

import { useEffect, useRef, useState } from "react";
import { PALETTE, tint } from "./attendancePalette";
import { LATE_LOGIN_LABEL, LATE_LOGIN_MEANING } from "@/lib/lateLogin";
import { tr } from "@/lib/i18n/tr";
import {
  STATUS_META, buildGrid, dayTiming, effectiveStatus, formatMonthLabel, hoursBarPercent, timeRangeLabel, type DayRecord,
} from "./monthView";

const DAY_HEADERS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const STRIPES = "repeating-linear-gradient(135deg, transparent 0 7px, rgba(148,163,184,.14) 7px 14px)";
const COMPACT_BELOW_PX = 84;   // a cell narrower than this shows the short label and no times
const CELL_MIN_HEIGHT = 72;    // a day box is never shorter than this; the rows share any extra height so the calendar matches the column beside it
const COMPACT_CELL_MIN_HEIGHT = 54;

interface Props {
  days: DayRecord[];
  month: string;
  todayISO: string;
  /** The status picked in the legend, or "". */
  highlight: string;
  /** The picked day, or null. */
  selectedDate: string | null;
  onSelect: (date: string) => void;
}

function describe(day: DayRecord, status: string, month: string): string {
  const times = timeRangeLabel(day);
  return `${day.day_num} ${formatMonthLabel(month).split(" ")[0]}: ${STATUS_META[status].label}${times ? `, ${times}` : ""}${day.is_wfh ? `, ${tr("Work from home")}` : ""}`;
}

/** The width of an element, kept up to date as the window or the layout changes. Zero until measured (and in tests, where nothing is). */
function useMeasuredWidth<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(entries => setWidth(entries[0]?.contentRect.width ?? 0));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

interface CellProps extends Omit<Props, "days"> { day: DayRecord; weekend: boolean; compact: boolean }

function Cell({ day, month, todayISO, highlight, selectedDate, onSelect, weekend, compact }: CellProps) {
  const [hover, setHover] = useState(false);
  const timing = dayTiming(day.date, todayISO);
  const status = effectiveStatus(day, todayISO);
  const meta = STATUS_META[status] ?? STATUS_META.future;
  const isFuture = status === "future";
  const isNeutral = isFuture || status === "no_record";
  const isOff = status === "weekly_off" || status === "holiday";
  const selected = selectedDate === day.date;
  const isToday = timing === "today";
  const faded = highlight !== "" && status !== highlight;
  const times = timeRangeLabel(day);

  const rings = [
    selected ? `inset 0 0 0 2px ${PALETTE.brand}, 0 0 0 4px ${tint(PALETTE.brand, 0.18)}` : isToday ? `inset 0 0 0 1.5px ${tint(PALETTE.brand, 0.6)}` : "",
    hover && !selected ? "0 6px 16px rgba(15,23,42,0.12)" : "",
  ].filter(Boolean).join(", ");

  const style: React.CSSProperties = {
    position: "relative", zIndex: selected ? 2 : hover ? 1 : 0, display: "flex", flexDirection: "column", gap: 3, width: "100%", height: "100%", minHeight: compact ? COMPACT_CELL_MIN_HEIGHT : CELL_MIN_HEIGHT,
    padding: compact ? "4px 5px" : "6px 9px 8px", textAlign: "left", border: 0, font: "inherit", color: "inherit", cursor: "pointer", overflow: "hidden",
    backgroundColor: selected ? tint(PALETTE.brand, 0.08) : isNeutral ? (weekend ? "#F8FAFC" : "var(--surface)") : meta.bg,
    backgroundImage: isOff ? STRIPES : undefined,
    borderLeft: `3px solid ${isNeutral ? "transparent" : meta.colour}`,
    opacity: faded ? 0.22 : 1, transform: hover ? "translateY(-1px)" : "none", boxShadow: rings || undefined,
    transition: "transform .14s ease, box-shadow .14s ease, opacity .15s ease, background-color .15s ease",
  };

  return (
    <button
      type="button" aria-label={describe(day, status, month)} aria-pressed={selected} onClick={() => onSelect(day.date)} style={style}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)} onFocus={() => setHover(true)} onBlur={() => setHover(false)}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 4 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{
            fontWeight: 800, fontSize: compact ? 11.5 : 13, minWidth: compact ? 20 : 24, height: compact ? 20 : 24, borderRadius: 12, display: "grid", placeItems: "center",
            background: isToday ? PALETTE.brand : "transparent", color: isToday ? "#fff" : selected ? PALETTE.brand : isFuture ? "var(--outline)" : "var(--on-bg)",
          }}>{day.day_num}</span>
          {isToday && !compact && <span style={{ fontSize: 9.5, fontWeight: 800, letterSpacing: ".06em", color: PALETTE.brand }}>TODAY</span>}
        </span>
        {day.is_flagged && <i className="ti ti-flag-3-filled" role="img" aria-label="Flagged" title="Flagged for review" style={{ color: meta.colour, fontSize: compact ? 11 : 14 }} />}
      </div>
      {!isFuture && (
        <span style={{
          alignSelf: "flex-start", maxWidth: "100%", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: compact ? 9.5 : 10.5, fontWeight: 700, padding: compact ? "0 5px" : "1px 8px", borderRadius: 999,
          ...(status === "no_record" ? { background: "transparent", color: meta.colour, border: `1px dashed ${tint(meta.colour, 0.7)}` } : { background: meta.colour, color: "#fff", border: "1px solid transparent" }),
        }}>{compact ? meta.short : meta.label}</span>
      )}
      {day.late_forgiven && (
        <span title={tr(LATE_LOGIN_MEANING)} style={{ alignSelf: "flex-start", fontSize: compact ? 9 : 10, fontWeight: 700, color: PALETTE.late, whiteSpace: "nowrap" }}>
          <i className="ti ti-clock-exclamation" aria-hidden="true" /> {compact ? "Late" : tr(LATE_LOGIN_LABEL)}
        </span>
      )}
      {day.is_wfh && (
        <span title={tr("Work from home")} style={{ alignSelf: "flex-start", display: "inline-flex", alignItems: "center", gap: 3, fontSize: compact ? 9 : 10, fontWeight: 700, padding: compact ? "0 4px" : "1px 7px", borderRadius: 999, color: PALETTE.wfh, background: tint(PALETTE.wfh, 0.14), border: `1px solid ${tint(PALETTE.wfh, 0.35)}`, whiteSpace: "nowrap" }}>
          <i className="ti ti-home-2" aria-hidden="true" />{!compact && tr("WFH")}
        </span>
      )}
      {!compact && times && <div style={{ fontSize: 10.5, color: "var(--on-variant)", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>{times}</div>}
      {day.total_hours > 0 && (
        <div title={`${day.total_hours}h worked`} aria-hidden="true" style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 3, background: "rgba(15,23,42,0.07)" }}>
          <div style={{ width: `${hoursBarPercent(day.total_hours)}%`, height: "100%", background: meta.colour }} />
        </div>
      )}
    </button>
  );
}

export default function MonthCalendar({ days, month, todayISO, highlight, selectedDate, onSelect }: Props) {
  const weeks = buildGrid(days, month);
  const [gridRef, width] = useMeasuredWidth<HTMLDivElement>();
  const compact = width > 0 && width / 7 < COMPACT_BELOW_PX;
  return (
    <div ref={gridRef} className="card" aria-label="Attendance calendar" style={{ overflow: "hidden", padding: 0, display: "flex", flexDirection: "column", flex: 1, height: "100%" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", borderBottom: "1px solid var(--outline-v)", background: "var(--bg-low)" }}>
        {DAY_HEADERS.map((header, index) => (
          <div key={header} style={{ padding: "8px 0", textAlign: "center", fontSize: 11, fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: index >= 5 ? PALETTE.brand : "var(--on-variant)" }}>
            {compact ? header.slice(0, 1) : header}
          </div>
        ))}
      </div>
      <div style={{ flex: 1, display: "grid", gridTemplateRows: `repeat(${weeks.length}, minmax(${compact ? COMPACT_CELL_MIN_HEIGHT : CELL_MIN_HEIGHT}px, 1fr))` }}>
      {weeks.map((week, weekIndex) => (
        <div key={weekIndex} style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", borderBottom: weekIndex < weeks.length - 1 ? "1px solid var(--outline-v)" : "none", minHeight: 0 }}>
          {week.map((day, dayIndex) => (
            <div key={dayIndex} style={{ position: "relative", borderRight: dayIndex < 6 ? "1px solid var(--outline-v)" : "none", background: day ? undefined : "var(--bg-low)", minWidth: 0, minHeight: 0 }}>
              {day && <Cell day={day} month={month} todayISO={todayISO} highlight={highlight} selectedDate={selectedDate} onSelect={onSelect} weekend={dayIndex >= 5} compact={compact} />}
            </div>
          ))}
        </div>
      ))}
      </div>
    </div>
  );
}

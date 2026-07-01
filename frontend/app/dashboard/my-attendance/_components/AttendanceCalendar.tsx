"use client";

import type { DayRecord } from "@/types/attendance";

interface Props {
  year:         number;
  month:        number;  // 1-indexed
  data:         Record<string, DayRecord>;
  onRegularize: (date: string) => void;
}

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const STATUS_CONFIG: Record<string, { bg: string; color: string; label: string }> = {
  present:    { bg: "var(--success-c)",          color: "var(--success)",   label: "P"  },
  late:       { bg: "var(--warn-c)",             color: "var(--warn)",      label: "L"  },
  absent:     { bg: "var(--error-c)",            color: "var(--error)",     label: "A"  },
  half_day:   { bg: "rgba(251,146,60,0.15)",     color: "#ea580c",          label: "H"  },
  weekly_off: { bg: "var(--bg-low)",             color: "var(--outline)",   label: "W"  },
  holiday:    { bg: "rgba(59,130,246,0.12)",     color: "#3b82f6",          label: "Ho" },
  on_leave:   { bg: "rgba(168,85,247,0.12)",     color: "#a855f7",          label: "OL" },
};

export default function AttendanceCalendar({ year, month, data, onRegularize }: Props) {
  const jsMonth    = month - 1;  // convert to 0-indexed for Date API
  const firstDay   = new Date(year, jsMonth, 1).getDay();
  const daysInMonth = new Date(year, jsMonth + 1, 0).getDate();
  const now        = new Date();
  const isCurrentMonth = now.getFullYear() === year && now.getMonth() === jsMonth;
  const today      = now.getDate();

  const cells: Array<number | null> = [
    ...Array<null>(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  function dateStr(day: number) {
    return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
  }

  return (
    <div className="card" style={{ overflow: "hidden" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", borderBottom: "1px solid var(--outline-v)", background: "var(--bg-low)" }}>
        {DAY_NAMES.map(d => (
          <div key={d} style={{ padding: "10px 0", textAlign: "center", fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--on-variant)" }}>
            {d}
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)" }}>
        {cells.map((day, idx) => {
          const record = day ? data[String(day)] : null;
          const cfg    = record ? STATUS_CONFIG[record.status] : null;
          const isToday = isCurrentMonth && day === today;
          const col     = idx % 7;
          const showRight = col !== 6;
          const showBot   = idx < cells.length - 7;

          return (
            <div
              key={idx}
              style={{
                minHeight: 72,
                padding: "8px 6px",
                background: cfg ? cfg.bg : "transparent",
                borderRight:  showRight ? "1px solid var(--outline-v)" : "none",
                borderBottom: showBot   ? "1px solid var(--outline-v)" : "none",
              }}
            >
              {day && (
                <>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 3 }}>
                    <div style={{
                      width: 22, height: 22, borderRadius: "50%",
                      background: isToday ? "var(--primary)" : "transparent",
                      color: isToday ? "#fff" : cfg ? cfg.color : "var(--outline-v)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 11, fontWeight: isToday ? 700 : 500,
                    }}>
                      {day}
                    </div>
                    {cfg && (
                      <span style={{ fontSize: 8, fontWeight: 700, color: cfg.color, letterSpacing: "0.04em" }}>
                        {cfg.label}
                      </span>
                    )}
                  </div>

                  {record?.clockIn && (
                    <div style={{ fontSize: 9, color: "var(--on-variant)", fontFamily: "Menlo, Consolas, monospace", lineHeight: 1.5 }}>
                      <div>{record.clockIn}</div>
                      {record.clockOut && <div>{record.clockOut}</div>}
                    </div>
                  )}

                  {record?.canRegularize && (
                    <button
                      onClick={() => onRegularize(dateStr(day))}
                      title="Request correction for this day"
                      style={{
                        marginTop: 3, padding: "1px 5px", fontSize: 8, fontWeight: 700,
                        background: "var(--warn-c)", color: "var(--warn)",
                        border: "1px solid var(--warn)", borderRadius: 4,
                        cursor: "pointer", letterSpacing: "0.03em", lineHeight: 1.4,
                      }}
                    >
                      Regularize
                    </button>
                  )}
                </>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

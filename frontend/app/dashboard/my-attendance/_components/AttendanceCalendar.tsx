"use client";

import type { DayRecord } from "@/types/attendance";

interface Props {
  year:         number;
  month:        number;  // 1-indexed
  data:         Record<string, DayRecord>;
  onRegularize: (date: string) => void;
  // Hides the Regularize action — used when viewing another employee's
  // calendar, since the correction flow always submits against request.user.
  readOnly?:    boolean;
}

// Monday-first week (M-S columns), matching the reference layout.
const DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// Keyed by the display strings the backend sends (STATUS_DISPLAY_MAP capitalises all values)
const STATUS_LABELS: Record<string, string> = {
  'Present':           'P',
  'Late':              'L',
  'Absent':            'A',
  'Half Day':          'H',
  'Weekly Off':        'W',
  'Holiday':           'Ho',
  'On Leave':          'OL',
  'Incomplete':        '!',
  'Missing Clock Out': '!',
};

// Non-working days: hide clock-in/out times (no punches expected)
const NON_WORKING = new Set(['Weekly Off', 'Holiday']);

export default function AttendanceCalendar({ year, month, data, onRegularize, readOnly = false }: Props) {
  const jsMonth    = month - 1;  // convert to 0-indexed for Date API
  // getDay() is 0=Sun..6=Sat; shift so 0=Mon..6=Sun to match the Monday-first
  // column order above.
  const firstDay   = (new Date(year, jsMonth, 1).getDay() + 6) % 7;
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
    <div style={{ overflow: "hidden", borderTop: "1px solid var(--outline-v)" }}>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", borderBottom: "1px solid var(--outline-v)", background: "var(--bg-low)" }}>
        {DAY_NAMES.map(d => (
          <div key={d} style={{ padding: "6px 0", textAlign: "center", fontSize: 10.5, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--on-variant)" }}>
            {d}
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)" }}>
        {cells.map((day, idx) => {
          const record  = day ? data[String(day)] : null;
          const status  = record?.status ?? '';
          const label   = STATUS_LABELS[status] ?? '';
          // Use hex color from backend (_STATUS_COLOR); bg is the same color at 15% opacity
          const fg      = record?.color ?? 'var(--outline-v)';
          const bg      = record?.color ? record.color + '26' : 'transparent';
          const isToday = isCurrentMonth && day === today;
          const col     = idx % 7;

          return (
            <div
              key={idx}
              style={{
                minHeight: 48,
                padding: "5px 5px",
                background: bg,
                borderRight:  col !== 6            ? "1px solid var(--outline-v)" : "none",
                borderBottom: idx < cells.length - 7 ? "1px solid var(--outline-v)" : "none",
              }}
            >
              {day && (
                <>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 1 }}>
                    <div style={{
                      width: 17, height: 17, borderRadius: "50%",
                      background: isToday ? "var(--primary)" : "transparent",
                      // var(--on-primary), not a literal white, so the "today" badge
                      // text stays readable against --primary's lighter dark-mode tone.
                      color: isToday ? "var(--on-primary)" : (record ? fg : "var(--outline-v)"),
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 10, fontWeight: isToday ? 700 : 500,
                    }}>
                      {day}
                    </div>
                    {label && (
                      <span style={{ fontSize: 7.5, fontWeight: 700, color: fg, letterSpacing: "0.04em" }}>
                        {label}
                      </span>
                    )}
                  </div>

                  {record?.clockIn && !NON_WORKING.has(status) && (
                    <div style={{ fontSize: 8, color: "var(--on-variant)", fontFamily: "Menlo, Consolas, monospace", lineHeight: 1.35 }}>
                      <div>{record.clockIn}</div>
                      {record.clockOut && <div>{record.clockOut}</div>}
                    </div>
                  )}

                  {status === "Holiday" && record?.holiday_name && (
                    <div
                      title={record.holiday_name}
                      style={{
                        fontSize: 8, marginTop: 1, color: fg, fontWeight: 600,
                        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                      }}
                    >
                      {record.holiday_name}
                    </div>
                  )}

                  {!readOnly && record?.canRegularize && (
                    <button
                      onClick={() => onRegularize(dateStr(day))}
                      title="Request correction for this day"
                      style={{
                        marginTop: 2, padding: "1px 4px", fontSize: 7.5, fontWeight: 700,
                        background: "var(--warn-c)", color: "var(--warn)",
                        border: "1px solid var(--warn)", borderRadius: 4,
                        cursor: "pointer", letterSpacing: "0.02em", lineHeight: 1.3,
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

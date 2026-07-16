"use client";

export type DayStatus =
  | "Present" | "Late" | "Absent" | "On Leave"
  | "Half Day" | "Weekly Off" | "Holiday" | "future" | "empty";

export interface DayRecord {
  status:        DayStatus;
  clockIn?:      string;
  clockOut?:     string;
  hours?:        string;
  note?:         string;
  canRegularize?: boolean;
}

interface Props {
  year:           number;
  month:          number;
  data:           Record<number, DayRecord>;
  onRegularize?:  (day: number) => void;
}

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

const STATUS_STYLE: Record<DayStatus, { bg: string; color: string; label: string }> = {
  Present:      { bg: "var(--success-c)",        color: "var(--success)",   label: "P"  },
  Late:         { bg: "var(--warn-c)",            color: "var(--warn)",      label: "L"  },
  Absent:       { bg: "var(--error-c)",           color: "var(--error)",     label: "A"  },
  "On Leave":   { bg: "var(--info-c)",            color: "var(--info)",      label: "OL" },
  "Half Day":   { bg: "rgba(30,78,140,0.10)",     color: "var(--primary)",   label: "H"  },
  "Weekly Off": { bg: "var(--bg-low)",            color: "var(--outline)",   label: "W"  },
  Holiday:      { bg: "var(--sec-c)",             color: "var(--secondary)", label: "H"  },
  future:       { bg: "transparent",              color: "var(--outline-v)", label: ""   },
  empty:        { bg: "transparent",              color: "transparent",      label: ""   },
};

export default function CalendarGrid({ year, month, data, onRegularize }: Props) {
  const now          = new Date();
  const firstDay     = new Date(year, month, 1).getDay();
  const daysInMonth  = new Date(year, month + 1, 0).getDate();
  const isCurrentMonth = now.getFullYear() === year && now.getMonth() === month;
  const today        = now.getDate();

  const cells: Array<number | null> = [
    ...Array<null>(firstDay).fill(null),
    ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
  ];
  while (cells.length % 7 !== 0) cells.push(null);

  return (
    <div className="card" style={{ overflow: "hidden" }}>
      {/* Day-name header row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", borderBottom: "1px solid var(--outline-v)", background: "var(--bg-low)" }}>
        {DAY_NAMES.map(d => (
          <div key={d} style={{ padding: "10px 0", textAlign: "center", fontSize: 11, fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--on-variant)" }}>
            {d}
          </div>
        ))}
      </div>

      {/* Day cells */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)" }}>
        {cells.map((day, idx) => {
          const record   = day ? (data[day] ?? { status: "future" as DayStatus }) : null;
          const style    = record ? STATUS_STYLE[record.status] : null;
          const isToday  = isCurrentMonth && day === today;
          const col      = idx % 7;
          const showRight = col !== 6;
          const showBot   = idx < cells.length - 7;

          return (
            <div
              key={idx}
              title={record && record.status !== "future" && record.status !== "empty" ? record.status : undefined}
              style={{
                minHeight: 80,
                padding: "8px 6px",
                background: style ? style.bg : "transparent",
                borderRight:  showRight ? "1px solid var(--outline-v)" : "none",
                borderBottom: showBot   ? "1px solid var(--outline-v)" : "none",
              }}
            >
              {day && (
                <>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                    <div style={{
                      width: 24, height: 24, borderRadius: "50%",
                      background: isToday ? "var(--primary)" : "transparent",
                      color: isToday ? "#fff" : style ? style.color : "var(--on-bg)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontSize: 12, fontWeight: isToday ? 700 : 500,
                    }}>
                      {day}
                    </div>
                    {style && style.label && (
                      <span style={{ fontSize: 9, fontWeight: 700, color: style.color, letterSpacing: "0.04em" }}>
                        {style.label}
                      </span>
                    )}
                  </div>

                  {record && record.clockIn && (
                    <div style={{ fontSize: 9, color: "var(--on-variant)", fontFamily: "Menlo, Consolas, monospace", lineHeight: 1.6 }}>
                      <div>{record.clockIn}</div>
                      {record.clockOut && <div>{record.clockOut}</div>}
                    </div>
                  )}

                  {record && record.note && (
                    <div style={{ fontSize: 9, marginTop: 2, color: style ? style.color : "var(--on-variant)", fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                      {record.note}
                    </div>
                  )}

                  {record && record.canRegularize && onRegularize && (
                    <button
                      onClick={() => onRegularize(day)}
                      title="Request correction for this day"
                      style={{
                        marginTop: 3,
                        padding: "1px 5px",
                        fontSize: 8,
                        fontWeight: 700,
                        background: "var(--warn-c)",
                        color: "var(--warn)",
                        border: "1px solid var(--warn)",
                        borderRadius: 4,
                        cursor: "pointer",
                        letterSpacing: "0.03em",
                        lineHeight: 1.4,
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

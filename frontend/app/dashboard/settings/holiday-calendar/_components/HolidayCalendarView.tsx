"use client";

import type { Holiday } from "@/types/holidays";
import { TYPE_STYLES } from "./HolidayListView";

const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const MONTH_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const DAY_SHORT   = ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"];

function fmtDate(iso: string) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${parseInt(d)} ${MONTH_SHORT[parseInt(m) - 1]} ${y}`;
}

function calendarWeeks(year: number, month: number) {
  const firstDay = new Date(year, month, 1).getDay();
  const totalDays = new Date(year, month + 1, 0).getDate();
  const cells: (number | null)[] = Array(firstDay).fill(null);
  for (let d = 1; d <= totalDays; d++) cells.push(d);
  while (cells.length % 7 !== 0) cells.push(null);
  const weeks: (number | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) weeks.push(cells.slice(i, i + 7));
  return weeks;
}

function isoDate(year: number, month: number, day: number) {
  return `${year}-${String(month + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

interface Props {
  year:      number;
  calMonth:  number;
  holidays:  Holiday[];
  onMonthChange: (month: number) => void;
  onView:        (h: Holiday) => void;
}

export default function HolidayCalendarView({ year, calMonth, holidays, onMonthChange, onView }: Props) {
  const weeks = calendarWeeks(year, calMonth);
  const calMap = Object.fromEntries(holidays.map(h => [h.date, h]));

  return (
    <div className="bg-[var(--surface)] rounded-2xl border border-[var(--outline-v)] shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--outline-v)]">
        <button onClick={() => onMonthChange(Math.max(0, calMonth - 1))} disabled={calMonth === 0}
          className="w-8 h-8 flex items-center justify-center rounded-xl border border-[var(--outline-v)] text-[var(--on-variant)] disabled:opacity-30 hover:border-[var(--info)] hover:text-[var(--info)] transition-colors">
          <i className="ti ti-chevron-left text-sm" />
        </button>
        <div className="text-center">
          <div className="text-base font-bold text-[var(--on-bg)]">{MONTH_NAMES[calMonth]} {year}</div>
          <div className="text-xs text-[var(--outline)] mt-0.5">{holidays.length} holiday{holidays.length !== 1 ? "s" : ""} this month</div>
        </div>
        <button onClick={() => onMonthChange(Math.min(11, calMonth + 1))} disabled={calMonth === 11}
          className="w-8 h-8 flex items-center justify-center rounded-xl border border-[var(--outline-v)] text-[var(--on-variant)] disabled:opacity-30 hover:border-[var(--info)] hover:text-[var(--info)] transition-colors">
          <i className="ti ti-chevron-right text-sm" />
        </button>
      </div>

      <div className="grid grid-cols-7 border-b border-[var(--outline-v)]">
        {DAY_SHORT.map(d => (
          <div key={d} className={`py-2 text-center text-xs font-bold uppercase tracking-wider ${d === "Sun" ? "text-[var(--error)]" : "text-[var(--outline)]"}`}>{d}</div>
        ))}
      </div>

      <div>
        {weeks.map((week, wi) => (
          <div key={wi} className="grid grid-cols-7 border-b border-[var(--outline-v)] last:border-b-0">
            {week.map((day, di) => {
              const iso = day ? isoDate(year, calMonth, day) : "";
              const holiday = iso ? calMap[iso] : null;
              const isSun = di === 0;
              return (
                <div key={di} className={`min-h-[80px] p-2 border-r border-[var(--outline-v)] last:border-r-0 ${!day ? "bg-[var(--bg-mid)]" : ""}`}>
                  {day && (
                    <>
                      <span className={`text-xs font-semibold ${isSun ? "text-[var(--error)]" : "text-[var(--on-variant)]"} ${holiday ? "w-6 h-6 flex items-center justify-center rounded-full bg-[var(--info)] text-white text-xs" : ""}`}>
                        {day}
                      </span>
                      {holiday && (
                        <div className={`mt-1 px-1.5 py-1 rounded text-xs font-medium leading-tight ${TYPE_STYLES[holiday.holiday_type].cal} cursor-pointer`}
                          onClick={() => onView(holiday)}>
                          <div className="truncate">{holiday.name}</div>
                          {holiday.is_optional && <div className="text-[var(--primary)] text-[10px]">Optional</div>}
                        </div>
                      )}
                    </>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>

      {holidays.length > 0 && (
        <div className="border-t border-[var(--outline-v)] px-5 py-4">
          <div className="text-xs font-bold text-[var(--outline)] uppercase tracking-wider mb-3">Holidays in {MONTH_NAMES[calMonth]}</div>
          <div className="flex flex-col gap-2">
            {[...holidays].sort((a, b) => a.date.localeCompare(b.date)).map(h => (
              <div key={h.id} className="flex items-center gap-3 text-sm">
                <span className={`w-2 h-2 rounded-full flex-shrink-0 ${TYPE_STYLES[h.holiday_type].dot}`} />
                <span className="font-semibold text-[var(--on-bg)] w-[160px] truncate">{h.name}</span>
                <span className="text-[var(--outline)]">{fmtDate(h.date)}</span>
                <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold ${TYPE_STYLES[h.holiday_type].badge}`}>{h.holiday_type_display}</span>
                {h.is_optional && <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-semibold bg-[var(--primary-c)] text-[var(--primary)]">Optional</span>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import AttendanceDetailDrawer from "./AttendanceDetailDrawer";
import { AttendanceCreateForm } from "./AttendanceEditForm";
import EmptyState from "@/components/EmptyState";
import LoadingState from "@/components/LoadingState";

interface EmployeeOption {
  id: string;
  employee_id: string;
  full_name: string;
  department: string;
  designation: string;
}

interface DayRecord {
  date: string;
  day_short: string;
  day_num: number;
  status: string;
  status_label: string;
  clock_in: string | null;
  clock_out: string | null;
  total_hours: number;
  is_flagged: boolean;
  record_id: string | null;
}

interface MonthStats {
  present: number;
  late: number;
  half_day: number;
  absent: number;
  on_leave: number;
  lop_days: number;
  total_hours: number;
}

interface MonthData {
  employee: EmployeeOption;
  month: string;
  stats: MonthStats;
  days: DayRecord[];
}

interface EmpListResponse {
  results: EmployeeOption[];
}


const STATUS_COLOR: Record<string, string> = {
  present: "#15803d", late: "#b45309", half_day: "#1d4ed8",
  on_leave: "#6d28d9", weekly_off: "var(--on-variant)", holiday: "#0f766e",
  absent: "#b91c1c", incomplete: "#c2410c", no_record: "var(--on-variant)",
};

const STATUS_BG: Record<string, string> = {
  present: "rgba(21,128,61,0.10)", late: "rgba(180,83,9,0.10)",
  half_day: "rgba(29,78,216,0.10)", on_leave: "rgba(109,40,217,0.10)",
  weekly_off: "rgba(0,0,0,0.03)", holiday: "rgba(15,118,110,0.10)",
  absent: "rgba(185,28,28,0.10)", incomplete: "rgba(194,65,12,0.10)",
};

const STATUS_SHORT: Record<string, string> = {
  present: "P", late: "Late", half_day: "½", on_leave: "OL",
  weekly_off: "WO", holiday: "Hol", absent: "A", incomplete: "Inc", no_record: "—",
};

const DAY_HEADERS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function currentMonthISO() {
  return new Date().toISOString().slice(0, 7);
}

function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function formatMonthLabel(month: string): string {
  const [y, m] = month.split("-").map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
}

function buildGrid(days: DayRecord[], month: string): (DayRecord | null)[][] {
  const [y, m] = month.split("-").map(Number);
  const pad = (new Date(y, m - 1, 1).getDay() + 6) % 7;
  const cells: (DayRecord | null)[] = [...Array<null>(pad).fill(null), ...days];
  while (cells.length % 7 !== 0) cells.push(null);
  const rows: (DayRecord | null)[][] = [];
  for (let i = 0; i < cells.length; i += 7) rows.push(cells.slice(i, i + 7));
  return rows;
}

interface Props {
  initialEmployee?: string | null;
  initialMonth?: string | null;
}

export default function EmployeeMonthView({ initialEmployee, initialMonth }: Props) {
  const [query, setQuery]       = useState("");
  const [dropOpen, setDropOpen] = useState(false);
  const [selected, setSelected] = useState<EmployeeOption | null>(null);
  const [month, setMonth]       = useState(initialMonth ?? currentMonthISO());
  const [viewing,  setViewing]  = useState<{ id: string; date: string } | null>(null);
  const [marking,  setMarking]  = useState<{ date: string } | null>(null);
  const [seeded, setSeeded]     = useState(false);

  // A click's target is resolved at mouseup, not mousedown — selecting text
  // inside the modal and releasing past its edge would otherwise land on the
  // overlay and close it. Only close when the gesture both started AND ended
  // on the backdrop itself.
  const mouseDownOnOverlay = useRef(false);

  const { data: empList } = useFetch<EmpListResponse>(`${API.employees.list}?page_size=500`);
  const allEmployees = empList?.results ?? [];

  // Pre-select the employee from the URL by fetching them directly — much faster
  // than waiting for the full 500-employee list to load and searching through it.
  const { data: preloadedEmp } = useFetch<EmployeeOption>(
    initialEmployee && !seeded ? API.employees.detail(initialEmployee) : null
  );

  useEffect(() => {
    if (seeded || !preloadedEmp) return;
    setSelected({
      id:          preloadedEmp.id,
      employee_id: preloadedEmp.employee_id,
      full_name:   preloadedEmp.full_name,
      department:  preloadedEmp.department  ?? "",
      designation: preloadedEmp.designation ?? "",
    });
    setQuery(preloadedEmp.full_name);
    setSeeded(true);
  }, [preloadedEmp, seeded]);

  const filtered = useMemo(() => {
    if (!query || query.length < 2 || selected) return [];
    const q = query.toLowerCase();
    return allEmployees
      .filter(e => e.full_name.toLowerCase().includes(q) || e.employee_id.toLowerCase().includes(q))
      .slice(0, 8);
  }, [allEmployees, query, selected]);

  const calUrl = selected ? API.attendance.employeeCalendar(selected.id, month) : null;
  const { data, loading, error, refetch: refetchMonth } = useFetch<MonthData>(calUrl);

  const grid = data ? buildGrid(data.days, month) : [];

  function pickEmployee(emp: EmployeeOption) {
    setSelected(emp);
    setQuery(emp.full_name);
    setDropOpen(false);
  }

  function handleDayClick(day: DayRecord) {
    if (!day.record_id) {
      setMarking({ date: day.date });
      return;
    }
    setViewing({ id: day.record_id, date: day.date });
  }

  const stats = data?.stats;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

      {/* Controls row */}
      <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        {/* Employee search */}
        <div style={{ position: "relative", flex: "1 1 280px", maxWidth: 380 }}>
          <input
            className="field-input"
            style={{ width: "100%", paddingLeft: 32 }}
            placeholder="Search employee by name or ID…"
            value={query}
            onChange={e => { setQuery(e.target.value); setSelected(null); setDropOpen(true); }}
            onFocus={() => setDropOpen(true)}
            onBlur={() => setTimeout(() => setDropOpen(false), 160)}
          />
          <i className="ti ti-search" style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", fontSize: 14, color: "var(--on-variant)", pointerEvents: "none" }} />
          {dropOpen && filtered.length > 0 && (
            <div style={{ position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, background: "var(--bg)", border: "1px solid var(--outline-v)", borderRadius: 8, boxShadow: "0 4px 16px rgba(0,0,0,0.12)", zIndex: 50, overflow: "hidden" }}>
              {filtered.map(emp => (
                <div
                  key={emp.id}
                  onMouseDown={() => pickEmployee(emp)}
                  style={{ padding: "9px 14px", cursor: "pointer", fontSize: 13, borderBottom: "1px solid var(--outline-v)" }}
                >
                  <span style={{ fontWeight: 600 }}>{emp.full_name}</span>
                  <span style={{ marginLeft: 8, fontSize: 11, color: "var(--on-variant)" }}>{emp.employee_id} · {emp.department}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Month navigator */}
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => setMonth(m => shiftMonth(m, -1))}>
            <i className="ti ti-chevron-left" />
          </button>
          <span style={{ fontWeight: 600, fontSize: 14, minWidth: 120, textAlign: "center" }}>
            {formatMonthLabel(month)}
          </span>
          <button className="btn btn-ghost btn-sm" onClick={() => setMonth(m => shiftMonth(m, 1))} disabled={month >= currentMonthISO()}>
            <i className="ti ti-chevron-right" />
          </button>
        </div>
      </div>

      {/* Prompt when no employee selected */}
      {!selected && (
        <EmptyState icon="ti-user-search" title="Search for an employee to view their monthly attendance calendar." />
      )}

      {selected && loading && <LoadingState label="Loading attendance data…" />}

      {selected && error && (
        <div className="alert alert-error"><i className="ti ti-alert-circle" /> {error}</div>
      )}

      {selected && data && (
        <>
          {/* Employee info + summary strip */}
          <div className="card" style={{ padding: "14px 20px", display: "flex", flexWrap: "wrap", gap: 20, alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15 }}>{data.employee.full_name}</div>
              <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
                {data.employee.employee_id} · {data.employee.designation} · {data.employee.department}
              </div>
            </div>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginLeft: "auto" }}>
              {([
                ["Present",  stats?.present,  "#15803d"],
                ["Late",     stats?.late,     "#b45309"],
                ["Half Day", stats?.half_day, "#1d4ed8"],
                ["Absent",   stats?.absent,   "#b91c1c"],
                ["On Leave", stats?.on_leave, "#6d28d9"],
                ["LOP",      stats?.lop_days, "#b91c1c"],
              ] as [string, number | undefined, string][]).map(([label, val, color]) => (
                <div key={label} style={{ textAlign: "center" }}>
                  <div style={{ fontWeight: 700, fontSize: 18, color, fontVariantNumeric: "tabular-nums" }}>{val ?? 0}</div>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{label}</div>
                </div>
              ))}
              <div style={{ textAlign: "center" }}>
                <div style={{ fontWeight: 700, fontSize: 18, fontVariantNumeric: "tabular-nums" }}>{stats?.total_hours ?? 0}h</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Total Hrs</div>
              </div>
            </div>
          </div>

          {/* Calendar grid */}
          <div className="card" style={{ overflow: "hidden" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", borderBottom: "1px solid var(--outline-v)" }}>
              {DAY_HEADERS.map(d => (
                <div key={d} style={{ padding: "8px 0", textAlign: "center", fontSize: 11, fontWeight: 700, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: ".05em" }}>
                  {d}
                </div>
              ))}
            </div>
            {grid.map((week, wi) => (
              <div key={wi} style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", borderBottom: wi < grid.length - 1 ? "1px solid var(--outline-v)" : "none" }}>
                {week.map((day, di) => (
                  <div
                    key={di}
                    onClick={() => day && handleDayClick(day)}
                    style={{
                      padding: "8px 10px",
                      minHeight: 72,
                      background: day ? (STATUS_BG[day.status] ?? "transparent") : "transparent",
                      borderRight: di < 6 ? "1px solid var(--outline-v)" : "none",
                      cursor: day ? "pointer" : "default",
                      opacity: day?.status === "weekly_off" || day?.status === "holiday" ? 0.45 : 1,
                      outline: day?.is_flagged ? `2px solid ${STATUS_COLOR[day.status]}` : "none",
                      outlineOffset: -2,
                      borderRadius: 0,
                      transition: "background 0.1s",
                    }}
                  >
                    {day && (
                      <>
                        <div style={{ fontWeight: 700, fontSize: 14, color: "var(--on-bg)" }}>{day.day_num}</div>
                        <div style={{ fontSize: 10, fontWeight: 600, color: STATUS_COLOR[day.status] ?? "var(--on-variant)", marginTop: 3 }}>
                          {STATUS_SHORT[day.status] ?? "—"}
                        </div>
                        {day.clock_in && (
                          <div style={{ fontSize: 9, color: "var(--on-variant)", marginTop: 2, fontVariantNumeric: "tabular-nums" }}>
                            {day.clock_in}{day.clock_out ? ` – ${day.clock_out}` : ""}
                          </div>
                        )}
                        {day.total_hours > 0 && (
                          <div style={{ fontSize: 9, color: "var(--on-variant)", marginTop: 1, fontVariantNumeric: "tabular-nums" }}>
                            {day.total_hours}h
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>

          {/* Legend */}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", fontSize: 11, color: "var(--on-variant)" }}>
            {Object.entries({ present: "Present", late: "Late", half_day: "Half Day", on_leave: "On Leave", absent: "Absent", incomplete: "Incomplete", weekly_off: "Week Off", holiday: "Holiday" }).map(([k, label]) => (
              <div key={k} style={{ display: "flex", alignItems: "center", gap: 5 }}>
                <span style={{ width: 10, height: 10, borderRadius: 2, background: STATUS_BG[k] ?? "var(--outline-v)", border: `1px solid ${STATUS_COLOR[k] ?? "var(--outline-v)"}`, flexShrink: 0 }} />
                {label}
              </div>
            ))}
          </div>
        </>
      )}

      {/* Mark Attendance modal — for absent / no-record days */}
      {marking && selected && (
        <div
          className="drawer-overlay open"
          onMouseDown={e => { mouseDownOnOverlay.current = e.target === e.currentTarget; }}
          onClick={e => { if (mouseDownOnOverlay.current && e.target === e.currentTarget) setMarking(null); }}
        >
          <div className="drawer open" style={{ maxWidth: 420 }} onClick={e => e.stopPropagation()}>
            <div className="drawer-header">
              <span className="drawer-title">Mark Attendance — {marking.date}</span>
              <button className="drawer-close" onClick={() => setMarking(null)}><i className="ti ti-x" /></button>
            </div>
            <div className="drawer-body">
              <div style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 16 }}>
                <i className="ti ti-user" style={{ marginRight: 6 }} />
                {selected.full_name} · {selected.employee_id}
              </div>
              <AttendanceCreateForm
                employeeId={selected.id}
                date={marking.date}
                onSaved={() => { setMarking(null); refetchMonth(); }}
                onCancel={() => setMarking(null)}
              />
            </div>
          </div>
        </div>
      )}

      {viewing && (
        <AttendanceDetailDrawer
          recordId={viewing.id}
          date={viewing.date}
          onClose={() => setViewing(null)}
          onRecordChanged={refetchMonth}
        />
      )}
    </div>
  );
}

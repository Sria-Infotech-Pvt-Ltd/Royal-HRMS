"use client";

// Employee Month View: pick an employee, then see their month as a calendar or a list, with the month at a glance, a status filter,
// a day's detail on click, and "Mark" on past days that have no record. Before anyone is chosen it lists every employee with a search
// bar. The pieces live in the Month*.tsx files beside this one.

import { useEffect, useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { API } from "@/lib/api/endpoints";
import AttendanceDetailDrawer from "./AttendanceDetailDrawer";
import MarkAttendanceDrawer from "./MarkAttendanceDrawer";
import MonthEmployeeDirectory from "./MonthEmployeeDirectory";
import MonthCalendar from "./MonthCalendar";
import MonthDayList from "./MonthDayList";
import MonthDayPanel from "./MonthDayPanel";
import MonthHeaderCard, { type MonthViewMode } from "./MonthHeaderCard";
import MonthSkeleton from "./MonthSkeleton";
import MonthStatusFilter from "./MonthStatusFilter";
import MonthSummary from "./MonthSummary";
import {
  barSegments, canMark, countByStatus, currentMonthISO, defaultSelectedDate, localISODate, monthInsights, shiftMonth, type DayRecord, type EmployeeOption, type MonthData,
} from "./monthView";

interface Props {
  initialEmployee?: string | null;
  initialMonth?: string | null;
}

export default function EmployeeMonthView({ initialEmployee, initialMonth }: Props) {
  const [selected, setSelected]   = useState<EmployeeOption | null>(null);
  const [month, setMonth]         = useState(initialMonth ?? currentMonthISO());
  const [view, setView]           = useState<MonthViewMode>("calendar");
  const [highlight, setHighlight] = useState("");
  const [pickedDate, setPickedDate] = useState<string | null>(null);
  const [viewing, setViewing]     = useState<{ id: string; date: string } | null>(null);
  const [marking, setMarking]     = useState<{ date: string } | null>(null);
  const [seeded, setSeeded]       = useState(false);
  const [todayISO]                = useState(() => localISODate());
  const mayMark                   = usePermission("attendance.create");   // marking a day is for people who may create attendance

  const { data: employeeList, loading: employeesLoading } = useFetch<{ results: EmployeeOption[] }>(`${API.employees.list}?page_size=500`);
  const employees = useMemo(() => [...(employeeList?.results ?? [])].sort((a, b) => a.full_name.localeCompare(b.full_name)), [employeeList]);

  // Pre-select the employee from the URL by fetching them directly: much faster than waiting for the full 500-employee list.
  const { data: preloaded } = useFetch<EmployeeOption>(initialEmployee && !seeded ? API.employees.detail(initialEmployee) : null);
  useEffect(() => {
    if (seeded || !preloaded) return;
    setSelected({ id: preloaded.id, employee_id: preloaded.employee_id, full_name: preloaded.full_name, department: preloaded.department ?? "", designation: preloaded.designation ?? "" });
    setSeeded(true);
  }, [preloaded, seeded]);

  const { data, loading, error, refetch } = useFetch<MonthData>(selected ? API.attendance.employeeCalendar(selected.id, month) : null);

  const days = useMemo(() => data?.days ?? [], [data]);
  const counts = useMemo(() => countByStatus(days, todayISO), [days, todayISO]);
  const insights = useMemo(() => monthInsights(days, todayISO), [days, todayISO]);
  const segments = useMemo(() => barSegments(days, todayISO), [days, todayISO]);

  const choices = useMemo(() => (selected && !employees.some(employee => employee.id === selected.id) ? [selected, ...employees] : employees), [employees, selected]);
  const position = selected ? employees.findIndex(employee => employee.id === selected.id) : -1;
  const neighbour = (step: number) => (position >= 0 && employees[position + step] ? () => { setSelected(employees[position + step]); setHighlight(""); setPickedDate(null); } : null);

  // The day in the side panel: the one the person picked if it is in this month, else today / the latest recorded day.
  const activeDate = pickedDate && days.some(day => day.date === pickedDate) ? pickedDate : defaultSelectedDate(days, todayISO);
  const activeDay = days.find(day => day.date === activeDate) ?? null;

  function handleDayClick(day: DayRecord) {
    if (day.record_id) setViewing({ id: day.record_id, date: day.date });
    else if (mayMark && canMark(day, todayISO)) setMarking({ date: day.date });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <MonthHeaderCard
        employees={choices} employee={selected} onSelectEmployee={id => { setSelected(choices.find(employee => employee.id === id) ?? null); setHighlight(""); setPickedDate(null); }}
        onPreviousEmployee={neighbour(-1)} onNextEmployee={neighbour(1)} month={month} view={view} onViewChange={setView}
        canGoNextMonth={month < currentMonthISO()} isCurrentMonth={month === currentMonthISO()}
        onMonthStep={delta => setMonth(current => shiftMonth(current, delta))} onThisMonth={() => setMonth(currentMonthISO())}
      />

      {!selected && (
        <MonthEmployeeDirectory
          employees={employees} loading={employeesLoading}
          onSelect={employee => { setSelected(employee); setHighlight(""); setPickedDate(null); }}
        />
      )}
      {selected && loading && <MonthSkeleton />}
      {selected && error && <div className="alert alert-error"><i className="ti ti-alert-circle" /> {error}</div>}

      {selected && data && (
        <>
          <MonthStatusFilter counts={counts} active={highlight} onChange={setHighlight} />
          {view === "calendar" ? (
            // About 65% calendar and 35% details on a wide screen, both columns the same height (the taller one sets it); below ~920px the two stack.
            <div style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "stretch" }}>
              <div style={{ flex: "65 1 0%", minWidth: "min(560px, 100%)", display: "flex", flexDirection: "column" }}>
                <MonthCalendar days={days} month={month} todayISO={todayISO} highlight={highlight} selectedDate={activeDate} onSelect={setPickedDate} />
              </div>
              <aside style={{ flex: "35 1 0%", minWidth: "min(340px, 100%)", display: "flex", flexDirection: "column", gap: 14 }}>
                <MonthDayPanel day={activeDay} todayISO={todayISO} mayMark={mayMark} onViewDetail={handleDayClick} onMark={handleDayClick} />
                <MonthSummary insights={insights} stats={data.stats} segments={segments} />
              </aside>
            </div>
          ) : (
            <>
              <MonthSummary insights={insights} stats={data.stats} segments={segments} />
              <MonthDayList days={days} todayISO={todayISO} highlight={highlight} mayMark={mayMark} onDayClick={handleDayClick} />
            </>
          )}
        </>
      )}

      {marking && selected && (
        <MarkAttendanceDrawer employee={selected} date={marking.date} onClose={() => setMarking(null)} onSaved={() => { setMarking(null); refetch(); }} />
      )}
      {viewing && <AttendanceDetailDrawer recordId={viewing.id} date={viewing.date} onClose={() => setViewing(null)} onRecordChanged={refetch} />}
    </div>
  );
}

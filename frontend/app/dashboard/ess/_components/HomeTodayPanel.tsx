"use client";

// Right-column "Today" panel — today's clock status, a this-month attendance
// snapshot standing in for "weekly timesheet status" (no week-scoped ESS
// endpoint exists yet — see HomeTab.tsx note), and upcoming holidays via the
// existing EmpUpcomingHolidays widget (already used elsewhere, not duplicated).

import type { AttendanceStatus } from "@/types/employeeDashboard";
import type { AttendanceStats } from "@/types/attendance";
import EmpUpcomingHolidays from "@/components/dashboard/employee/EmpUpcomingHolidays";

interface Props {
  status: AttendanceStatus | null;
  stats:  AttendanceStats | null;
}

function Row({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "9px 0", borderBottom: "1px solid var(--outline-v)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--on-variant)" }}>
        <i className={`ti ${icon}`} /> {label}
      </div>
      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{value}</div>
    </div>
  );
}

export default function HomeTodayPanel({ status, stats }: Props) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="card">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-calendar-time" /> Today</div>
        </div>
        <div style={{ padding: "4px 20px 16px" }}>
          <Row icon="ti-login" label="Clock in" value={status?.clock_in_time ?? "—"} />
          <Row icon="ti-logout" label="Clock out" value={status?.clock_out_time ?? "—"} />
          <Row icon="ti-clock" label="Hours logged today" value={status?.working_hours || "—"} />
          <Row
            icon="ti-calendar-stats"
            label="Days present this month"
            value={stats ? `${stats.days_present}/${stats.working_days}` : "—"}
          />
        </div>
      </div>

      <EmpUpcomingHolidays />
    </div>
  );
}

"use client";

import { useManagerKPIs } from "@/hooks/useManagerDashboard";

interface Props { firstName: string }

export default function ManagerConsole({ firstName }: Props) {
  const { data: kpis, loading } = useManagerKPIs();

  const today = new Date().toLocaleDateString("en-IN", {
    weekday: "long", day: "numeric", month: "long",
  });

  const stat = (val: number | undefined) => (loading ? "—" : String(val ?? 0));

  return (
    <div className="dash-greeting mb-20" style={{ background: "linear-gradient(135deg, #0F6E56 0%, #0a4f3e 100%)" }}>
      <div className="dash-greeting-content">
        <h1>Team Overview, {firstName} 👋</h1>
        <p suppressHydrationWarning>
          {loading
            ? "Loading your team overview…"
            : `${kpis?.pending_approvals ?? 0} approvals pending · ${kpis?.on_leave_today ?? 0} team members on leave today · ${today}`}
        </p>
        <div className="dash-greeting-stats">
          <div className="dgs-item"><div className="dgs-val">{stat(kpis?.team_size)}</div><div className="dgs-lbl">Team Size</div></div>
          <div className="dgs-item"><div className="dgs-val">{stat(kpis?.pending_approvals)}</div><div className="dgs-lbl">Pending Approvals</div></div>
          <div className="dgs-item"><div className="dgs-val">{stat(kpis?.on_leave_today)}</div><div className="dgs-lbl">On Leave Today</div></div>
          <div className="dgs-item"><div className="dgs-val">{loading ? "—" : `${kpis?.attendance_rate ?? 0}%`}</div><div className="dgs-lbl">Attendance Rate</div></div>
        </div>
      </div>
    </div>
  );
}

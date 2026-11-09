"use client";

// Reports: generate any report the signed-in person is allowed to see, download it, or email it to colleagues.
// The reports are built on the server in the person's own scope (the same permissions and scoping as the module each
// one reports on), so this screen adds no access of its own. The screens that were here before (Audit Log, Leave
// Analytics, Attendance, Payroll) stay reachable below for the people who may open them.
import { useRouter } from "next/navigation";
import { usePermission } from "@/hooks/usePermission";
import { useReportCatalog } from "@/hooks/useReports";
import ReportCard from "./_components/ReportCard";

const OTHER_SCREENS = [
  { id: "audit", route: "/dashboard/settings/audit", permission: "audit.view", icon: "ti-history", label: "Audit Log", desc: "Every recorded action." },
  { id: "leave", route: "/dashboard/leave?tab=analytics", permission: "leave.view", icon: "ti-chart-bar", label: "Leave Analytics", desc: "Utilisation by type, department and branch." },
  { id: "attendance", route: "/dashboard/attendance", permission: "attendance.create", icon: "ti-clock", label: "Attendance Overview", desc: "Presence, exceptions and regularization." },
  { id: "payroll", route: "/dashboard/payroll", permission: "payroll.view", icon: "ti-report-money", label: "Payroll", desc: "Cycle readiness and statutory returns." },
] as const;

export default function ReportsPage() {
  const router = useRouter();
  const catalog = useReportCatalog();
  const allowed: Record<string, boolean> = {
    audit: usePermission("audit.view"), leave: usePermission("leave.view"),
    attendance: usePermission("attendance.create"), payroll: usePermission("payroll.view"),
  };
  const otherScreens = OTHER_SCREENS.filter(screen => allowed[screen.id]);
  const reports = catalog.data?.reports ?? [];
  const limits = catalog.data?.limits;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div>
        <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 8 }}>Dashboard / Reports</div>
        <h1 style={{ margin: 0, fontSize: 24 }}>Reports</h1>
        <p style={{ margin: "6px 0 0", color: "var(--on-variant)" }}>
          Generate a report, download it, or email it to a colleague. You only see reports you are allowed to run, and each one
          contains only the people and records you are allowed to see.
        </p>
      </div>

      {catalog.loading && <p>Loading reports…</p>}
      {catalog.error && <p role="alert" style={{ color: "var(--error)" }}>{catalog.error}</p>}
      {!catalog.loading && !catalog.error && reports.length === 0 && (
        <div className="empty-state"><i className="ti ti-chart-bar" /><h3>No reports are available to you</h3>
          <p>Reports appear here when your role gives you access to the data they cover.</p></div>
      )}

      <div style={{ display: "grid", gap: 14, gridTemplateColumns: "repeat(auto-fit, minmax(360px, 1fr))" }}>
        {limits && reports.map(report => <ReportCard key={report.key} report={report} limits={limits} />)}
      </div>

      {otherScreens.length > 0 && (
        <section>
          <h2 style={{ fontSize: 15, margin: "8px 0" }}>Other report screens</h2>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {otherScreens.map(screen => (
              <button key={screen.id} type="button" className="btn btn-outline" onClick={() => router.push(screen.route)} title={screen.desc}>
                <i className={`ti ${screen.icon}`} /> {screen.label}
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

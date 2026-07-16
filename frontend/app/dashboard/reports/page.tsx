import ComingSoon from "@/components/ComingSoon";

export default function ReportsPage() {
  return (
    <ComingSoon
      icon="ti-chart-bar"
      title="Reports & Analytics"
      description="Comprehensive HR analytics and exportable reports across all modules — headcount, attendance, payroll, leave utilisation, and recruitment funnel."
      features={[
        "Headcount and attrition reports",
        "Attendance and punctuality analytics",
        "Payroll cost and variance reports",
        "Leave utilisation by department and branch",
        "Recruitment funnel and time-to-hire metrics",
        "Export to Excel, PDF, and CSV",
      ]}
    />
  );
}

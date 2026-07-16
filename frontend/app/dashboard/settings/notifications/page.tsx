import ComingSoon from "@/components/ComingSoon";

export default function NotificationsConfigPage() {
  return (
    <ComingSoon
      icon="ti-bell"
      title="Notification Preferences"
      description="Control which events trigger in-app and email notifications for each role — leave approvals, payslip releases, announcements, and more."
      features={[
        "Per-role notification enable/disable controls",
        "Email and in-app notification channels",
        "Leave approval and rejection alerts",
        "Payslip release and payroll processing alerts",
        "Announcement and document publish notifications",
        "Digest mode — bundle notifications into a daily summary",
      ]}
    />
  );
}

import ComingSoon from "@/components/ComingSoon";

export default function ApprovalsPage() {
  return (
    <ComingSoon
      icon="ti-checks"
      title="Team Approvals"
      description="A unified approval inbox for leave requests, expenses, regularizations, and loan applications — all in one place with bulk approve/reject actions."
      features={[
        "Unified queue for all pending approvals",
        "Bulk approve or reject with remarks",
        "Approval history and audit trail",
        "Escalation and delegation rules",
        "Push notifications for pending items",
      ]}
    />
  );
}

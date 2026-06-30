import ComingSoon from "@/components/ComingSoon";

export default function MyRequestsPage() {
  return (
    <ComingSoon
      icon="ti-inbox"
      title="My Requests"
      description="Track all your submitted requests in one place — leave applications, expense claims, regularizations, and loan requests with real-time status updates."
      features={[
        "All leave, expense, and loan requests in one view",
        "Real-time approval status and remarks",
        "Cancel or recall pending requests",
        "Request history with timeline",
        "Download approved request letters",
      ]}
    />
  );
}

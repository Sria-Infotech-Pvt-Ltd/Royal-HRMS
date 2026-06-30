import ComingSoon from "@/components/ComingSoon";

export default function SeparationPage() {
  return (
    <ComingSoon
      icon="ti-logout"
      title="Separation & Full & Final"
      description="Manage employee exits end-to-end — resignation letters, notice period tracking, exit interviews, asset recovery, and full & final settlement calculations."
      features={[
        "Resignation and termination workflows",
        "Notice period and last working day tracking",
        "Exit interview questionnaire",
        "Asset handover checklist",
        "Full & final settlement with salary arrears",
        "Experience letter and relieving letter generation",
      ]}
    />
  );
}

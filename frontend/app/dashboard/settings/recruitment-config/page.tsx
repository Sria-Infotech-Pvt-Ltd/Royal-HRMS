import ComingSoon from "@/components/ComingSoon";

export default function RecruitmentConfigPage() {
  return (
    <ComingSoon
      icon="ti-users"
      title="Recruitment Configuration"
      description="Define interview stages, evaluation scorecards, offer letter templates, and the candidate pipeline structure for your organisation."
      features={[
        "Customisable interview stages and round names",
        "Evaluation scorecard templates per role",
        "Offer letter and rejection email templates",
        "Job portal integration settings",
        "Auto-advance rules between pipeline stages",
      ]}
    />
  );
}

"use client";

interface AssessmentsHeaderProps {
  onBack: () => void
}

/** Title and a way back. (Creating is offered from the assessment types on the page, not from here.) */
export default function AssessmentsHeader({ onBack }: AssessmentsHeaderProps) {
  return (
    <div className="page-header">
      <div>
        <div className="page-title">Assessment Management</div>
        <div className="page-sub">Build pre-onboarding assessments and assign them to people</div>
      </div>
      <div className="page-actions">
        <button type="button" className="btn btn-ghost" onClick={onBack}>
          <i className="ti ti-arrow-left" /> Back
        </button>
      </div>
    </div>
  );
}

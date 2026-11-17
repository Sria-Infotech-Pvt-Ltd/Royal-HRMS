"use client";

interface ApprovalsHeaderProps {
  onBack:    () => void
  onRefresh: () => void
  isLoading: boolean
}

/** Title, a way back, and a refresh. */
export default function ApprovalsHeader({ onBack, onRefresh, isLoading }: ApprovalsHeaderProps) {
  return (
    <div className="page-header">
      <div>
        <div className="page-title">Onboarding Approvals</div>
        <div className="page-sub">Review and approve employee onboarding submissions</div>
      </div>
      <div className="page-actions">
        <button type="button" className="btn btn-ghost" onClick={onRefresh} disabled={isLoading} suppressHydrationWarning>
          <i className={`ti ti-refresh${isLoading ? " spin" : ""}`} /> Refresh
        </button>
        <button type="button" className="btn btn-ghost" onClick={onBack}>
          <i className="ti ti-arrow-left" /> Back
        </button>
      </div>
    </div>
  );
}

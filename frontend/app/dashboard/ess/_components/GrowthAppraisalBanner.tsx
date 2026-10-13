"use client";

// Plain top-of-page callout on Growth — matches the reference layout, which
// shows this as bare text (no card/border/tint) sitting directly on the page
// background, title+subtitle stacked above the button rather than side by
// side. A button that cross-navigates to the ESS "Appraisals" tab, same
// pattern as PoliciesAssetsTab's onNavigateToDocuments prop.

interface Props {
  cycleName: string;
  onNavigateToAppraisals: () => void;
}

export default function GrowthAppraisalBanner({ cycleName, onNavigateToAppraisals }: Props) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ fontSize: 14, fontWeight: 700, color: "var(--on-bg)" }}>
        {cycleName} appraisal is open
      </div>
      <p style={{ margin: "4px 0 12px", fontSize: 12.5, color: "var(--on-variant)" }}>
        Complete your self-review, track manager and HR stages, and review your final development plan.
      </p>
      <button className="btn btn-filled btn-sm" onClick={onNavigateToAppraisals}>
        Open appraisal
      </button>
    </div>
  );
}

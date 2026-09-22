"use client";

// Secondary bordered callout at the top of Growth — NOT the purple gradient
// hero used on Home (HomeBanner.tsx), a lighter card tinted with the app's
// existing "warn" token (left border-accent + tinted background, both
// already defined in globals.css) and a button that cross-navigates to the
// ESS "Appraisals" tab, same pattern as PoliciesAssetsTab's
// onNavigateToDocuments prop.

interface Props {
  cycleName: string;
  onNavigateToAppraisals: () => void;
}

export default function GrowthAppraisalBanner({ cycleName, onNavigateToAppraisals }: Props) {
  return (
    <div
      className="card mb-16"
      style={{ background: "var(--warn-c)", borderLeft: "4px solid var(--warn)" }}
    >
      <div style={{ padding: "16px 20px", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "var(--on-bg)" }}>
            {cycleName} appraisal is open
          </div>
          <p style={{ margin: "4px 0 0", fontSize: 12.5, color: "var(--on-variant)" }}>
            Complete your self-review, track manager and HR stages, and review your final development plan.
          </p>
        </div>
        <button className="btn btn-filled btn-sm" onClick={onNavigateToAppraisals}>
          Open appraisal
        </button>
      </div>
    </div>
  );
}

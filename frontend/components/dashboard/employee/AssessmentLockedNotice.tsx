"use client";

import Link from "next/link";

/**
 * Shown in place of a dashboard widget's normal empty state when the
 * backend blocked the request with 403 because the employee has a pending
 * assessment (core.permissions.HasCompletedOnboarding). Without this,
 * widgets fell back to their generic "nothing here" text — e.g. the leave
 * balance widget said "Contact HR to credit your leave", which is actively
 * wrong: the real, actionable step is finishing the assessment, not
 * contacting HR.
 */
export default function AssessmentLockedNotice() {
  return (
    <div style={{ padding: "24px 20px", textAlign: "center" }}>
      <i className="ti ti-lock" style={{ fontSize: 24, color: "var(--warn)", display: "block", marginBottom: 8, opacity: 0.7 }} />
      <div style={{ fontSize: 13, color: "var(--on-variant)", marginBottom: 6 }}>
        Complete your pending assessment to unlock this.
      </div>
      <Link href="/onboarding/assessments" style={{ color: "var(--primary)", fontSize: 12, fontWeight: 600 }}>
        Go to Assessments →
      </Link>
    </div>
  );
}

"use client";

// Growth — appraisal-open banner, a "Growth & feedback" intro card, goals
// for the active review cycle, and a self/manager review timeline. Goals
// are plain CRUD, no approval workflow (see apps/performance/models.py:Goal's
// own docstring). Split into GrowthAppraisalBanner / GrowthGoalsCard /
// GrowthReviewTimeline to keep this file under the project's line guideline.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import GrowthAppraisalBanner from "./GrowthAppraisalBanner";
import GrowthGoalsCard, { GrowthGoal } from "./GrowthGoalsCard";
import GrowthReviewTimeline from "./GrowthReviewTimeline";
import { AppraisalActivityEntry } from "./AppraisalActivityHistory";

interface ApiReview {
  cycle_name: string;
  status: string;
  status_display: string;
  cycle_self_review_due: string | null;
  cycle_manager_review_due: string | null;
  self_submitted_at: string | null;
  manager_submitted_at: string | null;
  activity_history: AppraisalActivityEntry[];
}

interface Props {
  onNavigateToAppraisals: () => void;
}

function cycleOpenedDate(review: ApiReview | null | undefined): string | null {
  const opened = review?.activity_history?.find(entry => entry.label === "Cycle opened");
  return opened?.at ?? null;
}

export default function GrowthTab({ onNavigateToAppraisals }: Props) {
  const { data: goals, loading, error, refetch } = useFetch<GrowthGoal[]>(API.performance.myGoals);
  const { data: review } = useFetch<ApiReview>(API.performance.myReview);

  const list = goals ?? [];
  const cycleName = review?.cycle_name ?? null;

  return (
    <div>
      <div className="page-header">
        <div>
          <div className="page-title">Growth</div>
          <div className="page-sub">Goals, self-review timeline and manager feedback for the current cycle.</div>
        </div>
      </div>

      {review && review.cycle_name && (
        <GrowthAppraisalBanner cycleName={review.cycle_name} onNavigateToAppraisals={onNavigateToAppraisals} />
      )}

      <div className="card mb-16">
        <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="card-title"><i className="ti ti-heart-handshake" /> Growth &amp; feedback</div>
          <button
            className="btn btn-ghost btn-sm"
            disabled
            title="Request feedback — Coming Soon"
            style={{ cursor: "not-allowed", opacity: 0.6 }}
          >
            Request feedback
            <span style={{ fontSize: 8.5, fontWeight: 700, background: "var(--bg-high)", color: "var(--on-variant)", padding: "1px 5px", borderRadius: 99, letterSpacing: "0.04em", marginLeft: 6 }}>
              SOON
            </span>
          </button>
        </div>
        <div style={{ padding: "0 20px 16px" }}>
          <p style={{ margin: 0, fontSize: 12.5, color: "var(--on-variant)" }}>
            See your goals, review cycle and career conversations.
          </p>
        </div>
      </div>

      <GrowthGoalsCard cycleName={cycleName} goals={list} loading={loading} error={error} refetch={refetch} />

      {review && (
        <GrowthReviewTimeline
          input={{
            cycleName: review.cycle_name,
            cycleOpenedAt: cycleOpenedDate(review),
            selfReviewDue: review.cycle_self_review_due,
            managerReviewDue: review.cycle_manager_review_due,
            selfSubmittedAt: review.self_submitted_at,
            managerSubmittedAt: review.manager_submitted_at,
          }}
        />
      )}
    </div>
  );
}

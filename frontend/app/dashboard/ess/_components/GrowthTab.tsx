"use client";

// Growth — appraisal-open banner, a "Growth & feedback" page header with a
// real "Request feedback" action, goals for the active review cycle and a
// self/manager review timeline side by side, then a feedback-requests card.
// Split into GrowthAppraisalBanner / GrowthGoalsCard / GrowthReviewTimeline /
// GrowthFeedbackRequestsCard to keep this file under the project's line
// guideline.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import GrowthAppraisalBanner from "./GrowthAppraisalBanner";
import GrowthGoalsCard, { GrowthGoal } from "./GrowthGoalsCard";
import GrowthReviewTimeline from "./GrowthReviewTimeline";
import GrowthFeedbackRequestsCard from "./GrowthFeedbackRequestsCard";
import GrowthFeedbackRequestModal from "./GrowthFeedbackRequestModal";
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
  const { data: goals, loading, error } = useFetch<GrowthGoal[]>(API.performance.myGoals);
  const { data: review } = useFetch<ApiReview>(API.performance.myReview);
  const [showFeedbackRequest, setShowFeedbackRequest] = useState(false);
  const [feedbackKey, setFeedbackKey] = useState(0);

  const list = goals ?? [];
  const cycleName = review?.cycle_name ?? null;

  return (
    <div>
      {review && review.cycle_name && (
        <GrowthAppraisalBanner cycleName={review.cycle_name} onNavigateToAppraisals={onNavigateToAppraisals} />
      )}

      <div className="page-header">
        <div>
          <div className="page-title">Growth &amp; feedback</div>
          <div className="page-sub">See your goals, review cycle and career conversations.</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-filled" onClick={() => setShowFeedbackRequest(true)} suppressHydrationWarning>
            Request feedback
          </button>
        </div>
      </div>

      <div className="grid-2" style={{ alignItems: "stretch", marginBottom: 16 }}>
        <GrowthGoalsCard cycleName={cycleName} goals={list} loading={loading} error={error} />
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

      <GrowthFeedbackRequestsCard key={feedbackKey} />

      {showFeedbackRequest && (
        <GrowthFeedbackRequestModal
          cycleName={cycleName}
          onClose={() => setShowFeedbackRequest(false)}
          onSubmitted={() => { setShowFeedbackRequest(false); setFeedbackKey(k => k + 1); }}
        />
      )}
    </div>
  );
}

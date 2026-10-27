"use client";

// Growth — appraisal-open banner, a "Growth & feedback" page header with a
// real "Request feedback" action, goals for the active review cycle and a
// self/manager review timeline side by side, then a feedback-requests card.
// Split into GrowthAppraisalBanner / GrowthGoalsCard / GrowthReviewTimeline /
// FeedbackRequestsCard to keep this file under the project's line
// guideline.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import GrowthAppraisalBanner from "./GrowthAppraisalBanner";
import GrowthGoalsCard, { GrowthGoal } from "./GrowthGoalsCard";
import GrowthReviewTimeline from "./GrowthReviewTimeline";
import { AppraisalActivityEntry } from "./AppraisalActivityHistory";
import FeedbackRequestModal from "./FeedbackRequestModal";
import FeedbackRequestsCard from "./FeedbackRequestsCard";

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
  const [showFeedbackModal, setShowFeedbackModal] = useState(false);
  const [feedbackKey, setFeedbackKey] = useState(0);

  const list = goals ?? [];
  // `review` is {} (not null) when there's no active cycle — see MyReviewView.
  // Checked by key count, not truthiness, so an empty object is never
  // mistaken for a real review (that's what rendered "undefined cycle
  // opened" below before this fix).
  const hasCycle = !!review && Object.keys(review).length > 0;
  const cycleName = hasCycle ? review!.cycle_name : null;

  return (
    <div>
      {hasCycle && (
        <GrowthAppraisalBanner cycleName={review!.cycle_name} onNavigateToAppraisals={onNavigateToAppraisals} />
      )}

      <div className="card mb-16">
        <div className="card-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="card-title"><i className="ti ti-heart-handshake" /> Growth &amp; feedback</div>
          <button className="btn btn-ghost btn-sm" type="button" onClick={() => setShowFeedbackModal(true)}>
            Request feedback
          </button>
        </div>
        <div style={{ padding: "0 20px 16px" }}>
          <p style={{ margin: 0, fontSize: 12.5, color: "var(--on-variant)" }}>
            See your goals, review cycle and career conversations.
          </p>
        </div>
      </div>

      <FeedbackRequestsCard refreshKey={feedbackKey} />

      <div className="grid-2" style={{ alignItems: "stretch", marginBottom: 16 }}>
        <GrowthGoalsCard cycleName={cycleName} goals={list} loading={loading} error={error} refetch={refetch} />
        {hasCycle ? (
          <GrowthReviewTimeline
            input={{
              cycleName: review!.cycle_name,
              cycleOpenedAt: cycleOpenedDate(review),
              selfReviewDue: review!.cycle_self_review_due,
              managerReviewDue: review!.cycle_manager_review_due,
              selfSubmittedAt: review!.self_submitted_at,
              managerSubmittedAt: review!.manager_submitted_at,
            }}
          />
        ) : (
          <div className="card">
            <div className="card-header">
              <div className="card-title"><i className="ti ti-timeline" /> Review timeline</div>
            </div>
            <div className="empty-state">
              <i className="ti ti-timeline" />
              <h3>No active review cycle</h3>
              <p>Your timeline will appear when HR opens a cycle.</p>
            </div>
          </div>
        )}
      </div>

      {showFeedbackModal && (
        <FeedbackRequestModal
          cycleName={cycleName}
          onClose={() => setShowFeedbackModal(false)}
          onSent={() => setFeedbackKey(k => k + 1)}
        />
      )}
    </div>
  );
}

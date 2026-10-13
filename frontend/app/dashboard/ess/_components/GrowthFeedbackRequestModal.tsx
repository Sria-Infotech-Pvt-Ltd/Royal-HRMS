"use client";

// "Feedback request" modal — submits via the generic HR Help support-request
// endpoint (topic='feedback_request'), same reuse pattern as
// ProfileCorrectionModal.tsx/AssetRequestModal.tsx: peer-to-peer feedback has
// no dedicated model of its own (see apps/performance/models.py's own scope
// notes), so the review cycle/feedback-from/topic are folded into
// HRHelpRequest.message rather than adding a new Django model for this one
// free-text request.

import { useState } from "react";
import RequestModal from "@/components/RequestModal";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

export const FEEDBACK_REQUEST_TOPIC = "feedback_request";

// "Continuous feedback" / "Career conversation" are fixed, cycle-independent
// options alongside the real active review cycle name (passed in as
// `cycleName`) — feedback doesn't have to be tied to a formal review cycle.
const FIXED_CYCLE_OPTIONS = ["Continuous feedback", "Career conversation"];

interface Props {
  cycleName: string | null;
  onClose: () => void;
  onSubmitted: () => void;
}

export default function GrowthFeedbackRequestModal({ cycleName, onClose, onSubmitted }: Props) {
  const cycleOptions = [...(cycleName ? [cycleName] : []), ...FIXED_CYCLE_OPTIONS];
  const [reviewCycle, setReviewCycle] = useState(cycleOptions[0]);
  const [feedbackFrom, setFeedbackFrom] = useState("");
  const [topic, setTopic] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setError(null);
    if (!feedbackFrom.trim()) { setError("Please enter who you'd like feedback from."); return; }
    if (topic.trim().length < 10) { setError("Please describe what feedback would help you in at least 10 characters."); return; }
    setSubmitting(true);
    try {
      const message = `Review cycle: ${reviewCycle}. Feedback from: ${feedbackFrom.trim()}. Topic/goal: ${topic.trim()}`;
      await clientApi.post(API.hrHelp.list, { topic: FEEDBACK_REQUEST_TOPIC, priority: "normal", message });
      onSubmitted();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg ?? "Failed to submit request. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <RequestModal
      title={<><i className="ti ti-message-heart" /> Feedback request</>}
      onClose={onClose}
      onSubmit={handleSubmit}
      submitting={submitting}
      error={error}
    >
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Review cycle</label>
          <select className="field-input field-select" value={reviewCycle} onChange={e => setReviewCycle(e.target.value)}>
            {cycleOptions.map(opt => <option key={opt} value={opt}>{opt}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Feedback from</label>
          <input
            className="field-input"
            value={feedbackFrom}
            onChange={e => setFeedbackFrom(e.target.value)}
            placeholder="Manager or colleague"
          />
        </div>
      </div>
      <div className="field-group">
        <label className="field-label">Topic / goal</label>
        <textarea
          className="field-input"
          rows={3}
          value={topic}
          onChange={e => setTopic(e.target.value)}
          placeholder="What feedback would help you?"
        />
      </div>
    </RequestModal>
  );
}

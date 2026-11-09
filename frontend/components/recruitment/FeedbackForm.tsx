"use client";

import { useState } from "react";
import { feedbackProblem } from "@/hooks/useInterviewFeedback";
import type { FeedbackEntry, FeedbackInput, FeedbackRecommendation } from "@/types/interviewFeedback";

const RECOMMENDATIONS: { value: FeedbackRecommendation; label: string }[] = [
  { value: "recommend", label: "Recommend" },
  { value: "hold", label: "Undecided" },
  { value: "not_recommend", label: "Do not recommend" },
];

interface FeedbackFormProps {
  initial: FeedbackEntry | null;
  isSaving: boolean;
  serverError: string;
  onSubmit: (input: FeedbackInput) => void;
  onCancel: () => void;
}

/** Rating (1-5), recommendation and comments — what an interviewer submits for an assigned interview. */
export default function FeedbackForm({ initial, isSaving, serverError, onSubmit, onCancel }: FeedbackFormProps) {
  const [rating, setRating] = useState(initial?.rating ?? 0);
  const [recommendation, setRecommendation] = useState<FeedbackRecommendation | "">(initial?.recommendation ?? "");
  const [comments, setComments] = useState(initial?.comments ?? "");
  const [localError, setLocalError] = useState("");

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const problem = feedbackProblem({ rating, recommendation, comments });
    setLocalError(problem);
    if (problem || recommendation === "") return;
    onSubmit({ rating, recommendation, comments: comments.trim() });
  }

  const message = localError || serverError;
  return (
    <form onSubmit={handleSubmit} style={{ display: "grid", gap: 14 }}>
      <fieldset style={{ border: 0, padding: 0 }}>
        <legend className="field-label">Rating</legend>
        <div style={{ display: "flex", gap: 8 }}>
          {[1, 2, 3, 4, 5].map(value => (
            <button key={value} type="button" aria-pressed={rating === value}
              className={`btn btn-sm ${rating === value ? "btn-filled" : "btn-ghost"}`} onClick={() => setRating(value)}>
              {value}
            </button>
          ))}
        </div>
      </fieldset>
      <fieldset style={{ border: 0, padding: 0 }}>
        <legend className="field-label">Recommendation</legend>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {RECOMMENDATIONS.map(option => (
            <button key={option.value} type="button" aria-pressed={recommendation === option.value}
              className={`btn btn-sm ${recommendation === option.value ? "btn-filled" : "btn-ghost"}`}
              onClick={() => setRecommendation(option.value)}>
              {option.label}
            </button>
          ))}
        </div>
      </fieldset>
      <label className="field-label" htmlFor="feedback-comments">Comments</label>
      <textarea id="feedback-comments" className="field-input" rows={5} value={comments}
        onChange={event => setComments(event.target.value)} maxLength={5000} />
      {message && <p role="alert" style={{ color: "var(--error)", margin: 0 }}>{message}</p>}
      <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
        <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={isSaving}>Cancel</button>
        <button type="submit" className="btn btn-filled" disabled={isSaving}>
          {isSaving ? "Saving…" : initial ? "Update feedback" : "Submit feedback"}
        </button>
      </div>
    </form>
  );
}

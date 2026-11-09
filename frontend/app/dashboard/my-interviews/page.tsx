"use client";

// The interviewer's page: only the interviews assigned to the signed-in user, and a form to submit feedback on each.
import { useState } from "react";
import Modal from "@/components/Modal";
import FeedbackForm from "@/components/recruitment/FeedbackForm";
import { useFetch } from "@/hooks/useFetch";
import { useSubmitFeedback } from "@/hooks/useInterviewFeedback";
import { API } from "@/lib/api/endpoints";
import type { FeedbackInput, MyInterview } from "@/types/interviewFeedback";

interface InterviewPage {
  results: MyInterview[];
}

export default function MyInterviewsPage() {
  const { data, loading, error, refetch } = useFetch<InterviewPage>(API.recruitment.myInterviews);
  const { submit, isSaving, error: saveError } = useSubmitFeedback();
  const [active, setActive] = useState<MyInterview | null>(null);

  async function handleSubmit(input: FeedbackInput) {
    if (!active) return;
    const saved = await submit(active.id, input);
    if (saved) {
      setActive(null);
      refetch();
    }
  }

  const interviews = data?.results ?? [];
  return (
    <div className="page-content">
      <h1 style={{ fontSize: 22, marginBottom: 12 }}>My Interviews</h1>
      {loading && <p>Loading…</p>}
      {error && <p role="alert" style={{ color: "var(--error)" }}>{error}</p>}
      {!loading && !error && interviews.length === 0 && <p>No interviews are assigned to you.</p>}
      <div style={{ display: "grid", gap: 12 }}>
        {interviews.map(interview => (
          <article key={interview.id} style={{ border: "1px solid var(--outline-variant, #ddd)", borderRadius: 10, padding: 14 }}>
            <strong>{interview.candidate_name}</strong> — {interview.position_applied}
            <div style={{ color: "var(--on-variant)", fontSize: ".85rem", margin: "4px 0 8px" }}>
              {interview.interview_date} {interview.interview_time ?? ""} · {interview.interview_mode_label}
              {interview.branch ? ` · ${interview.branch}` : ""} · {interview.status_label}
              {interview.meeting_link && <> · <a href={interview.meeting_link} target="_blank" rel="noreferrer">Join link</a></>}
            </div>
            {interview.my_feedback && (
              <p style={{ margin: "0 0 8px" }}>
                Your feedback: {interview.my_feedback.rating}/5, {interview.my_feedback.recommendation_label}
              </p>
            )}
            {interview.can_submit ? (
              <button className="btn btn-filled btn-sm" onClick={() => setActive(interview)}>
                {interview.my_feedback ? "Update feedback" : "Submit feedback"}
              </button>
            ) : (
              <span className="badge badge-neutral">Feedback closed</span>
            )}
          </article>
        ))}
      </div>
      {active && (
        <Modal title={`Feedback — ${active.candidate_name}`} onClose={() => setActive(null)} closeDisabled={isSaving}>
          <FeedbackForm initial={active.my_feedback} isSaving={isSaving} serverError={saveError}
            onSubmit={handleSubmit} onCancel={() => setActive(null)} />
        </Modal>
      )}
    </div>
  );
}

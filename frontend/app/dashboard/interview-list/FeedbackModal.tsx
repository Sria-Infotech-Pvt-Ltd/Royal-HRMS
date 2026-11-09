"use client";

import Modal from "@/components/Modal";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { CandidateFeedbackData } from "@/types/interviewFeedback";

interface FeedbackModalProps {
  candidateId: number;
  candidateName: string;
  onClose: () => void;
}

/** HR's read-only view of every interviewer's feedback on one candidate, with the summary. */
export function FeedbackModal({ candidateId, candidateName, onClose }: FeedbackModalProps) {
  const { data, loading, error } = useFetch<CandidateFeedbackData>(API.recruitment.candidateFeedback(candidateId));
  const summary = data?.summary;
  return (
    <Modal title={`Interview feedback — ${candidateName}`} onClose={onClose} size="lg">
      {loading && <p>Loading…</p>}
      {error && <p role="alert" style={{ color: "var(--error)" }}>{error}</p>}
      {data && (
        <div style={{ display: "grid", gap: 12 }}>
          {summary && summary.count > 0 ? (
            <p style={{ margin: 0 }}>
              {summary.count} submitted · average {summary.average_rating ?? "—"}/5 · {summary.recommend} recommend,{" "}
              {summary.undecided} undecided, {summary.not_recommend} do not recommend
            </p>
          ) : (
            <p style={{ margin: 0 }}>No interviewer has submitted feedback yet. A candidate cannot be marked Selected until at least one has.</p>
          )}
          {data.feedback.map(entry => (
            <article key={entry.id} style={{ border: "1px solid var(--outline-variant, #ddd)", borderRadius: 8, padding: 12 }}>
              <strong>{entry.interviewer}</strong> — {entry.rating}/5, {entry.recommendation_label}
              <p style={{ margin: "6px 0 0", whiteSpace: "pre-wrap" }}>{entry.comments}</p>
            </article>
          ))}
        </div>
      )}
    </Modal>
  );
}

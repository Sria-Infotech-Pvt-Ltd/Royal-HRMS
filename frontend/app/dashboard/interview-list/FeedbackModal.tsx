"use client";

import Modal from "@/components/Modal";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { CandidateFeedbackData } from "@/types/interviewFeedback";
import { useT } from "@/hooks/useI18n";

interface FeedbackModalProps {
  candidateId: number;
  candidateName: string;
  onClose: () => void;
}

/** HR's read-only view of every interviewer's feedback on one candidate, with the summary. */
export function FeedbackModal({ candidateId, candidateName, onClose }: FeedbackModalProps) {
  const t = useT();
  const { data, loading, error } = useFetch<CandidateFeedbackData>(API.recruitment.candidateFeedback(candidateId));
  const summary = data?.summary;
  return (
    <Modal title={t("Interview feedback — {name}", { name: candidateName })} onClose={onClose} size="lg">
      {loading && <p>{t("Loading…")}</p>}
      {error && <p role="alert" style={{ color: "var(--error)" }}>{error}</p>}
      {data && (
        <div style={{ display: "grid", gap: 12 }}>
          {summary && summary.count > 0 ? (
            <p style={{ margin: 0 }}>
              {t("{count} submitted · average {average}/5 · {recommend} recommend, {undecided} undecided, {notRecommend} do not recommend", {
                count: summary.count, average: summary.average_rating ?? "—", recommend: summary.recommend,
                undecided: summary.undecided, notRecommend: summary.not_recommend,
              })}
            </p>
          ) : (
            <p style={{ margin: 0 }}>{t("No interviewer has submitted feedback yet. A candidate cannot be marked Selected until at least one has.")}</p>
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

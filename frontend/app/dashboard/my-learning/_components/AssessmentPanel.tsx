"use client";

// The course's linked assessment (questions, pass mark and attempt limit come
// from the Assessments module; the server scores it).

import { useState } from "react";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { apiError, type AssessmentState } from "@/lib/training";

interface Question { id: string; question: string; section: string; options: { key: string; text: string }[] }
interface Result { score: number; max_score: number; percentage: number; pass_percentage: number; passed: boolean }

export default function AssessmentPanel({ assignmentId, state, onDone }: {
  assignmentId: string; state: AssessmentState; onDone: () => void;
}) {
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  // The attempt in progress / just submitted is a retake after passing.
  const [retake, setRetake] = useState(false);
  const { showToast } = useToast();

  async function start() {
    setBusy(true);
    setResult(null);
    setRetake(!!state.passed);
    try {
      const res = await clientApi.post<{ data: { questions: Question[] } }>(API.training.myAssessment(assignmentId, "start"));
      setQuestions(res.data.data.questions);
      setAnswers({});
    } catch (e) {
      showToast(apiError(e, "The assessment could not be started."), "error");
    } finally {
      setBusy(false);
    }
  }

  async function submit() {
    if (!questions) return;
    const missing = questions.filter(q => !answers[q.id]).length;
    if (missing && !window.confirm(`${missing} question(s) unanswered. Submit anyway?`)) return;
    setBusy(true);
    try {
      const res = await clientApi.post<{ data: Result }>(API.training.myAssessment(assignmentId, "submit"), { answers });
      const r = res.data.data;
      setResult(r);
      if (retake) {
        const best = Math.max(state.best_score_percent ?? 0, r.percentage);
        showToast(`Retake score ${r.percentage}% — your best score is ${best}%.`, "info");
      } else {
        showToast(r.passed ? `Passed — ${r.percentage}%`
          : `Not passed — ${r.percentage}% (pass mark ${r.pass_percentage}%)`, r.passed ? "success" : "error");
      }
      setQuestions(null);
      onDone();
    } catch (e) {
      showToast(apiError(e, "The assessment could not be submitted."), "error");
    } finally {
      setBusy(false);
    }
  }

  const attemptsText = state.max_attempts
    ? `${state.attempts_used ?? 0} of ${state.max_attempts} attempts used`
    : "Unlimited attempts";

  return (
    <div className="card card-body" data-testid="assessment-panel">
      <div style={{ fontWeight: 600, fontSize: 15 }}>{state.title}</div>
      <div className="text-[12px] text-[var(--on-variant)] mt-1 mb-3">
        Pass mark {state.pass_percentage}% · {attemptsText}
        {state.time_limit_mins ? ` · ${state.time_limit_mins} minute time limit` : ""}
      </div>

      {result && retake && (
        <div className="alert alert-info mb-16">
          <i className="ti ti-info-circle" /> Retake score {result.percentage}%. Your best score is{" "}
          {Math.max(state.best_score_percent ?? 0, result.percentage)}% — the course stays completed.
        </div>
      )}
      {result && !retake && (
        <div className={`alert ${result.passed ? "alert-success" : "alert-error"} mb-16`}>
          {result.passed ? "Passed" : "Not passed"} — {result.percentage}% (pass mark {result.pass_percentage}%).
        </div>
      )}

      {!questions && (
        <>
          {state.passed && (
            <div className="text-[13px] mb-2">
              <i className="ti ti-circle-check" style={{ color: "var(--success)" }} /> You passed — best score{" "}
              <strong>{state.best_score_percent}%</strong>.
              {state.can_retake && (
                <div className="text-[12px] text-[var(--on-variant)] mt-1">
                  Optional: retake it to improve your score
                  {state.attempts_left != null ? ` (${state.attempts_left} retake${state.attempts_left === 1 ? "" : "s"} left)` : ""}.
                  Your best score is kept and the course stays completed.
                </div>
              )}
            </div>
          )}
          {state.has_questions === false && (
            <div className="text-[13px]">This assessment has no questions yet — contact HR.</div>
          )}
          {!state.passed && !state.unlocked && state.has_questions !== false && (
            <div className="text-[13px] text-[var(--on-variant)]">Complete the required learning materials to unlock it.</div>
          )}
          {!state.passed && state.unlocked && !state.can_attempt && state.has_questions !== false && !state.starts_on && (
            <div className="text-[13px]">No attempts left. HR can reset your attempts.</div>
          )}
          {state.last_result && !result && !state.passed && (
            <div className="text-[13px] mb-2">Last attempt: {state.last_result.percentage}%.</div>
          )}
          {state.can_attempt && (
            <button className="btn btn-filled" onClick={start} disabled={busy}>
              {busy ? "Starting…" : state.passed ? "Retake to improve score"
                : (state.attempts_used ? "Try again" : "Start assessment")}
            </button>
          )}
        </>
      )}

      {questions && (
        <div>
          {questions.map((q, i) => (
            <fieldset key={q.id} style={{ border: 0, padding: "10px 0", borderBottom: "1px solid var(--outline-v)" }}>
              <legend style={{ fontSize: 13, fontWeight: 600 }}>
                {i + 1}. {q.question}{q.section ? <span className="text-[11px] text-[var(--on-variant)]"> · {q.section}</span> : null}
              </legend>
              {q.options.map(o => (
                <label key={o.key} style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 13, padding: "4px 0" }}>
                  <input type="radio" name={`q-${q.id}`} checked={answers[q.id] === o.key}
                         onChange={() => setAnswers(a => ({ ...a, [q.id]: o.key }))} />
                  {o.text}
                </label>
              ))}
            </fieldset>
          ))}
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 12 }}>
            <button className="btn btn-filled" onClick={submit} disabled={busy}>{busy ? "Submitting…" : "Submit"}</button>
          </div>
        </div>
      )}
    </div>
  );
}

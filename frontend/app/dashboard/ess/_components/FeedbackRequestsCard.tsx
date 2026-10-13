"use client";

// Feedback you asked for (with the answers) and feedback others asked of you
// (with Respond / Decline) — the reference's "Feedback requests" card, backed
// by real requests.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { formatDate } from "@/lib/formatDate";
import Modal from "@/components/Modal";
import { useToast } from "@/components/ToastProvider";
import type { FeedbackRequest } from "@/types/feedback";

interface Page { results: FeedbackRequest[] }

interface Props { refreshKey: number }

export default function FeedbackRequestsCard({ refreshKey }: Props) {
  const { showToast } = useToast();
  const mine = useFetch<Page>(`${API.performance.feedbackRequests}?scope=mine&r=${refreshKey}`);
  const forMe = useFetch<Page>(`${API.performance.feedbackRequests}?scope=for-me&r=${refreshKey}`);
  const [answering, setAnswering] = useState<FeedbackRequest | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const asked = mine.data?.results ?? [];
  const toAnswer = (forMe.data?.results ?? []).filter(r => r.can_respond);

  async function respond(decline: boolean) {
    if (!answering) return;
    if (!decline && !text.trim()) { setError("Write your feedback before sending it."); return; }
    setBusy(true); setError("");
    try {
      await clientApi.post(API.performance.feedbackRespond(answering.id), decline ? { decline: true } : { response: text.trim() });
      showToast(decline ? "Request declined." : "Feedback sent.", "success");
      setAnswering(null); setText("");
      mine.refetch(); forMe.refetch();
    } catch (e: unknown) {
      setError((e as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Could not send your response.");
    } finally { setBusy(false); }
  }

  return (
    <>
      {toAnswer.length > 0 && (
        <section className="ess-card">
          <h2>Feedback asked of you</h2>
          <p>Colleagues who would value your perspective.</p>
          <div className="ess-list">
            {toAnswer.map(r => (
              <div key={r.id} className="ess-row">
                <div><b>{r.requester_name} · {r.cycle_label}</b><small>{r.topic}</small></div>
                <button className="btn btn-filled btn-sm" type="button" onClick={() => { setAnswering(r); setText(""); setError(""); }}>Respond</button>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="ess-card">
        <h2>Feedback requests</h2>
        <p>Requests you have made and what came back.</p>
        <div className="ess-list">
          {asked.length === 0 ? (
            <div className="ess-row"><div><b>No feedback requests</b><small>Ask a manager or colleague for focused feedback.</small></div></div>
          ) : asked.map(r => (
            <div key={r.id} className="ess-row">
              <div>
                <b>{r.recipient_name} · {r.cycle_label}</b>
                <small>{formatDate(r.created_at)} · {r.topic.slice(0, 90)}</small>
                {r.status === "provided" && <small style={{ color: "var(--ink)", marginTop: 6 }}>&ldquo;{r.response}&rdquo;</small>}
              </div>
              <span className={`state${r.status === "pending" ? "" : " ok"}`}>{r.status_display.toUpperCase()}</span>
            </div>
          ))}
        </div>
      </section>

      {answering && (
        <Modal
          title={<h2 className="modal-title">Give <em style={{ color: "var(--brand-ink)" }}>feedback</em></h2>}
          onClose={() => setAnswering(null)} closeDisabled={busy}
          footer={
            <>
              <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => respond(true)}>Decline</button>
              <button className="btn btn-filled" type="button" disabled={busy} onClick={() => respond(false)}>{busy ? "Sending…" : "Send feedback"}</button>
            </>
          }
        >
          <div className="space-y-4">
            <p className="hint">{answering.requester_name} asked: {answering.topic}</p>
            {error && <div className="alert alert-error">{error}</div>}
            <div className="ess-field">
              <label htmlFor="fbAnswer">YOUR FEEDBACK</label>
              <textarea id="fbAnswer" value={text} onChange={e => setText(e.target.value)} placeholder="Specific, constructive and kind." />
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}

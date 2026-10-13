"use client";

// "Request feedback" — ask a manager, peer or direct report for focused
// feedback. The server only allows people the requester works with, so the
// list below is exactly who they can pick.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import Modal from "@/components/Modal";
import { useToast } from "@/components/ToastProvider";
import type { FeedbackColleague } from "@/types/feedback";

interface Props {
  /** Name of the active appraisal cycle, offered first when there is one. */
  cycleName: string | null;
  onClose: () => void;
  onSent: () => void;
}

export default function FeedbackRequestModal({ cycleName, onClose, onSent }: Props) {
  const { showToast } = useToast();
  const { data: colleagues, loading } = useFetch<FeedbackColleague[]>(API.performance.feedbackColleagues);
  const cycles = [...(cycleName ? [cycleName] : []), "Continuous feedback", "Career conversation"];

  const [cycle, setCycle] = useState(cycles[0]);
  const [recipient, setRecipient] = useState("");
  const [topic, setTopic] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function send() {
    if (!recipient) { setError("Choose who you would like feedback from."); return; }
    if (!topic.trim()) { setError("Describe what feedback would help you."); return; }
    setSaving(true); setError("");
    try {
      await clientApi.post(API.performance.feedbackRequests, { recipient, cycle_label: cycle, topic: topic.trim() });
      showToast("Feedback request sent.", "success");
      onSent(); onClose();
    } catch (e: unknown) {
      setError((e as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Could not send this request.");
    } finally { setSaving(false); }
  }

  return (
    <Modal
      title={<h2 className="modal-title">Request <em style={{ color: "var(--brand-ink)" }}>feedback</em></h2>}
      onClose={onClose} closeDisabled={saving}
      footer={
        <>
          <button className="btn btn-ghost" type="button" onClick={onClose} disabled={saving}>Cancel</button>
          <button className="btn btn-filled" type="button" onClick={send} disabled={saving}>{saving ? "Sending…" : "Submit request"}</button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="hint">Complete the required information. Your request goes straight to the person you pick.</p>
        {error && <div className="alert alert-error">{error}</div>}
        <div className="ess-form">
          <div className="ess-field">
            <label htmlFor="fbCycle">REVIEW CYCLE</label>
            <select id="fbCycle" value={cycle} onChange={e => setCycle(e.target.value)}>
              {cycles.map(c => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="ess-field">
            <label htmlFor="fbFrom">FEEDBACK FROM</label>
            <select id="fbFrom" value={recipient} onChange={e => setRecipient(e.target.value)} disabled={loading}>
              <option value="">{loading ? "Loading…" : "Manager or colleague"}</option>
              {(colleagues ?? []).map(c => <option key={c.id} value={c.id}>{c.name} · {c.relation}</option>)}
            </select>
          </div>
          <div className="ess-field" style={{ gridColumn: "1 / -1" }}>
            <label htmlFor="fbTopic">TOPIC / GOAL</label>
            <textarea id="fbTopic" value={topic} onChange={e => setTopic(e.target.value)} placeholder="What feedback would help you?" />
          </div>
        </div>
        {!loading && (colleagues ?? []).length === 0 && (
          <p className="hint">You have no manager, peers or direct reports on record yet, so there is nobody to ask. Ask HR to confirm your reporting line.</p>
        )}
      </div>
    </Modal>
  );
}

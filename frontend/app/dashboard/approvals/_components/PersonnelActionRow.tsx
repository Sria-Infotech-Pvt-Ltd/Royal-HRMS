"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import Modal from "@/components/Modal";
import type { PersonnelActionRequest } from "@/types/personnelAction";
import { personnelEffective, personnelValuesSummary } from "./personnelActionFormat";

interface Props {
  request: PersonnelActionRequest;
  onChanged: () => void;
}

const STATE_CLASS: Record<string, string> = {
  pending: "warn", applied: "", rejected: "crit", cancelled: "", failed: "crit",
};

function errorMessage(error: unknown): string {
  return (error as { response?: { data?: { message?: string } } })?.response?.data?.message
    ?? "Something went wrong. Please try again.";
}

export default function PersonnelActionRow({ request: r, onChanged }: Props) {
  const { showToast } = useToast();
  const [busy, setBusy] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [note, setNote] = useState("");
  const [noteError, setNoteError] = useState("");

  async function approve() {
    setBusy(true);
    try {
      const { data } = await clientApi.post<{ data: PersonnelActionRequest }>(API.actionRequests.approve(r.id), {});
      const status = data.data.status;
      showToast(
        status === "applied" ? `${r.action_label} approved and applied.`
          : status === "failed" ? "Approved, but the change could not be applied — see the request."
          : `Approved. Now with ${data.data.current_step_label}.`,
        status === "failed" ? "error" : "success",
      );
      onChanged();
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  }

  async function reject() {
    if (!note.trim()) { setNoteError("Add a reason so the person who raised it knows what to change."); return; }
    setBusy(true);
    try {
      await clientApi.post(API.actionRequests.reject(r.id), { note: note.trim() });
      showToast(`${r.action_label} rejected.`, "success");
      setRejecting(false);
      setNote("");
      onChanged();
    } catch (error) {
      setNoteError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    setBusy(true);
    try {
      await clientApi.post(API.actionRequests.cancel(r.id), {});
      showToast(`${r.action_label} cancelled.`, "success");
      onChanged();
    } catch (error) {
      showToast(errorMessage(error), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="case-row">
      <b>
        {r.employee.code}
        <br /><small>{r.employee.name}</small>
      </b>
      <span>
        {r.action_label}
        <br /><small style={{ color: "var(--muted)" }}>{personnelValuesSummary(r) || r.reason}</small>
        <br /><small style={{ color: "var(--faint)" }}>Route: {r.route}</small>
      </span>
      <span>{personnelEffective(r.effective_from)}</span>
      <span>
        {r.status === "pending" ? r.current_step_label : `Raised by ${r.raised_by_name}`}
        <br /><span className={`state ${STATE_CLASS[r.status] ?? ""}`}>{r.status_display}</span>
        {r.status === "rejected" && r.decision_note && <><br /><small style={{ color: "var(--crit)" }}>{r.decision_note}</small></>}
        {r.status === "failed" && r.apply_error && <><br /><small style={{ color: "var(--crit)" }}>{r.apply_error}</small></>}
      </span>
      <span className="case-actions" style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
        {r.can_decide && (
          <>
            <button className="btn btn-filled btn-sm" disabled={busy} onClick={approve} type="button">Approve</button>
            <button className="btn btn-outline btn-sm" disabled={busy} onClick={() => setRejecting(true)} type="button">Reject</button>
          </>
        )}
        {r.can_cancel && !r.can_decide && (
          <button className="btn btn-outline btn-sm" disabled={busy} onClick={cancel} type="button">Cancel request</button>
        )}
      </span>

      {rejecting && (
        <Modal
          title={<h2 className="modal-title">Reject <em style={{ color: "var(--brand-ink)" }}>{r.action_label.toLowerCase()}</em></h2>}
          onClose={() => { setRejecting(false); setNoteError(""); }}
          closeDisabled={busy}
          footer={
            <>
              <button className="btn btn-ghost" disabled={busy} onClick={() => setRejecting(false)} type="button">Cancel</button>
              <button className="btn btn-filled" disabled={busy} onClick={reject} type="button">{busy ? "Rejecting…" : "Reject request"}</button>
            </>
          }
        >
          <p className="hint" style={{ marginBottom: 10 }}>{r.employee.name} · {r.employee.code} — {personnelValuesSummary(r)}</p>
          <div className="f">
            <label>Reason <span className="req">*</span></label>
            <textarea className="finput" rows={3} value={note} onChange={e => { setNote(e.target.value); setNoteError(""); }} placeholder="What should be changed or reconsidered?" />
            {noteError && <span className="errtxt" style={{ display: "block" }}>{noteError}</span>}
          </div>
        </Modal>
      )}
    </div>
  );
}

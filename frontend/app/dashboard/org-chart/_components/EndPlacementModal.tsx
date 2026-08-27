"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { Position } from "@/types/orgStructure";

interface Props {
  position: Position | null;
  onClose: () => void;
  onEnded: () => void;
}

function Spin() {
  return <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

export default function EndPlacementModal({ position, onClose, onEnded }: Props) {
  const [lastDay, setLastDay] = useState(today());
  const [dateError, setDateError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function submit() {
    if (!position) return;
    if (!lastDay) { setDateError("Last day is required."); return; }
    if (position.holder_since && lastDay < position.holder_since) {
      setDateError(`Can't be before ${position.holder_since}, when this placement started.`);
      return;
    }
    setIsSubmitting(true);
    setSubmitError(null);
    try {
      await clientApi.post(API.orgStructure.positions.placementsEnd(position.id), { effective_to: lastDay });
      onEnded();
    } catch (err: unknown) {
      setSubmitError((err as { message?: string })?.message ?? "Failed to end this placement.");
    } finally {
      setIsSubmitting(false);
    }
  }

  if (!position) return null;

  return (
    <Modal
      title={<><i className="ti ti-door-exit" style={{ marginRight: 8 }} />End placement</>}
      onClose={onClose}
      maxWidth={420}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={submit} disabled={isSubmitting}>
            {isSubmitting ? <><Spin />&nbsp;Saving…</> : "End placement"}
          </button>
        </>
      }
    >
      {submitError && (
        <div style={{ marginBottom: 14, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 8, color: "var(--error)", fontSize: 13 }}>
          {submitError}
        </div>
      )}
      <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 14 }}>
        {position.title} · {position.org_unit_name} — currently held by <b>{position.holder_name}</b>
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Last day <span style={{ color: "var(--error)" }}>*</span></label>
        <input
          className={`field-input${dateError ? " field-error" : ""}`}
          type="date"
          min={position.holder_since ?? undefined}
          value={lastDay}
          onChange={e => { setLastDay(e.target.value); setDateError(null); }}
        />
        {dateError && <p className="field-error-msg">{dateError}</p>}
      </div>

      <div style={{ fontSize: 11.5, color: "var(--outline)" }}>
        {position.holder_name} stays the holder through this date. The seat becomes vacant the day after.
      </div>
    </Modal>
  );
}

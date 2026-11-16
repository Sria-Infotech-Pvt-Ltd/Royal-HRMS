"use client";

// Inside an open HR Help row: for a profile correction that carries a new value, shows what is asked (current -> requested) and lets
// HR / the System Admin open the employee's record, apply the requested value (which also resolves the ticket) or decline it.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { HrHelpRequest, ProfileChangeField } from "@/types/hrHelp";
import ProfileChangeValueInput from "./ProfileChangeValueInput";

interface HrHelpChangePanelProps {
  entry: HrHelpRequest;
  /** The note typed in the row's Response box; sent with the decision and shown to the employee. */
  note: string;
  onDecided: () => void;
}

const DECISION_TEXT: Record<"applied" | "rejected", string> = {
  applied: "Applied to the employee's record.",
  rejected: "Declined.",
};

export default function HrHelpChangePanel({ entry, note, onDecided }: HrHelpChangePanelProps) {
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [typedValue, setTypedValue] = useState("");
  // An older request has no stored new value: HR types it here, with the right input for the field.
  const needsValue = !entry.change_field && Boolean(entry.change_suggested_key);
  const { data: fields } = useFetch<ProfileChangeField[]>(needsValue ? API.hrHelp.changeFields : null);
  const suggested = needsValue ? (fields ?? []).find(candidate => candidate.key === entry.change_suggested_key) ?? null : null;

  async function decide(decision: "approve" | "reject") {
    setError(null);
    setBusy(decision);
    try {
      await clientApi.post(API.hrHelp.decideChange(entry.id), { decision, note, ...(needsValue && decision === "approve" ? { new_value: typedValue.trim() } : {}) });
      onDecided();
    } catch (caught: unknown) {
      const message = (caught as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(message ?? "Could not update this request.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: 12, marginBottom: 12, background: "var(--surface)" }}>
      <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--outline)", marginBottom: 6 }}>
        Requested change · {entry.change_label || suggested?.label || "profile field"}
      </div>
      {needsValue ? (
        <div className="field-group" style={{ marginBottom: 10, maxWidth: 420 }}>
          <label className="field-label">New {(suggested?.label ?? "value").toLowerCase()} (as the employee asked in the request)</label>
          {suggested ? <ProfileChangeValueInput spec={suggested} value={typedValue} onChange={setTypedValue} /> : <p style={{ fontSize: 12, margin: 0 }}>Loading…</p>}
        </div>
      ) : (
        <div style={{ fontSize: 13, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
          <span style={{ color: "var(--on-variant)" }}>{entry.change_old_value || "(empty)"}</span>
          <i className="ti ti-arrow-right" />
          <strong>{entry.change_new_value}</strong>
        </div>
      )}
      {entry.change_decision ? (
        <p style={{ fontSize: 12, margin: 0, color: "var(--on-variant)" }}>{DECISION_TEXT[entry.change_decision]}</p>
      ) : (
        <>
          {error && <div className="alert alert-error" style={{ marginBottom: 10 }}>{error}</div>}
          {entry.change_needs_system_admin && (
            <p style={{ fontSize: 11, color: "var(--on-variant)", margin: "0 0 8px" }}>Only a System Admin can change the date of joining.</p>
          )}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <a className="btn btn-ghost btn-sm" href={`/dashboard/employees?open=${encodeURIComponent(entry.submitted_by_code)}`}>
              <i className="ti ti-user-search" /> Open employee record
            </a>
            <button type="button" className="btn btn-filled btn-sm" onClick={() => decide("approve")} disabled={busy !== null || (needsValue && !typedValue.trim())} suppressHydrationWarning>
              {busy === "approve" ? "Applying…" : "Apply requested change"}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => decide("reject")} disabled={busy !== null} suppressHydrationWarning>
              {busy === "reject" ? "Declining…" : "Decline"}
            </button>
          </div>
          <p style={{ fontSize: 11, color: "var(--on-variant)", margin: "8px 0 0" }}>
            Applying updates the record and resolves this request. Declining needs a reason in the Response box.
          </p>
        </>
      )}
    </div>
  );
}

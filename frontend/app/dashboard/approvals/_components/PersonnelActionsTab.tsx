"use client";

// Approval inbox for Promotion / Org assignment / Pay change / Confirmation
// requests raised by Reporting Managers (see apps.accounts
// services_personnel_actions). "Awaiting my decision" lists requests whose
// CURRENT step I am allowed to decide; "Raised by me" lists what I sent and
// lets me cancel anything still pending. Maker-checker is enforced by the
// server — the buttons here only reflect what the API says I may do.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PersonnelActionRequest } from "@/types/personnelAction";
import PersonnelActionRow from "./PersonnelActionRow";

interface InboxResponse { count: number; results: PersonnelActionRequest[] }

type View = "inbox" | "mine";

export default function PersonnelActionsTab() {
  const [view, setView] = useState<View>("inbox");
  const inbox = useFetch<InboxResponse>(API.actionRequests.list);
  const mine = useFetch<InboxResponse>(`${API.actionRequests.list}?scope=mine`);

  const rows = view === "inbox" ? inbox.data?.results ?? [] : mine.data?.results ?? [];
  const loading = view === "inbox" ? inbox.loading : mine.loading;
  const error = view === "inbox" ? inbox.error : mine.error;

  function refresh() {
    inbox.refetch();
    mine.refetch();
  }

  return (
    <div className="settings-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 10, marginBottom: 12 }}>
        <div>
          <h2 style={{ fontSize: 17, fontWeight: 800 }}>Personnel actions &amp; approval inbox</h2>
          <p className="hint">Every action keeps its effective date, owner, state and decision history. Nothing changes until the last approver approves.</p>
        </div>
        <div className="seg" role="tablist" aria-label="Personnel action views">
          <button type="button" role="tab" aria-selected={view === "inbox"} className={view === "inbox" ? "on" : ""} onClick={() => setView("inbox")}>
            Awaiting my decision{inbox.data ? ` (${inbox.data.count})` : ""}
          </button>
          <button type="button" role="tab" aria-selected={view === "mine"} className={view === "mine" ? "on" : ""} onClick={() => setView("mine")}>
            Raised by me
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error mb-16">{error}</div>}

      {loading ? (
        <p className="hint">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="hint" style={{ padding: "18px 0" }}>
          {view === "inbox" ? "Nothing is waiting for your decision." : "You have not raised any personnel actions."}
        </p>
      ) : (
        <div className="case-table">
          <div className="case-row head">
            <span>CASE / EMPLOYEE</span><span>ACTION</span><span>EFFECTIVE</span><span>OWNER / STATE</span><span>DECISION</span>
          </div>
          {rows.map(r => <PersonnelActionRow key={r.id} request={r} onChanged={refresh} />)}
        </div>
      )}
    </div>
  );
}

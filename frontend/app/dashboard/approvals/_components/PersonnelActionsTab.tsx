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
import { TabEmpty, TabHeader } from "./ApprovalTabChrome";
import { ApprovalTabStyles } from "./approvalTabStyles";

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
    <div className="card" style={{ overflow: "hidden" }}>
      <ApprovalTabStyles />
      <TabHeader
        icon="ti-arrows-exchange" accent="#ea580c" title="Personnel actions & approval inbox"
        subtitle="Promotions, transfers, pay changes and confirmations. Nothing changes until the last approver approves."
        stats={[
          { label: "Awaiting my decision", value: inbox.data?.count ?? 0, icon: "ti-hourglass", accent: "#d97706", isUrgent: (inbox.data?.count ?? 0) > 0 },
          { label: "Raised by me", value: mine.data?.count ?? 0, icon: "ti-send", accent: "#2563eb" },
        ]}
        actions={(
          <div className="seg" role="tablist" aria-label="Personnel action views">
            <button type="button" role="tab" aria-selected={view === "inbox"} className={view === "inbox" ? "on" : ""} onClick={() => setView("inbox")}>
              Awaiting my decision{inbox.data ? ` (${inbox.data.count})` : ""}
            </button>
            <button type="button" role="tab" aria-selected={view === "mine"} className={view === "mine" ? "on" : ""} onClick={() => setView("mine")}>
              Raised by me
            </button>
          </div>
        )}
      />

      {error && <div className="alert alert-error" style={{ margin: 16 }}>{error}</div>}

      {loading ? (
        <p className="hint" style={{ padding: 20 }}>Loading…</p>
      ) : rows.length === 0 ? (
        <TabEmpty
          icon={view === "inbox" ? "ti-checks" : "ti-send"}
          title={view === "inbox" ? "Nothing is waiting for your decision." : "You have not raised any personnel actions."}
          hint={view === "inbox" ? "When a manager raises a promotion, transfer or pay change that needs you, it shows up here." : "Actions you raise for your team are listed here, and you can cancel any that are still pending."}
        />
      ) : (
        <div className="tb-cases">
          <div className="case-row head" style={{ padding: "0 14px", minWidth: 720 }}>
            <span>CASE / EMPLOYEE</span><span>ACTION</span><span>EFFECTIVE</span><span>OWNER / STATE</span><span>DECISION</span>
          </div>
          {rows.map(r => <div key={r.id} className="tb-case"><PersonnelActionRow request={r} onChanged={refresh} /></div>)}
        </div>
      )}
    </div>
  );
}

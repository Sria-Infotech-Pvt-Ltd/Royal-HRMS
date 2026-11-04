"use client";

// Payments for one subscription: amount due vs confirmed payments, the full
// payment history (who recorded / confirmed each), receipts, and the
// actions — record, confirm, reject (with reason), waive, edit amount due.
// Payments are never edited or deleted; a wrong entry is rejected.

import { useState } from "react";
import DocPreviewModal from "@/components/DocPreviewModal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { API_BASE } from "@/lib/config";
import type { CompanySubscription, SubscriptionPaymentRecord } from "@/types/platformAdmin";
import { apiMessage, fmtDate, fmtMoney } from "./SaasTabs";
import * as v from "@/lib/saasValidation";
import PaymentFields, { EMPTY_PAYMENT, MULTIPART, paymentErrors, paymentFormData } from "./PaymentFields";

const RECORD_BADGE: Record<SubscriptionPaymentRecord["status"], { label: string; cls: string }> = {
  recorded: { label: "Awaiting confirmation", cls: "badge-warn" },
  verified: { label: "Confirmed", cls: "badge-success" },
  rejected: { label: "Rejected", cls: "badge-error" },
};

type Panel = null | "record" | "due" | "waive";

export default function PaymentsSection({ clientId, sub, payments, onChanged }: {
  clientId: string;
  sub: CompanySubscription;
  payments: SubscriptionPaymentRecord[];
  onChanged: () => void;
}) {
  const [panel, setPanel] = useState<Panel>(null);
  const [payment, setPayment] = useState(EMPTY_PAYMENT);
  const [due, setDue] = useState(sub.amount_due ?? "");
  const [reason, setReason] = useState("");
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [payErrors, setPayErrors] = useState<v.Errors>({});
  const [receipt, setReceipt] = useState<SubscriptionPaymentRecord | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const waived = sub.payment_status === "waived";
  const received = Number(sub.amount_received);
  const balance = sub.amount_due !== null ? Math.max(Number(sub.amount_due) - received, 0) : null;

  async function run(fn: () => Promise<{ data: { message?: string } }>, fallback: string) {
    setBusy(true);
    setMsg(null);
    try {
      const { data } = await fn();
      setMsg({ ok: true, text: data.message ?? "Saved." });
      setPanel(null);
      setPayment(EMPTY_PAYMENT);
      setReason("");
      setRejecting(null);
      setRejectReason("");
      setPayErrors({});
      onChanged();
    } catch (e) {
      setPayErrors(v.apiFieldErrors(e));
      setMsg({ ok: false, text: apiMessage(e, fallback) });
    } finally {
      setBusy(false);
    }
  }

  const toggle = (p: Panel) => { setMsg(null); setPayErrors({}); setPanel(panel === p ? null : p); };
  const dueError = v.decimal(due, { min: 0, minExclusive: true, what: "Amount due" });

  function recordPayment() {
    const found = paymentErrors(payment);
    setPayErrors(found);
    if (Object.keys(found).length) { setMsg({ ok: false, text: "Please correct the highlighted fields." }); return; }
    run(() => platformAdminApi.post(API.platformAdmin.saas.payments(clientId), paymentFormData(payment), MULTIPART), "Could not record the payment.");
  }

  // Confirming needs the amount due (it decides Paid vs Partially paid).
  function askForDue(suggested: string) {
    setDue(suggested);
    setPanel("due");
    setMsg({ ok: false, text: "Set the amount due for this subscription first, then click Confirm again." });
  }

  return (
    <div className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600 }}>Payments</span>
        <span style={{ flex: 1 }} />
        <button className="btn btn-sm btn-filled" disabled={busy} onClick={() => toggle("record")}>
          <i className="ti ti-plus" /> Record payment
        </button>
        <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => { setDue(sub.amount_due ?? ""); toggle("due"); }}>
          {sub.amount_due === null ? "Set amount due" : "Edit amount due"}
        </button>
        {waived ? (
          <button className="btn btn-sm btn-ghost" disabled={busy}
            onClick={() => run(() => platformAdminApi.post(API.platformAdmin.saas.waiver(clientId), { waive: false }), "Could not remove the waiver.")}>
            Remove waiver
          </button>
        ) : (
          <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => toggle("waive")}>Waive payment</button>
        )}
      </div>

      {msg && <div className={`alert ${msg.ok ? "alert-success" : "alert-error"}`}>{msg.text}</div>}

      <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
        {([
          ["Amount due", sub.amount_due !== null ? fmtMoney(sub.amount_due, sub.currency) : "Not set"],
          ["Received (confirmed)", fmtMoney(received, sub.currency)],
          ["Balance", balance !== null ? fmtMoney(balance, sub.currency) : "—"],
        ] as [string, string][]).map(([k, v]) => (
          <div key={k} style={{ background: "var(--bg-low)", borderRadius: 8, padding: "8px 10px" }}>
            <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{k}</div>
            <div style={{ fontWeight: 600 }}>{v}</div>
          </div>
        ))}
      </div>
      {waived && <div style={{ color: "var(--on-variant)" }}>Payment waived: {sub.payment_waiver_reason}</div>}

      {panel === "record" && (
        <div style={{ borderTop: "1px solid var(--outline-v)", paddingTop: 12, display: "flex", flexDirection: "column", gap: 12 }}>
          <PaymentFields value={payment} errors={payErrors} onChange={p => { setPayment(p); setPayErrors({}); }} />
          {payment.confirm && sub.amount_due === null && (
            <div style={{ color: "var(--error)", fontSize: 12 }}>Set the amount due before confirming payments.</div>
          )}
          <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
            <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => setPanel(null)}>Cancel</button>
            <button className="btn btn-sm btn-filled" disabled={busy || (payment.confirm && sub.amount_due === null)} onClick={recordPayment}>
              {busy ? "Saving…" : payment.confirm ? "Record & confirm" : "Record payment"}
            </button>
          </div>
        </div>
      )}

      {panel === "due" && (
        <div style={{ borderTop: "1px solid var(--outline-v)", paddingTop: 12, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span>Amount due ({sub.currency})</span>
          <input className="field-input" type="number" min={0} step="0.01" inputMode="decimal" value={due} onChange={e => setDue(e.target.value)} style={{ maxWidth: 180 }} />
          <button className="btn btn-sm btn-filled" disabled={busy || !!dueError}
            onClick={() => run(() => platformAdminApi.post(API.platformAdmin.saas.amountDue(clientId), { amount_due: due }), "Could not update the amount due.")}>
            Save
          </button>
          <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => setPanel(null)}>Cancel</button>
          {dueError && (
            <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
              {dueError}{Number(due) === 0 && due.trim() ? " Use “Waive payment” for no charge." : ""}
            </span>
          )}
        </div>
      )}

      {panel === "waive" && (
        <div style={{ borderTop: "1px solid var(--outline-v)", paddingTop: 12, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input className="field-input" placeholder="Reason for waiving (required)" value={reason} maxLength={1000} onChange={e => setReason(e.target.value)}
            style={{ flex: 1, minWidth: 220 }} />
          <button className="btn btn-sm btn-filled" disabled={busy || !reason.trim()}
            onClick={() => run(() => platformAdminApi.post(API.platformAdmin.saas.waiver(clientId), { waive: true, reason: reason.trim() }), "Could not waive the payment.")}>
            Waive payment
          </button>
          <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => setPanel(null)}>Cancel</button>
        </div>
      )}

      {payments.length === 0 ? (
        <div style={{ color: "var(--on-variant)" }}>No payments recorded yet.</div>
      ) : (
        <div className="table-wrap">
          <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
            <thead>
              <tr><th>Date</th><th>Amount</th><th>Method</th><th>Reference</th><th>Status / action</th><th>Recorded / reviewed by</th></tr>
            </thead>
            <tbody>
              {payments.map(p => (
                <tr key={p.id}>
                  <td style={{ whiteSpace: "nowrap" }}>{fmtDate(p.paid_on)}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{fmtMoney(p.amount, p.currency)}</td>
                  <td>{p.method_label}</td>
                  <td style={{ maxWidth: 160, wordBreak: "break-all" }}>
                    {p.reference || "—"}
                    {p.notes && <div style={{ fontSize: 11, color: "var(--on-variant)", wordBreak: "break-word" }}>{p.notes}</div>}
                  </td>
                  <td>
                    <span className={`badge ${RECORD_BADGE[p.status].cls}`}>{RECORD_BADGE[p.status].label}</span>
                    {p.rejection_reason && <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{p.rejection_reason}</div>}
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center", marginTop: 6 }}>
                      {p.has_receipt && (
                        <button className="btn btn-ghost btn-sm" onClick={() => setReceipt(p)}><i className="ti ti-file-invoice" /> Receipt</button>
                      )}
                      {p.status === "recorded" && rejecting !== p.id && (
                        <>
                          <button className="btn btn-filled btn-sm" disabled={busy}
                            onClick={() => sub.amount_due === null
                              ? askForDue(p.amount)
                              : run(() => platformAdminApi.post(API.platformAdmin.saas.verifyPayment(clientId, p.id)), "Could not confirm the payment.")}>
                            Confirm
                          </button>
                          <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => { setRejecting(p.id); setRejectReason(""); }}>Reject</button>
                        </>
                      )}
                    </div>
                    {rejecting === p.id && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 6 }}>
                        <input className="field-input" placeholder="Reason (required)" value={rejectReason} maxLength={1000}
                          onChange={e => setRejectReason(e.target.value)} style={{ minWidth: 160 }} />
                        <button className="btn btn-sm btn-filled" disabled={busy || !rejectReason.trim()}
                          onClick={() => run(() => platformAdminApi.post(API.platformAdmin.saas.rejectPayment(clientId, p.id), { reason: rejectReason.trim() }), "Could not reject the payment.")}>
                          Reject
                        </button>
                        <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => setRejecting(null)}>Cancel</button>
                      </div>
                    )}
                  </td>
                  <td style={{ fontSize: 12 }}>
                    <div>Recorded: {p.recorded_by_name ?? "—"}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{new Date(p.created_at).toLocaleString("en-IN")}</div>
                    {p.reviewed_at && (
                      <>
                        <div style={{ marginTop: 4 }}>{p.status === "rejected" ? "Rejected" : "Confirmed"}: {p.reviewed_by_name ?? "—"}</div>
                        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{new Date(p.reviewed_at).toLocaleString("en-IN")}</div>
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {receipt && (
        <DocPreviewModal name={`Receipt — ${fmtMoney(receipt.amount, receipt.currency)} on ${fmtDate(receipt.paid_on)}`}
          fileName={receipt.receipt_name} fileUrl={`${API_BASE}${API.platformAdmin.saas.paymentReceipt(clientId, receipt.id)}`}
          onClose={() => setReceipt(null)} />
      )}
    </div>
  );
}

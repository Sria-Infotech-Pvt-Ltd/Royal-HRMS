"use client";

// Payments for one subscription: subscription amount, paid (confirmed),
// awaiting confirmation and outstanding — all calculated by the server —
// the full payment history (who recorded / confirmed each), receipts, and the
// actions — record, confirm, reject (with reason), waive, edit the
// subscription amount. Recording asks only for the payment amount (pre-filled
// with what is still open); a payment above the outstanding balance needs an
// explicit "Record anyway". Payments are never edited or deleted; a wrong
// entry is rejected.

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
  const [overpay, setOverpay] = useState<string | null>(null);   // server's overpayment warning

  const waived = sub.payment_status === "waived";
  const received = Number(sub.amount_received);
  const pending = Number(sub.amount_pending_confirmation ?? 0);
  const outstanding = sub.amount_outstanding;               // null = subscription amount not known
  const overpaid = Number(sub.amount_overpaid ?? 0);
  // What is still open once the payments awaiting confirmation are confirmed.
  const open = outstanding !== null ? Math.max(Number(outstanding) - pending, 0) : null;
  // No total and nothing to calculate it from: the admin must enter it once.
  const needsAmount = sub.amount_due === null && !sub.employee_count;

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
      const data = (e as { response?: { data?: { data?: { requires_confirmation?: string } } } })?.response?.data?.data;
      if (data?.requires_confirmation === "overpayment") {
        setOverpay(apiMessage(e, "This payment is more than the outstanding balance."));
        return;
      }
      setPayErrors(v.apiFieldErrors(e));
      setMsg({ ok: false, text: apiMessage(e, fallback) });
    } finally {
      setBusy(false);
    }
  }

  const toggle = (p: Panel) => { setMsg(null); setPayErrors({}); setOverpay(null); setPanel(panel === p ? null : p); };
  const dueError = v.decimal(due, { min: 0, minExclusive: true, what: "Subscription amount" });

  function openRecord() {
    // Pre-fill what is still to collect, so a full payment is one click.
    if (panel !== "record" && !payment.amount && open !== null && open > 0) {
      setPayment(p => ({ ...p, amount: open.toFixed(2) }));
    }
    toggle("record");
  }

  function recordPayment(allowOverpayment = false) {
    const found = paymentErrors(payment);
    setPayErrors(found);
    if (Object.keys(found).length) { setMsg({ ok: false, text: "Please correct the highlighted fields." }); return; }
    setOverpay(null);
    run(() => platformAdminApi.post(API.platformAdmin.saas.payments(clientId), paymentFormData(payment, allowOverpayment), MULTIPART),
      "Could not record the payment.");
  }

  // Confirming needs the subscription amount (it decides Paid vs Partially
  // paid). The server calculates it from the employee count when it can;
  // only without one is the admin asked, once.
  function askForDue(suggested: string) {
    setDue(suggested);
    setPanel("due");
    setMsg({ ok: false, text: "Set the subscription amount first (there is no employee count to calculate it from), then click Confirm again." });
  }

  const amountHint = open === null
    ? (sub.employee_count ? "The subscription amount is calculated from the employee count when you record." : null)
    : waived ? "Payment is waived — nothing is outstanding."
    : Number(payment.amount) > open && open >= 0
      ? `More than the ${fmtMoney(open, sub.currency)} still to collect — you will be asked to confirm.`
      : `Outstanding: ${fmtMoney(outstanding ?? 0, sub.currency)}${pending ? ` (${fmtMoney(pending, sub.currency)} awaiting confirmation)` : ""}.`;

  return (
    <div className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontWeight: 600 }}>Payments</span>
        <span style={{ flex: 1 }} />
        <button className="btn btn-sm btn-filled" disabled={busy} onClick={openRecord}>
          <i className="ti ti-plus" /> Record payment
        </button>
        <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => { setDue(sub.amount_due ?? ""); toggle("due"); }}>
          {sub.amount_due === null ? "Set subscription amount" : "Edit subscription amount"}
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
          ["Subscription amount", sub.amount_due !== null ? fmtMoney(sub.amount_due, sub.currency)
            : sub.employee_count ? "Calculated on first payment" : "Not set"],
          ["Paid (confirmed)", fmtMoney(received, sub.currency)],
          ...(pending > 0 ? [["Awaiting confirmation", fmtMoney(pending, sub.currency)]] : []),
          ["Outstanding", outstanding !== null ? fmtMoney(outstanding, sub.currency) : "—"],
          ...(overpaid > 0 ? [["Overpaid", fmtMoney(overpaid, sub.currency)]] : []),
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
          <PaymentFields value={payment} errors={payErrors} amountHint={amountHint}
            onChange={p => { setPayment(p); setPayErrors({}); setOverpay(null); }} />
          {payment.confirm && needsAmount && (
            <div style={{ color: "var(--error)", fontSize: 12 }}>Set the subscription amount before confirming payments.</div>
          )}
          {overpay ? (
            <div className="alert alert-warn" style={{ flexWrap: "wrap", gap: 8 }}>
              <span style={{ flex: 1, minWidth: 220 }}>{overpay}</span>
              <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => setOverpay(null)}>Change amount</button>
              <button className="btn btn-sm btn-filled" disabled={busy} onClick={() => recordPayment(true)}>
                {busy ? "Saving…" : "Record anyway"}
              </button>
            </div>
          ) : (
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button className="btn btn-sm btn-ghost" disabled={busy} onClick={() => setPanel(null)}>Cancel</button>
              <button className="btn btn-sm btn-filled" disabled={busy || (payment.confirm && needsAmount)} onClick={() => recordPayment()}>
                {busy ? "Saving…" : payment.confirm ? "Record & confirm" : "Record payment"}
              </button>
            </div>
          )}
        </div>
      )}

      {panel === "due" && (
        <div style={{ borderTop: "1px solid var(--outline-v)", paddingTop: 12, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <span>Subscription amount ({sub.currency})</span>
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
                            onClick={() => needsAmount
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

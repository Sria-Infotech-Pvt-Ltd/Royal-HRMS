"use client";

import { useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

interface YearlyRow {
  leave_type: string;
  leave_type_label: string;
  opening_or_allocated: number;
  carried_forward: number;
  manual_adjustments: number;
  total_credits: number;
  used: number;
  pending: number;
  remaining: number;
  available_after_pending: number;
}

interface CreditTxn {
  id: string;
  leave_type: string;
  year: number;
  txn_type: "adjustment" | "reversal";
  amount: number;
  total_before: number;
  total_after: number;
  reason: string;
  created_by_name: string;
  created_at: string;
  reverses: string | null;
  reversed_by: string | null;
  can_reverse: boolean;
}

interface MonthlyData {
  leave_type_label: string;
  months: { month: number; label: string; credit_adjustments: number; used: number }[];
  credit_adjustments_outside_year: number;
  used_in_next_year_months: number;
  used_not_itemised: number;
  total_credit_adjustments: number;
  total_used: number;
  approximated_requests: number;
}

interface CreditOverview {
  employee: { employee_id: string; full_name: string };
  year: number;
  current_year: number;
  summaries: YearlyRow[];
  leave_type: string | null;
  monthly: MonthlyData | null;
  transactions: CreditTxn[];
  assignable_leave_types: { value: string; label: string }[];
}

type Pending =
  | { kind: "adjust"; leaveType: string; label: string; amount: number; reason: string; key: string }
  | { kind: "reverse"; txn: CreditTxn; reason: string; key: string };

function newKey(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID().replace(/-/g, "")
    : `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
}

function signed(n: number): string {
  return n > 0 ? `+${n}` : String(n);
}

function errorMessage(err: unknown): string {
  return (err as { message?: string })?.message || "Something went wrong. Please try again.";
}

// Manual leave credit management: signed adjustments and compensating reversals,
// recorded in an append-only history. Renders nothing for users who may not manage this employee.
export default function LeaveCreditsSection({ employeeId, onChanged }: { employeeId: string; onChanged?: () => void }) {
  const [year, setYear] = useState(() => new Date().getFullYear());
  const [leaveType, setLeaveType] = useState("");
  const query = `?year=${year}${leaveType ? `&leave_type=${encodeURIComponent(leaveType)}` : ""}`;
  const { data, loading, error, status, refetch } = useFetch<CreditOverview>(`${API.leave.creditsOverview(employeeId)}${query}`);

  const [formType, setFormType] = useState("");
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const [reverseFor, setReverseFor] = useState<CreditTxn | null>(null);
  const [reverseReason, setReverseReason] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const reverseKeyRef = useRef<string>("");

  if (status === 403 || status === 404) return null;

  const selected = data?.leave_type ?? "";
  const canEditYear = !!data && data.year <= data.current_year;
  const typeOptions = data
    ? [
        ...data.summaries.map(s => ({ value: s.leave_type, label: s.leave_type_label })),
        ...data.assignable_leave_types.filter(t => !data.summaries.some(s => s.leave_type === t.value)),
      ]
    : [];
  const effectiveFormType = formType || selected || typeOptions[0]?.value || "";

  function reviewAdjustment() {
    setMessage(null);
    const value = Number(amount);
    if (!effectiveFormType) return setMessage({ ok: false, text: "Choose a leave type." });
    if (!amount.trim() || Number.isNaN(value) || value === 0) return setMessage({ ok: false, text: "Enter a non-zero number of days, e.g. 2 or -1.5." });
    if (!reason.trim()) return setMessage({ ok: false, text: "A reason is required." });
    const label = typeOptions.find(t => t.value === effectiveFormType)?.label ?? effectiveFormType;
    setPending({ kind: "adjust", leaveType: effectiveFormType, label, amount: value, reason: reason.trim(), key: newKey() });
  }

  function reviewReversal() {
    setMessage(null);
    if (!reverseFor) return;
    if (!reverseReason.trim()) return setMessage({ ok: false, text: "A reason is required to reverse an adjustment." });
    if (!reverseKeyRef.current) reverseKeyRef.current = newKey();
    setPending({ kind: "reverse", txn: reverseFor, reason: reverseReason.trim(), key: reverseKeyRef.current });
  }

  async function confirm() {
    if (!pending) return;
    setSubmitting(true);
    setMessage(null);
    try {
      if (pending.kind === "adjust") {
        await clientApi.post(API.leave.creditsAdjust(employeeId), {
          leave_type: pending.leaveType, year, amount: String(pending.amount),
          reason: pending.reason, idempotency_key: pending.key,
        });
        setAmount("");
        setReason("");
        setMessage({ ok: true, text: `${signed(pending.amount)} day(s) recorded for ${pending.label}.` });
      } else {
        await clientApi.post(API.leave.creditsReverse(employeeId, pending.txn.id), {
          reason: pending.reason, idempotency_key: pending.key,
        });
        setReverseFor(null);
        setReverseReason("");
        reverseKeyRef.current = "";
        setMessage({ ok: true, text: "Adjustment reversed." });
      }
      setPending(null);
      refetch();
      onChanged?.();
    } catch (err) {
      // Keep the same key so a retry of this exact request can never apply twice.
      setMessage({ ok: false, text: errorMessage(err) });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-adjustments-horizontal" /> Manage Leave Credits</div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <button className="btn btn-ghost btn-sm" onClick={() => { setYear(y => y - 1); setPending(null); }} disabled={loading}>
            <i className="ti ti-chevron-left" />
          </button>
          <span style={{ fontSize: 13, fontWeight: 600, minWidth: 48, textAlign: "center" }}>{year}</span>
          <button
            className="btn btn-ghost btn-sm"
            onClick={() => { setYear(y => y + 1); setPending(null); }}
            disabled={loading || (!!data && year >= data.current_year)}
          >
            <i className="ti ti-chevron-right" />
          </button>
        </div>
      </div>

      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {error && !data && <div className="alert alert-error"><i className="ti ti-alert-circle" /> {error}</div>}
        {message && (
          <div className={`alert ${message.ok ? "alert-success" : "alert-error"}`}>
            <i className={`ti ${message.ok ? "ti-circle-check" : "ti-alert-circle"}`} /> {message.text}
          </div>
        )}

        {/* Yearly summary */}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Leave Type</th>
                <th style={{ textAlign: "right" }}>Allocated / Opening*</th>
                <th style={{ textAlign: "right" }}>Carry-forward</th>
                <th style={{ textAlign: "right" }}>Adjustments</th>
                <th style={{ textAlign: "right" }}>Total Credits</th>
                <th style={{ textAlign: "right" }}>Used</th>
                <th style={{ textAlign: "right" }}>Pending</th>
                <th style={{ textAlign: "right" }}>Remaining</th>
              </tr>
            </thead>
            <tbody>
              {loading && !data ? (
                <tr><td colSpan={8} style={{ textAlign: "center", padding: 24 }}><i className="ti ti-loader-2" /></td></tr>
              ) : !data || data.summaries.length === 0 ? (
                <tr><td colSpan={8} style={{ textAlign: "center", padding: 24, color: "var(--on-variant)" }}>No leave balances for {year}.</td></tr>
              ) : (
                data.summaries.map(s => (
                  <tr
                    key={s.leave_type}
                    onClick={() => { setLeaveType(s.leave_type); setReverseFor(null); setPending(null); }}
                    style={{ cursor: "pointer", background: s.leave_type === selected ? "var(--bg-high)" : undefined }}
                  >
                    <td style={{ fontWeight: 600 }}>{s.leave_type_label}</td>
                    <td style={{ textAlign: "right" }}>{s.opening_or_allocated}</td>
                    <td style={{ textAlign: "right" }}>{s.carried_forward}</td>
                    <td style={{ textAlign: "right" }}>{signed(s.manual_adjustments)}</td>
                    <td style={{ textAlign: "right", fontWeight: 600 }}>{s.total_credits}</td>
                    <td style={{ textAlign: "right" }}>{s.used}</td>
                    <td style={{ textAlign: "right" }}>{s.pending}</td>
                    <td style={{ textAlign: "right", fontWeight: 700 }}>{s.remaining}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <p style={{ fontSize: 11, color: "var(--on-variant)", margin: "8px 4px 0" }}>
            * Credited before adjustment history began (annual allocation, opening balance import and earlier changes). Not itemised.
          </p>
        </div>

        {/* Adjust */}
        {canEditYear && (
          <div style={{ border: "1px solid var(--outline-v)", borderRadius: 8, padding: 16 }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12 }}>Assign or adjust credits for {year}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
              <div className="field-group" style={{ marginBottom: 0, minWidth: 180 }}>
                <label className="field-label">Leave type</label>
                <select className="field-input" value={effectiveFormType} onChange={e => setFormType(e.target.value)} disabled={!!pending}>
                  {typeOptions.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div className="field-group" style={{ marginBottom: 0, width: 140 }}>
                <label className="field-label">Days (+ add / − remove)</label>
                <input className="field-input" inputMode="decimal" placeholder="e.g. 2 or -1.5" value={amount} onChange={e => setAmount(e.target.value)} disabled={!!pending} />
              </div>
              <div className="field-group" style={{ marginBottom: 0, flex: 1, minWidth: 220 }}>
                <label className="field-label">Reason (required)</label>
                <input className="field-input" maxLength={1000} value={reason} onChange={e => setReason(e.target.value)} disabled={!!pending} />
              </div>
              <button className="btn btn-filled" onClick={reviewAdjustment} disabled={!!pending || submitting}>Review</button>
            </div>
          </div>
        )}

        {pending && (
          <div style={{ border: "1.5px solid var(--warn)", borderRadius: 8, padding: 16, background: "rgba(181,101,29,0.06)" }}>
            <div style={{ fontSize: 13, marginBottom: 12 }}>
              {pending.kind === "adjust" ? (
                <>Record <strong>{signed(pending.amount)} day(s)</strong> of <strong>{pending.label}</strong> for <strong>{data?.employee.full_name}</strong> in {year}?<br />Reason: {pending.reason}</>
              ) : (
                <>Reverse the <strong>{signed(pending.txn.amount)} day(s)</strong> adjustment from {new Date(pending.txn.created_at).toLocaleString()}? This records a {signed(-pending.txn.amount)} day(s) entry; the original stays in history.<br />Reason: {pending.reason}</>
              )}
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-filled" onClick={confirm} disabled={submitting}>
                {submitting ? "Saving…" : "Confirm"}
              </button>
              <button className="btn btn-ghost" onClick={() => setPending(null)} disabled={submitting}>Cancel</button>
            </div>
          </div>
        )}

        {/* History */}
        {data?.leave_type && (
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>
              Adjustment history — {data.monthly?.leave_type_label ?? data.leave_type}, {year}
            </div>
            {data.transactions.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--on-variant)" }}>No manual adjustments recorded.</div>
            ) : (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th style={{ textAlign: "right" }}>Change</th>
                      <th style={{ textAlign: "right" }}>Total After</th>
                      <th>Reason</th>
                      <th>By</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.transactions.map(t => (
                      <tr key={t.id}>
                        <td style={{ fontSize: 12 }}>{new Date(t.created_at).toLocaleString()}</td>
                        <td style={{ textAlign: "right", fontWeight: 700, color: t.amount > 0 ? "var(--success)" : "var(--error)" }}>{signed(t.amount)}</td>
                        <td style={{ textAlign: "right" }}>{t.total_after}</td>
                        <td style={{ fontSize: 12, maxWidth: 280, whiteSpace: "pre-wrap" }}>{t.reason}</td>
                        <td style={{ fontSize: 12 }}>{t.created_by_name || "—"}</td>
                        <td style={{ fontSize: 12 }}>
                          {t.txn_type === "reversal" && <span className="badge badge-neutral">Reversal of {t.reverses?.slice(0, 8)}</span>}
                          {t.reversed_by && <span className="badge badge-neutral">Reversed</span>}
                          {t.can_reverse && canEditYear && (
                            <button
                              className="btn btn-ghost btn-sm"
                              onClick={() => { setReverseFor(t); setReverseReason(""); reverseKeyRef.current = ""; setPending(null); setMessage(null); }}
                              disabled={!!pending}
                            >
                              Reverse
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {reverseFor && !pending && (
              <div style={{ display: "flex", gap: 12, alignItems: "flex-end", marginTop: 12, flexWrap: "wrap" }}>
                <div className="field-group" style={{ marginBottom: 0, flex: 1, minWidth: 220 }}>
                  <label className="field-label">Reason for reversing {signed(reverseFor.amount)} day(s)</label>
                  <input className="field-input" maxLength={1000} value={reverseReason} onChange={e => setReverseReason(e.target.value)} />
                </div>
                <button className="btn btn-filled" onClick={reviewReversal}>Review</button>
                <button className="btn btn-ghost" onClick={() => setReverseFor(null)}>Cancel</button>
              </div>
            )}
          </div>
        )}

        {/* Monthly */}
        {data?.monthly && (
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 8 }}>Monthly view — {data.monthly.leave_type_label}, {year}</div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Month</th>
                    <th style={{ textAlign: "right" }}>Credit adjustments</th>
                    <th style={{ textAlign: "right" }}>Leave used (working days)</th>
                  </tr>
                </thead>
                <tbody>
                  {data.monthly.months.map(m => (
                    <tr key={m.month}>
                      <td>{m.label}</td>
                      <td style={{ textAlign: "right" }}>{m.credit_adjustments ? signed(m.credit_adjustments) : "—"}</td>
                      <td style={{ textAlign: "right" }}>{m.used || "—"}</td>
                    </tr>
                  ))}
                  {data.monthly.credit_adjustments_outside_year !== 0 && (
                    <tr><td>Adjustments recorded in another year</td><td style={{ textAlign: "right" }}>{signed(data.monthly.credit_adjustments_outside_year)}</td><td /></tr>
                  )}
                  {data.monthly.used_in_next_year_months !== 0 && (
                    <tr><td>Leave days falling in {year + 1} (counted against {year})</td><td /><td style={{ textAlign: "right" }}>{data.monthly.used_in_next_year_months}</td></tr>
                  )}
                  {data.monthly.used_not_itemised !== 0 && (
                    <tr><td>Used before history / not linked to a leave request</td><td /><td style={{ textAlign: "right" }}>{data.monthly.used_not_itemised}</td></tr>
                  )}
                  <tr style={{ fontWeight: 700 }}>
                    <td>Total</td>
                    <td style={{ textAlign: "right" }}>{signed(data.monthly.total_credit_adjustments)}</td>
                    <td style={{ textAlign: "right" }}>{data.monthly.total_used}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            {data.monthly.approximated_requests > 0 && (
              <p style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 6 }}>
                {data.monthly.approximated_requests} leave request(s) no longer fall on any working day under current calendars and are shown in their start month.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

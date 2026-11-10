"use client";

// Edit a subscription after assignment: plan, employees, billing period,
// start / end date, notes and the subscription amount. Edit → Review changes
// (server preview: old → new values, amount with its calculation, payments
// and outstanding, payment status, module difference, warnings) → Save.
// Amount: Automatic = plan price × employees × billing period + GST, from the
// server; Manual = an adjustment with a required reason (kept in history).
// Payments are never changed here.

import { useState } from "react";
import Modal from "@/components/Modal";
import FieldError from "@/components/FieldError";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import { chargeFor } from "@/lib/saasPricing";
import { periodEnd } from "@/lib/saasDates";
import * as v from "@/lib/saasValidation";
import type { CompanySubscription, SubscriptionEditPreview, SubscriptionPlan } from "@/types/platformAdmin";
import { PAYMENT_BADGE, apiMessage, fmtDate, fmtMoney } from "./SaasTabs";

type EndMode = "auto" | "manual" | "none";

const PERIOD_LABEL: Record<string, string> = { monthly: "Monthly", yearly: "Yearly", "": "Not set" };

function shown(field: string, value: string | number | null, currency: string): string {
  if (value === null || value === "") {
    return field === "ends_on" ? "No end date" : ["amount_due", "employee_count", "billing_period"].includes(field) ? "Not set" : "—";
  }
  if (field === "amount_due") return fmtMoney(value, currency);
  if (field === "billing_period") return PERIOD_LABEL[String(value)] ?? String(value);
  if (field === "starts_on" || field === "ends_on") return fmtDate(String(value));
  return String(value);
}

export default function EditSubscriptionModal({ clientId, sub, plans, focusAmount = false, onClose, onSaved }: {
  clientId: string;
  sub: CompanySubscription;
  plans: SubscriptionPlan[];
  focusAmount?: boolean;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const snapshotTotal = sub.employee_count
    ? chargeFor(sub.price_per_employee, sub.gst_rate, sub.gst_inclusive, sub.employee_count, sub.billing_period).total : null;
  const initialManual = sub.amount_due !== null && snapshotTotal !== null && Number(sub.amount_due) !== snapshotTotal
    || (sub.amount_due !== null && snapshotTotal === null);
  const initialEnd: EndMode = !sub.ends_on ? "none" : sub.ends_on === periodEnd(sub.starts_on, sub.billing_period) ? "auto" : "manual";

  const [planId, setPlanId] = useState(sub.plan);
  const [employees, setEmployees] = useState(sub.employee_count ? String(sub.employee_count) : "");
  const [billing, setBilling] = useState(sub.billing_period || "");
  const [startsOn, setStartsOn] = useState(sub.starts_on);
  const [endMode, setEndMode] = useState<EndMode>(initialEnd);
  const [manualEnd, setManualEnd] = useState(sub.ends_on ?? "");
  const [notes, setNotes] = useState(sub.notes ?? "");
  const [amountMode, setAmountMode] = useState<"auto" | "manual">(initialManual ? "manual" : "auto");
  const [amount, setAmount] = useState(sub.amount_due ?? "");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [errors, setErrors] = useState<v.Errors>({});
  const [preview, setPreview] = useState<SubscriptionEditPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const choices = plans.filter(p => (p.status === "active" && !p.is_legacy) || p.id === sub.plan);
  const plan = choices.find(p => p.id === planId) ?? null;
  const planChanged = planId !== sub.plan;
  // Prices: the subscription's own snapshot while the plan is unchanged, else the new plan's current price.
  const price = planChanged && plan ? plan : { price_per_employee: sub.price_per_employee, gst_rate: sub.gst_rate, gst_inclusive: sub.gst_inclusive, currency: sub.currency };
  const count = Number(employees) || 0;
  const calc = count > 0 && /^\d+$/.test(employees.trim())
    ? chargeFor(price.price_per_employee, price.gst_rate, price.gst_inclusive, count, billing) : null;
  const autoEnd = periodEnd(startsOn, billing);
  const endsOn = endMode === "none" ? "" : endMode === "manual" ? manualEnd : autoEnd;
  const pricingChanged = planChanged || count !== (sub.employee_count ?? 0) || billing !== (sub.billing_period || "");
  const amountChangedByHand = amountMode === "manual" && (Number(amount) !== Number(sub.amount_due ?? NaN) || !initialManual);
  const sendAmountMode = amountMode === "auto"
    ? (pricingChanged || initialManual || sub.amount_due === null)
    : (pricingChanged || amountChangedByHand);

  function body(dryRun: boolean) {
    const b: Record<string, unknown> = {};
    if (planChanged) b.plan = planId;
    if (count !== (sub.employee_count ?? 0) && employees.trim()) b.employee_count = count;
    if (billing !== (sub.billing_period || "")) b.billing_period = billing;
    if (startsOn !== sub.starts_on) b.starts_on = startsOn;
    if ((endsOn || null) !== (sub.ends_on || null)) b.ends_on = endsOn || null;
    if (notes !== (sub.notes ?? "")) b.notes = notes;
    if (sendAmountMode) {
      b.amount_mode = amountMode;
      if (amountMode === "manual") { b.amount_due = amount; b.amount_reason = reason.trim(); }
    }
    if (note.trim()) b.note = note.trim();
    if (dryRun) b.dry_run = true;
    return b;
  }

  function validate(): v.Errors {
    return v.collect({
      plan: planChanged && !plan ? "Choose a plan." : null,
      employee_count: (amountMode === "auto" && !employees.trim() ? "Enter the employee count to calculate the amount." : null)
        ?? v.wholeNumber(employees, { what: "Employees" })
        ?? (plan && count && plan.min_employees && count < plan.min_employees ? `${plan.name} needs at least ${plan.min_employees} employees.` : null)
        ?? (plan && count && plan.max_employees && count > plan.max_employees ? `${plan.name} allows at most ${plan.max_employees} employees.` : null),
      billing_period: billing && plan && plan.billing_periods.length && !plan.billing_periods.includes(billing as "monthly" | "yearly")
        ? `${plan.name} is billed ${plan.billing_periods.join(" or ")} only.` : null,
      starts_on: v.date(startsOn, { what: "Start date" }),
      ends_on: v.date(endsOn, { isRequired: false, what: "End date" })
        ?? (endsOn && startsOn && endsOn < startsOn ? "End date cannot be before the start date." : null),
      notes: v.maxLength(notes, 1000),
      amount_due: amountMode === "manual" ? v.decimal(String(amount), { min: 0, minExclusive: true, what: "Subscription amount" }) : null,
      amount_reason: amountMode === "manual" && sendAmountMode ? v.required(reason, "A reason") ?? v.maxLength(reason, 1000) : null,
      note: v.maxLength(note, 500),
    });
  }

  async function send(dryRun: boolean) {
    if (dryRun) {
      const found = validate();
      setErrors(found);
      if (Object.keys(found).length) { setErr("Please correct the highlighted fields."); return; }
    }
    setBusy(true);
    setErr(null);
    try {
      const { data } = await platformAdminApi.post(API.platformAdmin.saas.edit(clientId), body(dryRun));
      if (dryRun) { setPreview(data.data as SubscriptionEditPreview); return; }
      onSaved(data.message ?? "Subscription updated.");
      onClose();
    } catch (e) {
      const fieldErrs = v.apiFieldErrors(e);
      setErrors(fieldErrs);
      setPreview(null);
      setErr(apiMessage(e, dryRun ? "Could not prepare the preview." : "Could not save the changes."));
    } finally {
      setBusy(false);
    }
  }

  const change = (fn: () => void, ...fields: string[]) => {
    fn();
    setPreview(null);
    setErr(null);
    if (fields.length) setErrors(e => Object.fromEntries(Object.entries(e).filter(([k]) => !fields.includes(k))));
  };
  const cur = planChanged && plan ? plan.currency : sub.currency;
  const hint = { fontSize: 11, color: "var(--on-variant)" } as const;

  return (
    <Modal title={`Edit subscription — ${sub.plan_name}`} onClose={onClose} closeDisabled={busy} size="lg"
      footer={preview ? (
        <>
          <button className="btn btn-ghost" onClick={() => setPreview(null)} disabled={busy}>Back</button>
          <button className="btn btn-filled" onClick={() => send(false)} disabled={busy}>{busy ? "Saving…" : "Save changes"}</button>
        </>
      ) : (
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn-filled" onClick={() => send(true)} disabled={busy}>{busy ? "Checking…" : "Review changes"}</button>
        </>
      )}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14, fontSize: 13 }}>
        {err && <div className="alert alert-error">{err}</div>}

        {!preview && (
          <>
            <div className="form-row cols-2">
              <div className="field-group">
                <label className="field-label">Plan *</label>
                <select className="field-input" value={planId} onChange={e => change(() => setPlanId(e.target.value), "plan", "employee_count", "billing_period")}>
                  {!choices.some(p => p.id === sub.plan) && <option value={sub.plan}>{sub.plan_name} (current)</option>}
                  {choices.map(p => (
                    <option key={p.id} value={p.id}>
                      {p.id === sub.plan ? `${sub.plan_name} (current) — ${fmtMoney(sub.price_per_employee, sub.currency)}` : `${p.name} — ${fmtMoney(p.price_per_employee, p.currency)}`}/employee/month
                    </option>
                  ))}
                </select>
                {planChanged && <span style={hint}>The new plan&apos;s current price and modules are used.</span>}
                <FieldError msg={errors.plan} />
              </div>
              <div className="field-group">
                <label className="field-label">Employees {amountMode === "auto" ? "*" : ""}</label>
                <input className="field-input" type="number" min={plan?.min_employees ?? 1} max={plan?.max_employees ?? v.MAX_EMPLOYEES} step={1}
                  inputMode="numeric" value={employees} autoFocus={!focusAmount && !sub.employee_count}
                  onChange={e => change(() => setEmployees(e.target.value), "employee_count")} />
                {plan && (plan.min_employees || plan.max_employees) && (
                  <span style={hint}>{plan.name}: {plan.min_employees ?? 1}–{plan.max_employees ?? "no limit"} employees</span>
                )}
                <FieldError msg={errors.employee_count} />
              </div>
              <div className="field-group">
                <label className="field-label">Billing period</label>
                <select className="field-input" value={billing} onChange={e => change(() => setBilling(e.target.value), "billing_period", "ends_on")}>
                  <option value="monthly">Monthly</option><option value="yearly">Yearly</option><option value="">Not set</option>
                </select>
                <FieldError msg={errors.billing_period} />
              </div>
              <div className="field-group">
                <label className="field-label">Start date *</label>
                <input className="field-input" type="date" min="2000-01-01" value={startsOn}
                  onChange={e => change(() => setStartsOn(e.target.value), "starts_on", "ends_on")} />
                <FieldError msg={errors.starts_on} />
              </div>
              <div className="field-group">
                <label className="field-label">End date</label>
                <input className="field-input" type="date" min={startsOn || "2000-01-01"} value={endsOn} disabled={endMode === "none"}
                  onChange={e => change(() => { setManualEnd(e.target.value); setEndMode(e.target.value ? "manual" : "auto"); }, "ends_on")} />
                <span style={hint}>
                  {endMode === "none" ? "No end date (open-ended)."
                    : endMode === "manual" ? <>Entered manually. <button type="button" className="btn btn-ghost btn-sm" style={{ padding: "0 4px" }}
                        onClick={() => change(() => setEndMode("auto"), "ends_on")}>Use one {billing === "yearly" ? "year" : "month"} from start</button></>
                    : autoEnd ? `One ${billing === "yearly" ? "year" : "month"} from the start date.` : "Choose a billing period to calculate it, or enter a date."}
                </span>
                <label style={{ display: "flex", gap: 6, fontSize: 12 }}>
                  <input type="checkbox" checked={endMode === "none"} onChange={e => change(() => setEndMode(e.target.checked ? "none" : "auto"), "ends_on")} /> No end date
                </label>
                <FieldError msg={errors.ends_on} />
              </div>
              <div className="field-group">
                <label className="field-label">Notes</label>
                <input className="field-input" value={notes} maxLength={1000} onChange={e => change(() => setNotes(e.target.value), "notes")} />
                <FieldError msg={errors.notes} />
              </div>
            </div>

            <div className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ fontWeight: 600 }}>Subscription amount</div>
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                <label style={{ display: "flex", gap: 6 }}>
                  <input type="radio" checked={amountMode === "auto"} onChange={() => change(() => setAmountMode("auto"), "amount_due", "amount_reason", "employee_count")} />
                  Automatic (from the plan)
                </label>
                <label style={{ display: "flex", gap: 6 }}>
                  <input type="radio" checked={amountMode === "manual"} onChange={() => change(() => setAmountMode("manual"), "amount_due", "amount_reason", "employee_count")} />
                  Manual adjustment
                </label>
              </div>
              {amountMode === "auto" ? (
                calc ? (
                  <div style={{ background: "var(--bg-low)", borderRadius: 8, padding: "8px 10px" }}>
                    <div><strong>{fmtMoney(calc.total, cur)}</strong> for one {billing === "yearly" ? "year" : "month"}</div>
                    <div style={hint}>
                      {count} employees × {fmtMoney(price.price_per_employee, cur)} × {calc.months} month(s) = {fmtMoney(calc.subtotal, cur)}
                      {price.gst_inclusive ? ` (GST ${Number(price.gst_rate)}% included: ${fmtMoney(calc.gst, cur)})` : ` + GST ${Number(price.gst_rate)}% ${fmtMoney(calc.gst, cur)}`}
                    </div>
                  </div>
                ) : (
                  <div style={{ color: "var(--on-variant)" }}>Enter the employee count to calculate the amount.</div>
                )
              ) : (
                <div className="form-row cols-2" style={{ marginBottom: 0 }}>
                  <div className="field-group">
                    <label className="field-label">Amount ({cur}) *</label>
                    <input className="field-input" type="number" min={0} step="0.01" inputMode="decimal" value={amount} autoFocus={focusAmount}
                      onChange={e => change(() => setAmount(e.target.value), "amount_due")} />
                    {calc && <span style={hint}>Calculated from the plan: {fmtMoney(calc.total, cur)}</span>}
                    <FieldError msg={errors.amount_due} />
                  </div>
                  <div className="field-group">
                    <label className="field-label">Reason {sendAmountMode ? "*" : ""}</label>
                    <input className="field-input" value={reason} maxLength={1000} placeholder="e.g. negotiated discount"
                      onChange={e => change(() => setReason(e.target.value), "amount_reason")} />
                    <span style={hint}>Kept in the subscription history.</span>
                    <FieldError msg={errors.amount_reason} />
                  </div>
                </div>
              )}
              <div style={hint}>Recorded payments are never changed. Paid / Partially paid follow the confirmed payments against the new amount.</div>
            </div>

            <div className="field-group">
              <label className="field-label">Note for the history (optional)</label>
              <input className="field-input" value={note} maxLength={500} onChange={e => change(() => setNote(e.target.value), "note")} />
              <FieldError msg={errors.note} />
            </div>
          </>
        )}

        {preview && (
          <>
            <div className="alert alert-info">Review the changes below. Nothing has been saved yet.</div>
            <table className="data-table" style={{ width: "100%", fontSize: 12.5 }}>
              <thead><tr><th>Field</th><th>Current</th><th>New</th></tr></thead>
              <tbody>
                {preview.changes.map(c => (
                  <tr key={c.field}>
                    <td>{c.label}</td>
                    <td>{shown(c.field, c.from, sub.currency)}</td>
                    <td><strong>{shown(c.field, c.to, cur)}</strong></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {preview.amount.calculated && preview.amount.mode === "auto" && (
              <div style={hint}>
                Amount: {preview.amount.calculated.employee_count} employees × {fmtMoney(preview.amount.calculated.price_per_employee, cur)} × {preview.amount.calculated.months} month(s)
                {" = "}{fmtMoney(preview.amount.calculated.subtotal, cur)}
                {preview.amount.calculated.gst_inclusive
                  ? ` (GST ${Number(preview.amount.calculated.gst_rate)}% included: ${fmtMoney(preview.amount.calculated.gst_amount, cur)})`
                  : ` + GST ${Number(preview.amount.calculated.gst_rate)}% ${fmtMoney(preview.amount.calculated.gst_amount, cur)}`}
                {" = "}<strong>{fmtMoney(preview.amount.calculated.total, cur)}</strong>
              </div>
            )}
            {preview.amount.mode === "manual" && <div style={hint}>Manual amount — reason: {preview.amount.reason}</div>}
            <div style={{ display: "grid", gap: 8, gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
              {([
                ["Paid (confirmed)", fmtMoney(preview.payments.received, cur)],
                ...(Number(preview.payments.pending) > 0 ? [["Awaiting confirmation", fmtMoney(preview.payments.pending, cur)]] : []),
                ["Outstanding", `${preview.payments.outstanding_before !== null ? fmtMoney(preview.payments.outstanding_before, cur) : "—"} → ${preview.payments.outstanding_after !== null ? fmtMoney(preview.payments.outstanding_after, cur) : "—"}`],
                ["Payment status", `${PAYMENT_BADGE[preview.payment_status.from].label} → ${PAYMENT_BADGE[preview.payment_status.to].label}`],
              ] as [string, string][]).map(([k, val]) => (
                <div key={k} style={{ background: "var(--bg-low)", borderRadius: 8, padding: "8px 10px" }}>
                  <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{k}</div>
                  <div style={{ fontWeight: 600 }}>{val}</div>
                </div>
              ))}
            </div>
            {(preview.modules.added.length > 0 || preview.modules.removed.length > 0) && (
              <div>
                {preview.modules.added.length > 0 && <div style={{ color: "var(--success)" }}>Switched on: {preview.modules.added.join(", ")}</div>}
                {preview.modules.removed.length > 0 && <div style={{ color: "var(--error)" }}><strong>Switched off: {preview.modules.removed.join(", ")}</strong></div>}
              </div>
            )}
            {preview.warnings.length > 0 && (
              <div className="alert alert-warn">
                <ul style={{ margin: 0, paddingLeft: 18 }}>{preview.warnings.map(w => <li key={w}>{w}</li>)}</ul>
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

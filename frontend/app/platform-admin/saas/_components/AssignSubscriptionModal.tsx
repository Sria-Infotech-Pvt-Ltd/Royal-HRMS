"use client";

// Add customer / assign subscription. Existing company: the subscription is
// attached (no new tenant). New company: created through the normal company
// provisioning, with the plan's modules. Preview → review → confirm.
// Assigning never marks a subscription paid: its modules are applied (or the
// new company set up) once a payment is confirmed or the payment is waived.
// End date: one billing period from the start (calendar months,
// lib/saasDates), kept in step with the start date and billing period until
// the admin types a date or chooses "No end date".
// Subscription amount: calculated from the plan (price × employees × billing
// period + GST — the server's own maths, lib/saasPricing); the employee count
// is required for that. A different amount is a manual adjustment and needs a
// reason, which the server keeps in the subscription history.

import { useState } from "react";
import Modal from "@/components/Modal";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { CompanySubscription, CustomerRow, SubscriptionPlan } from "@/types/platformAdmin";
import { apiMessage, fmtMoney } from "./SaasTabs";
import { chargeFor } from "@/lib/saasPricing";
import FieldError from "@/components/FieldError";
import * as v from "@/lib/saasValidation";
import { localToday, periodEnd } from "@/lib/saasDates";
import PaymentFields, { EMPTY_PAYMENT, MULTIPART, paymentErrors, paymentFormData } from "./PaymentFields";

interface Preview {
  modules: string[];
  current_modules: string[] | null;
  difference: { added: string[]; removed: string[] } | null;
  new_company: boolean;
}

export default function AssignSubscriptionModal({ customers, plans, preselect, onClose, onDone }: {
  customers: CustomerRow[];
  plans: SubscriptionPlan[];
  preselect: CustomerRow | null;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const unassigned = customers.filter(c => !c.subscription);
  const active = plans.filter(p => p.status === "active" && !p.is_legacy);
  const [mode, setMode] = useState<"existing" | "new">(preselect || unassigned.length ? "existing" : "new");
  const [clientId, setClientId] = useState(preselect?.id ?? "");
  const [company, setCompany] = useState({ company_code: "", company_name: "", admin_email: "", contact_name: "", contact_phone: "", gstin: "" });
  const [planId, setPlanId] = useState(active[0]?.id ?? "");
  const [startsOn, setStartsOn] = useState(localToday());
  // auto = one billing period from the start; manual = typed by the admin; none = no end date.
  const [endMode, setEndMode] = useState<"auto" | "manual" | "none">("auto");
  const [manualEnd, setManualEnd] = useState("");
  const [employees, setEmployees] = useState("");
  const [billing, setBilling] = useState<"" | "monthly" | "yearly">("monthly");
  const [notes, setNotes] = useState("");
  const [amountDue, setAmountDue] = useState<string | null>(null);   // null = follow the calculation
  const [amountReason, setAmountReason] = useState("");
  const [payMode, setPayMode] = useState<"later" | "record" | "waive">("later");
  const [payment, setPayment] = useState(EMPTY_PAYMENT);
  const [allowOverpayment, setAllowOverpayment] = useState(false);
  const [waiveReason, setWaiveReason] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [errors, setErrors] = useState<v.Errors>({});

  const plan = active.find(p => p.id === planId) ?? null;
  const count = Number(employees) || 0;
  const calc = plan && count > 0 ? chargeFor(plan.price_per_employee, plan.gst_rate, plan.gst_inclusive, count, billing) : null;
  const estimate = calc?.total ?? 0;
  const due = amountDue ?? (estimate > 0 ? estimate.toFixed(2) : "");
  // A total different from the calculated one is a manual adjustment.
  const manualAmount = amountDue !== null && amountDue.trim() !== "" && Number(amountDue) !== estimate;
  const autoEnd = periodEnd(startsOn, billing);
  const endsOn = endMode === "none" ? "" : endMode === "manual" ? manualEnd : autoEnd;
  const overpaying = payMode === "record" && Number(due) > 0 && Number(payment.amount) > Number(due);

  function body(dryRun: boolean) {
    return {
      ...(mode === "existing" ? { client: clientId } : { new_company: company }),
      plan: planId, starts_on: startsOn, ends_on: endsOn || null,
      employee_count: count || null, billing_period: billing, notes,
      // Only a manual adjustment is sent; otherwise the server calculates the amount.
      amount_due: manualAmount && Number(due) > 0 ? due : null,
      amount_reason: manualAmount ? amountReason.trim() : "",
      waive_reason: payMode === "waive" ? waiveReason.trim() : "",
      ...(dryRun ? { dry_run: true } : {}),
    };
  }

  function validate(): v.Errors {
    const found: v.Errors = v.collect({
      client: mode === "existing" && !clientId ? "Choose a company." : null,
      ...(mode === "new" ? {
        "new_company.company_name": v.businessName(company.company_name, "Company name") ?? v.maxLength(company.company_name, 200),
        "new_company.company_code": v.companyCode(company.company_code),
        "new_company.admin_email": v.email(company.admin_email),
        "new_company.contact_name": v.personName(company.contact_name) ?? v.maxLength(company.contact_name, 150),
        "new_company.contact_phone": v.phone(company.contact_phone),
        "new_company.gstin": v.gstin(company.gstin),
      } : {}),
      plan: plan ? null : "Choose an active plan.",
      employee_count: v.wholeNumber(employees, { isRequired: true, what: "Employees" })
        ?? (plan && count && plan.min_employees && count < plan.min_employees ? `${plan.name} needs at least ${plan.min_employees} employees.` : null)
        ?? (plan && count && plan.max_employees && count > plan.max_employees ? `${plan.name} allows at most ${plan.max_employees} employees.` : null),
      starts_on: v.date(startsOn, { what: "Start date" }),
      ends_on: v.date(endsOn, { isRequired: false, what: "End date" })
        ?? (endsOn && startsOn && endsOn < startsOn ? "End date cannot be before the start date." : null),
      billing_period: billing && plan && plan.billing_periods.length && !plan.billing_periods.includes(billing)
        ? `${plan.name} is billed ${plan.billing_periods.join(" or ")} only.` : null,
      notes: v.maxLength(notes, 1000),
      amount_due: v.decimal(due, { min: 0, minExclusive: true, isRequired: payMode === "record" && payment.confirm, what: "Subscription amount" }),
      amount_reason: manualAmount ? v.required(amountReason, "A reason for the changed amount") ?? v.maxLength(amountReason, 1000) : null,
      waive_reason: payMode === "waive" ? v.required(waiveReason, "A reason") ?? v.maxLength(waiveReason, 1000) : null,
    });
    if (payMode === "record") {
      for (const [k, m] of Object.entries(paymentErrors(payment))) found[`payment.${k}`] = m;
      if (overpaying && !allowOverpayment && !found["payment.amount"]) {
        found["payment.amount"] = "This is more than the subscription amount — correct it, or tick “Record it anyway”.";
      }
    }
    return found;
  }

  const paymentFieldErrors = Object.fromEntries(Object.entries(errors)
    .filter(([k]) => k.startsWith("payment.")).map(([k, m]) => [k.slice(8), m]));

  async function send(dryRun: boolean) {
    if (dryRun) {
      const found = validate();
      setErrors(found);
      if (Object.keys(found).length) { setErr("Please correct the highlighted fields."); return; }
    }
    setBusy(true);
    setErr(null);
    try {
      const { data } = await platformAdminApi.post(API.platformAdmin.saas.subscriptions, body(dryRun));
      if (dryRun) { setPreview(data.data); return; }
      if (payMode !== "record") { onDone(data.message ?? "Subscription assigned."); onClose(); return; }
      const sub = data.data as CompanySubscription;
      try {
        const { data: paid } = await platformAdminApi.post(API.platformAdmin.saas.payments(sub.client_id),
          paymentFormData(payment, overpaying && allowOverpayment), MULTIPART);
        onDone(`${data.message ?? "Subscription assigned."} ${paid.message ?? ""}`.trim());
      } catch (e) {
        onDone(`Subscription saved, but the payment was not recorded: ${apiMessage(e, "unknown error")} Record it from View → Payments.`);
      }
      onClose();
    } catch (e) {
      const fieldErrs = v.apiFieldErrors(e);
      setErrors(fieldErrs);
      if (Object.keys(fieldErrs).length) setPreview(null);
      setErr(apiMessage(e, dryRun ? "Could not prepare the preview." : "Could not assign the subscription."));
    } finally {
      setBusy(false);
    }
  }

  // Any edit drops the preview; the edited field's error goes away until the next check.
  const change = (fn: () => void, ...fields: string[]) => {
    fn();
    setPreview(null);
    if (fields.length) setErrors(e => Object.fromEntries(Object.entries(e).filter(([k]) => !fields.some(f => k === f || k.startsWith(`${f}.`)))));
  };

  return (
    <Modal title="Add customer / assign subscription" onClose={onClose} closeDisabled={busy} size="lg"
      footer={preview ? (
        <>
          <button className="btn btn-ghost" onClick={() => setPreview(null)} disabled={busy}>Back</button>
          <button className="btn btn-filled" onClick={() => send(false)} disabled={busy}>
            {busy ? "Saving…" : preview.new_company ? "Create company & assign" : "Confirm assignment"}
          </button>
        </>
      ) : (
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn-filled" onClick={() => send(true)} disabled={busy}>{busy ? "Checking…" : "Review"}</button>
        </>
      )}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14, fontSize: 13 }}>
        {err && <div className="alert alert-error">{err}</div>}

        {!preview && (
          <>
            <div style={{ display: "flex", gap: 16 }}>
              <label style={{ display: "flex", gap: 6 }}><input type="radio" checked={mode === "existing"} disabled={!unassigned.length}
                onChange={() => change(() => setMode("existing"))} /> Existing company</label>
              <label style={{ display: "flex", gap: 6 }}><input type="radio" checked={mode === "new"} disabled={!!preselect}
                onChange={() => change(() => setMode("new"))} /> New company</label>
            </div>

            {mode === "existing" ? (
              <div className="field-group">
                <label className="field-label">Company (without a subscription)</label>
                <select className="field-input" value={clientId} onChange={e => change(() => setClientId(e.target.value), "client")}>
                  <option value="">Select…</option>
                  {unassigned.map(c => <option key={c.id} value={c.id}>{c.company_name} ({c.company_code})</option>)}
                </select>
                <FieldError msg={errors.client} />
              </div>
            ) : (
              <div className="form-row cols-2">
                {([["company_name", "Company name *"], ["company_code", "Company code *"], ["admin_email", "Admin email (login) *"],
                  ["contact_name", "Contact person"], ["contact_phone", "Phone"], ["gstin", "GSTIN"]] as const).map(([k, label]) => (
                  <div className="field-group" key={k}>
                    <label className="field-label">{label}</label>
                    <input className="field-input" value={company[k]}
                      type={k === "admin_email" ? "email" : k === "contact_phone" ? "tel" : "text"}
                      inputMode={k === "contact_phone" ? "tel" : k === "admin_email" ? "email" : undefined}
                      maxLength={{ company_name: 200, company_code: 20, admin_email: 254, contact_name: 150, contact_phone: 20, gstin: 15 }[k]}
                      onChange={e => change(() => setCompany(c => ({ ...c, [k]: k === "company_code" || k === "gstin" ? e.target.value.toUpperCase() : e.target.value })), `new_company.${k}`)} />
                    <FieldError msg={errors[`new_company.${k}`]} />
                  </div>
                ))}
              </div>
            )}

            <div className="form-row cols-2">
              <div className="field-group">
                <label className="field-label">Plan *</label>
                <select className="field-input" value={planId} onChange={e => change(() => setPlanId(e.target.value), "plan", "employee_count", "billing_period")}>
                  {active.map(p => <option key={p.id} value={p.id}>{p.name} — {fmtMoney(p.price_per_employee, p.currency)}/employee/month</option>)}
                </select>
                <FieldError msg={errors.plan} />
              </div>
              <div className="field-group">
                <label className="field-label">Employees *</label>
                <input className="field-input" type="number" min={plan?.min_employees ?? 1} max={plan?.max_employees ?? v.MAX_EMPLOYEES} step={1}
                  inputMode="numeric" value={employees} onChange={e => change(() => setEmployees(e.target.value), "employee_count")} />
                {plan && (plan.min_employees || plan.max_employees) && (
                  <span style={{ fontSize: 11, color: "var(--on-variant)" }}>
                    {plan.name}: {plan.min_employees ?? 1}–{plan.max_employees ?? "no limit"} employees
                  </span>
                )}
                <FieldError msg={errors.employee_count} />
              </div>
              <div className="field-group">
                <label className="field-label">Start date *</label>
                <input className="field-input" type="date" min="2000-01-01" value={startsOn} onChange={e => change(() => setStartsOn(e.target.value), "starts_on", "ends_on")} />
                <FieldError msg={errors.starts_on} />
              </div>
              <div className="field-group">
                <label className="field-label">End date</label>
                <input className="field-input" type="date" min={startsOn || "2000-01-01"} value={endsOn} disabled={endMode === "none"}
                  onChange={e => change(() => { setManualEnd(e.target.value); setEndMode(e.target.value ? "manual" : "auto"); }, "ends_on")} />
                <span style={{ fontSize: 11, color: "var(--on-variant)" }}>
                  {endMode === "none" ? "No end date (open-ended)."
                    : endMode === "manual" ? <>Entered manually. <button type="button" className="btn btn-ghost btn-sm" style={{ padding: "0 4px" }}
                        onClick={() => change(() => setEndMode("auto"), "ends_on")}>Use one {billing === "yearly" ? "year" : "month"} from start</button></>
                    : autoEnd ? `One ${billing === "yearly" ? "year" : "month"} from the start date — updates with the start date and billing period.`
                    : "Choose a billing period to calculate it, or enter a date."}
                  {" "}Expiry is not enforced yet.
                </span>
                <label style={{ display: "flex", gap: 6, fontSize: 12 }}>
                  <input type="checkbox" checked={endMode === "none"}
                    onChange={e => change(() => setEndMode(e.target.checked ? "none" : "auto"), "ends_on")} /> No end date
                </label>
                <FieldError msg={errors.ends_on} />
              </div>
              <div className="field-group">
                <label className="field-label">Billing period</label>
                <select className="field-input" value={billing} onChange={e => change(() => setBilling(e.target.value as typeof billing), "billing_period")}>
                  <option value="monthly">Monthly</option><option value="yearly">Yearly</option><option value="">Not set</option>
                </select>
                <FieldError msg={errors.billing_period} />
              </div>
              <div className="field-group">
                <label className="field-label">Notes</label>
                <input className="field-input" value={notes} maxLength={1000} onChange={e => change(() => setNotes(e.target.value), "notes")} />
                <FieldError msg={errors.notes} />
              </div>
            </div>

            <div className="card" style={{ padding: 12, display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ fontWeight: 600 }}>Payment</div>
              <div className="form-row cols-2" style={{ marginBottom: 0 }}>
                <div className="field-group">
                  <label className="field-label">Subscription amount — total ({plan?.currency ?? "INR"})</label>
                  <input className="field-input" type="number" min={0} step="0.01" inputMode="decimal" value={due}
                    onChange={e => change(() => setAmountDue(e.target.value), "amount_due", "amount_reason")} />
                  <span style={{ fontSize: 11, color: "var(--on-variant)" }}>
                    {calc && plan
                      ? <>
                          {count} employees × {fmtMoney(plan.price_per_employee, plan.currency)} × {calc.months} month(s) = {fmtMoney(calc.subtotal, plan.currency)}
                          {plan.gst_inclusive ? ` (GST ${Number(plan.gst_rate)}% included)` : ` + GST ${Number(plan.gst_rate)}% ${fmtMoney(calc.gst, plan.currency)}`}
                          {" = "}{fmtMoney(calc.total, plan.currency)}.
                          {manualAmount && <> <button type="button" className="btn btn-ghost btn-sm" style={{ padding: "0 4px" }}
                            onClick={() => change(() => { setAmountDue(null); setAmountReason(""); }, "amount_due", "amount_reason")}>Use calculated amount</button></>}
                        </>
                      : "Enter the employee count to calculate the amount."}
                  </span>
                  <FieldError msg={errors.amount_due} />
                </div>
                {manualAmount && (
                  <div className="field-group">
                    <label className="field-label">Reason for the changed amount *</label>
                    <input className="field-input" value={amountReason} maxLength={1000} placeholder="e.g. negotiated discount"
                      onChange={e => change(() => setAmountReason(e.target.value), "amount_reason")} />
                    <span style={{ fontSize: 11, color: "var(--on-variant)" }}>Kept in the subscription history.</span>
                    <FieldError msg={errors.amount_reason} />
                  </div>
                )}
              </div>
              <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                {([["later", "Not received yet"], ["record", "Record a payment"], ["waive", "Waive payment"]] as const).map(([k, label]) => (
                  <label key={k} style={{ display: "flex", gap: 6 }}>
                    <input type="radio" checked={payMode === k} onChange={() => change(() => {
                      setPayMode(k);
                      // Recording a payment: pre-fill the full amount, so a full payment needs no typing.
                      if (k === "record" && !payment.amount && Number(due) > 0) setPayment(p => ({ ...p, amount: Number(due).toFixed(2) }));
                    }, "payment", "waive_reason", "amount_due")} /> {label}
                  </label>
                ))}
              </div>
              {payMode === "record" && (
                <>
                  <PaymentFields value={payment} errors={paymentFieldErrors}
                    amountHint={Number(due) > 0
                      ? (overpaying ? `More than the subscription amount (${fmtMoney(due, plan?.currency ?? "INR")}).`
                        : `Outstanding after this payment: ${fmtMoney(Math.max(Number(due) - (Number(payment.amount) || 0), 0), plan?.currency ?? "INR")}.`)
                      : undefined}
                    onChange={p => change(() => { setPayment(p); setAllowOverpayment(false); }, "payment", "amount_due")} />
                  {overpaying && (
                    <label className="alert alert-warn" style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                      <input type="checkbox" checked={allowOverpayment} style={{ marginTop: 2 }}
                        onChange={e => change(() => setAllowOverpayment(e.target.checked), "payment")} />
                      <span>This payment is more than the subscription amount ({fmtMoney(due, plan?.currency ?? "INR")}). Record it anyway?</span>
                    </label>
                  )}
                </>
              )}
              {payMode === "waive" && (
                <div className="field-group">
                  <label className="field-label">Reason for waiving *</label>
                  <input className="field-input" value={waiveReason} maxLength={1000} placeholder="e.g. pilot month, complimentary"
                    onChange={e => change(() => setWaiveReason(e.target.value), "waive_reason")} />
                  <FieldError msg={errors.waive_reason} />
                </div>
              )}
            </div>
          </>
        )}

        {preview && plan && (
          <>
            <div className="alert alert-info">
              <div>
                <strong>{preview.new_company ? `${company.company_name} (${company.company_code}) — new company` : unassigned.find(c => c.id === clientId)?.company_name}</strong>
                {" "}on <strong>{plan.name}</strong> from {startsOn}{endsOn ? ` to ${endsOn}` : ", no end date"}.
                {preview.new_company && " The company is provisioned in the background; the admin gets the activation email when it finishes."}
              </div>
            </div>
            <div>
              <strong>Payment:</strong>{" "}
              {Number(due) > 0 ? `${fmtMoney(due, plan.currency)} due${manualAmount ? ` (manual — calculated ${fmtMoney(estimate, plan.currency)})` : ""}. ` : "Amount due not set. "}
              {payMode === "waive" ? `Waived (${waiveReason.trim()}) — the subscription is applied now.`
                : payMode === "record" && payment.confirm && Number(payment.amount) >= Number(due)
                  ? `${fmtMoney(payment.amount, plan.currency)} received and confirmed — the subscription is applied now.`
                  : payMode === "record"
                    ? `${fmtMoney(payment.amount, plan.currency)} recorded${payment.confirm ? " and confirmed (partial)" : ", awaiting confirmation"}. The subscription is applied once payment is fully confirmed or waived.`
                    : `Awaiting payment — the subscription is applied ${preview.new_company ? "and the company set up " : ""}once payment is confirmed or waived.`}
            </div>
            <div><strong>Modules switched on:</strong> {preview.modules.length ? preview.modules.join(", ") : "core only"}</div>
            {preview.difference && (preview.difference.added.length > 0 || preview.difference.removed.length > 0) && (
              <div className="alert alert-warn">
                <div>
                  {preview.difference.added.length > 0 && <div>Will be switched on: {preview.difference.added.join(", ")}</div>}
                  {preview.difference.removed.length > 0 && <div><strong>Will be switched off: {preview.difference.removed.join(", ")}</strong> — the company loses access to these.</div>}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </Modal>
  );
}

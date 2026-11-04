"use client";

// Fields for recording a manually received payment (assignment modal and
// the subscription's Payments section). The receipt is optional: PDF, JPG
// or PNG under 5 MB, stored privately.

import FieldError from "@/components/FieldError";
import * as v from "@/lib/saasValidation";
import type { PaymentMethod } from "@/types/platformAdmin";
import { PAYMENT_METHODS } from "./SaasTabs";

export interface PaymentInput {
  amount: string;
  method: PaymentMethod;
  paid_on: string;
  reference: string;
  notes: string;
  receipt: File | null;
  confirm: boolean;
}

export const EMPTY_PAYMENT: PaymentInput = {
  amount: "", method: "upi", paid_on: new Date().toISOString().slice(0, 10), reference: "", notes: "",
  receipt: null, confirm: false,
};

const MAX_RECEIPT = 5 * 1024 * 1024;

const RECEIPT_TYPES = ["application/pdf", "image/jpeg", "image/png"];

/** Field errors for a payment entry (empty object = valid). */
export function paymentErrors(p: PaymentInput): v.Errors {
  return v.collect({
    amount: v.decimal(p.amount, { min: 0, minExclusive: true, what: "Amount received" }),
    method: PAYMENT_METHODS.some(([k]) => k === p.method) ? null : "Choose a payment method.",
    paid_on: v.date(p.paid_on, { notFuture: true, what: "Payment date" }),
    reference: v.reference(p.reference),
    notes: v.maxLength(p.notes, 1000),
    receipt: !p.receipt ? null
      : !RECEIPT_TYPES.includes(p.receipt.type) ? "Only PDF, JPG or PNG files."
      : p.receipt.size > MAX_RECEIPT ? "This file is larger than 5 MB." : null,
  });
}

export const paymentReady = (p: PaymentInput) => Object.keys(paymentErrors(p)).length === 0;

// platformAdminApi defaults to JSON; without this axios turns the FormData
// into JSON and the receipt never arrives as a file.
export const MULTIPART = { headers: { "Content-Type": "multipart/form-data" } };

export function paymentFormData(p: PaymentInput): FormData {
  const fd = new FormData();
  fd.append("amount", p.amount);
  fd.append("method", p.method);
  fd.append("paid_on", p.paid_on);
  fd.append("reference", p.reference.trim());
  fd.append("notes", p.notes.trim());
  fd.append("confirm", p.confirm ? "true" : "false");
  if (p.receipt) fd.append("receipt", p.receipt);
  return fd;
}

export default function PaymentFields({ value, onChange, errors = {} }: {
  value: PaymentInput;
  onChange: (p: PaymentInput) => void;
  errors?: v.Errors;
}) {
  const set = <K extends keyof PaymentInput>(k: K, v: PaymentInput[K]) => onChange({ ...value, [k]: v });
  const today = new Date().toISOString().slice(0, 10);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="form-row cols-2" style={{ marginBottom: 0 }}>
        <div className="field-group">
          <label className="field-label">Amount received *</label>
          <input className="field-input" type="number" min={0} step="0.01" inputMode="decimal" value={value.amount} onChange={e => set("amount", e.target.value)} />
          <FieldError msg={errors.amount} />
        </div>
        <div className="field-group">
          <label className="field-label">Payment method *</label>
          <select className="field-input" value={value.method} onChange={e => set("method", e.target.value as PaymentMethod)}>
            {PAYMENT_METHODS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
          <FieldError msg={errors.method} />
        </div>
        <div className="field-group">
          <label className="field-label">Payment date *</label>
          <input className="field-input" type="date" min="2000-01-01" max={today} value={value.paid_on} onChange={e => set("paid_on", e.target.value)} />
          <FieldError msg={errors.paid_on} />
        </div>
        <div className="field-group">
          <label className="field-label">Transaction / reference ID</label>
          <input className="field-input" value={value.reference} maxLength={100} placeholder="UTR, cheque no., UPI ref…"
            onChange={e => set("reference", e.target.value)} />
          <FieldError msg={errors.reference} />
        </div>
        <div className="field-group">
          <label className="field-label">Notes</label>
          <input className="field-input" value={value.notes} maxLength={1000} onChange={e => set("notes", e.target.value)} />
          <FieldError msg={errors.notes} />
        </div>
        <div className="field-group">
          <label className="field-label">Receipt (PDF, JPG or PNG, max 5 MB)</label>
          {value.receipt ? (
            <div className="field-input" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <i className="ti ti-file-invoice" />
              <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                title={value.receipt.name}>{value.receipt.name}</span>
              <button type="button" className="btn btn-ghost btn-sm" aria-label="Remove receipt" title="Remove receipt"
                onClick={() => set("receipt", null)} style={{ padding: "2px 6px" }}>
                <i className="ti ti-x" />
              </button>
            </div>
          ) : (
            <input className="field-input" type="file" accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
              onChange={e => set("receipt", e.target.files?.[0] ?? null)} />
          )}
          <FieldError msg={errors.receipt ?? (value.receipt && value.receipt.size > MAX_RECEIPT ? "This file is larger than 5 MB." : null)} />
        </div>
      </div>
      <label style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
        <input type="checkbox" checked={value.confirm} onChange={e => set("confirm", e.target.checked)} style={{ marginTop: 2 }} />
        <span>
          I confirm this payment has been received in our account.
          <span style={{ display: "block", fontSize: 11, color: "var(--on-variant)" }}>
            Leave unticked to record it now and confirm later, once the money is seen in the bank.
          </span>
        </span>
      </label>
    </div>
  );
}

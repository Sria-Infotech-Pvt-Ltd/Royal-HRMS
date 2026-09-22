"use client";

// "New declaration" modal for TaxTab. The real backend model
// (apps.payroll.models.EmployeeTaxDeclaration) has one row per employee per
// financial year, with `declared_investments` as a single dict covering all
// sections at once — it has no concept of a free-form "declaration type" +
// single "amount" per submission. This modal reconciles that by treating
// "Declaration type" as a select over the same fixed SECTIONS this app
// already declares tax sections with (80C/80D/80CCD1B/HRA), and "Amount" as
// the value to set for that one section — equivalent to what the section
// grid this modal replaces already did per-field, just presented as one
// focused action. Submitting merges that section into the existing
// declared_investments dict (so other sections aren't wiped) and then calls
// the real submit endpoint, so the declaration moves to "submitted" and
// shows up for HR review immediately, the same as the old Save+Submit flow.
//
// "Financial year" is NOT employee-choosable — MyTaxDeclarationView.get_or_
// create always resolves the current FY from company config, so this field
// is rendered read-only rather than as a real select.

import { useState } from "react";
import RequestModal from "@/components/RequestModal";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { SECTIONS, type ApiTaxDeclaration } from "./TaxTab";

interface Props {
  current: ApiTaxDeclaration | null;
  onClose: () => void;
  onSubmitted: () => void;
}

export default function TaxDeclarationModal({ current, onClose, onSubmitted }: Props) {
  const [regime, setRegime] = useState<"old" | "new">(current?.tax_regime ?? "new");
  const [section, setSection] = useState(SECTIONS[0].key);
  const [amount, setAmount] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setError(null);
    if (amount.trim() === "" || Number(amount) < 0) {
      setError("Enter a valid amount of zero or more.");
      return;
    }
    setSubmitting(true);
    try {
      const declared_investments = { ...(current?.declared_investments ?? {}), [section]: Number(amount) };
      await clientApi.patch(API.payroll.myTaxDeclaration, { tax_regime: regime, declared_investments });
      await clientApi.post(API.payroll.submitTaxDeclaration);
      onSubmitted();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg ?? "Failed to submit declaration.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <RequestModal
      title="Tax declaration"
      onClose={onClose}
      onSubmit={handleSubmit}
      submitting={submitting}
      error={error}
    >
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Financial Year</label>
          <select className="field-input field-select" value={current?.financial_year ?? ""} disabled>
            <option value={current?.financial_year ?? ""}>{current?.financial_year ?? "Current year"}</option>
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Tax Regime</label>
          <select
            className="field-input field-select"
            value={regime}
            onChange={e => setRegime(e.target.value as "old" | "new")}
          >
            <option value="new">New Regime (115BAC)</option>
            <option value="old">Old Regime</option>
          </select>
        </div>
      </div>
      <div className="form-row cols-2">
        <div className="field-group">
          <label className="field-label">Declaration Type</label>
          <select
            className="field-input field-select"
            value={section}
            onChange={e => setSection(e.target.value)}
          >
            {SECTIONS.map(s => <option key={s.key} value={s.key}>{s.label}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Amount (₹)</label>
          <input
            className="field-input"
            type="number"
            min={0}
            placeholder="0"
            value={amount}
            onChange={e => setAmount(e.target.value)}
          />
        </div>
      </div>
    </RequestModal>
  );
}

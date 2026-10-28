"use client";

// Tax declaration form. One declaration per employee per financial year (the server
// creates it on first load), saved as a draft or sent to payroll for review. Follows
// how Keka, Zoho Payroll and greytHR collect declarations and the particulars of
// Form 124 (the Income-tax Act 2025 successor to Form 12BB):
//   1. choose the tax regime (the deduction sections only apply to the old regime),
//   2. house rent with landlord details, then the itemised investments and payments,
//   3. income from a previous employer, and
//   4. a confirmation that the information is correct — proofs are uploaded item by
//      item afterwards from the Tax page (TaxProofsCard).
// What can be declared, and each limit, comes from the server's schema.

import { useState } from "react";
import Modal from "@/components/Modal";
import { useTaxDeclarationActions, useTaxDeclarationSchema } from "@/hooks/useTaxDeclaration";
import { buildDeclaredInvestments, formStateFromDeclaration, validateHomeLoan, validateRent } from "@/lib/taxDeclarationForm";
import type { ApiTaxDeclaration, TaxFormState, TaxRegime } from "@/types/taxDeclaration";
import TaxDeclarationSections from "./TaxDeclarationSections";
import TaxRentFields from "./TaxRentFields";
import TaxPreviousEmployerFields from "./TaxPreviousEmployerFields";
import { previousEmployerTdsError } from "@/lib/taxPreviousEmployer";

interface Props {
  current: ApiTaxDeclaration | null;
  onClose: () => void;
  onSaved: () => void;
}

const REGIME_OPTIONS: { value: TaxRegime; title: string; description: string }[] = [
  {
    value: "new", title: "New regime (Section 115BAC)",
    description: "Lower slab rates and a ₹75,000 standard deduction. HRA, 80C, 80D and loan interest can't be claimed.",
  },
  {
    value: "old", title: "Old regime",
    description: "Higher slab rates, but you can claim HRA, 80C, 80D, home loan interest and other deductions.",
  },
];

export default function TaxDeclarationModal({ current, onClose, onSaved }: Props) {
  const { data: schema, loading: isLoadingSchema, error: schemaError } = useTaxDeclarationSchema();
  const { isBusy, error, setError, save, saveAndSubmit } = useTaxDeclarationActions();
  const [form, setForm] = useState<TaxFormState>(() => formStateFromDeclaration(current));
  const [isConfirmed, setIsConfirmed] = useState(false);

  const isOldRegime = form.regime === "old";

  function buildInput() {
    return { tax_regime: form.regime, declared_investments: buildDeclaredInvestments(form, current) };
  }

  function findProblem(): string | null {
    if (!schema) return "The form is still loading.";
    const previousProblem = previousEmployerTdsError(form.previousEmployer.income, form.previousEmployer.tds);
    if (previousProblem) return previousProblem;
    return isOldRegime ? validateRent(form, schema) ?? validateHomeLoan(form) : null;
  }

  async function handleSave() {
    const problem = findProblem();
    if (problem) { setError(problem); return; }
    if (await save(buildInput())) onSaved();
  }

  async function handleSubmit() {
    const problem = findProblem();
    if (problem) { setError(problem); return; }
    if (!isConfirmed) { setError("Please confirm that the information you have declared is correct."); return; }
    if (await saveAndSubmit(buildInput())) onSaved();
  }

  return (
    <Modal
      title={<><i className="ti ti-receipt-tax" style={{ marginRight: 8 }} />Tax declaration — FY {current?.financial_year ?? ""}</>}
      onClose={onClose}
      closeDisabled={isBusy}
      maxWidth={820}
      scrollBody
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose} disabled={isBusy}>Cancel</button>
          <button className="btn btn-ghost" onClick={handleSave} disabled={isBusy || !schema}>Save draft</button>
          <button className="btn btn-filled" onClick={handleSubmit} disabled={isBusy || !schema}>
            {isBusy ? "Saving…" : "Submit for review"}
          </button>
        </>
      }
    >
      <div className="alert alert-info" style={{ marginBottom: 16 }}>
        <i className="ti ti-info-circle" />
        <span>
          Tell payroll what you plan to claim this year so the right tax is deducted each month. You can submit the
          proofs (receipts, certificates) item by item on the Tax page after you submit.
        </span>
      </div>

      {(error || schemaError) && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error ?? schemaError}</div>}

      <h4 style={{ margin: "0 0 8px", fontSize: 14 }}>Tax regime</h4>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12, marginBottom: 20 }}>
        {REGIME_OPTIONS.map(option => {
          const isSelected = form.regime === option.value;
          return (
            <label
              key={option.value}
              style={{
                display: "flex", gap: 10, padding: 14, borderRadius: 12, cursor: "pointer",
                border: `1.5px solid ${isSelected ? "var(--primary)" : "var(--outline-v)"}`,
                background: isSelected ? "color-mix(in srgb, var(--primary) 6%, transparent)" : "transparent",
              }}
            >
              <input type="radio" name="tax-regime" checked={isSelected} onChange={() => setForm({ ...form, regime: option.value })} />
              <span>
                <span style={{ display: "block", fontWeight: 600, fontSize: 14 }}>{option.title}</span>
                <span style={{ display: "block", fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>{option.description}</span>
              </span>
            </label>
          );
        })}
      </div>

      {isLoadingSchema && <div className="empty-state"><i className="ti ti-loader-2 spin" /><h3>Loading form…</h3></div>}

      {schema && isOldRegime && (
        <>
          <TaxRentFields schema={schema} form={form} onChange={setForm} />
          <TaxDeclarationSections schema={schema} form={form} onChange={setForm} />
        </>
      )}
      {schema && !isOldRegime && (
        <div className="alert alert-info" style={{ marginBottom: 16 }}>
          <i className="ti ti-info-circle" />
          <span>No investments or rent to declare under the new regime. Switch to the old regime if you want to claim deductions.</span>
        </div>
      )}

      {schema && <TaxPreviousEmployerFields form={form} onChange={setForm} />}

      <label style={{ display: "flex", gap: 8, alignItems: "flex-start", fontSize: 13, marginTop: 4 }}>
        <input type="checkbox" checked={isConfirmed} onChange={event => setIsConfirmed(event.target.checked)} style={{ marginTop: 3 }} />
        I declare that the information given above is true and complete, and I will submit proofs when payroll asks for them.
      </label>
    </Modal>
  );
}

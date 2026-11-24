"use client";

// Income from a previous employer in the same financial year (greytHR / Zoho collect the same) —
// payroll needs it to work out the tax still due. Applies to both tax regimes.

import { tr } from "@/lib/i18n/tr";
import type { TaxFormState } from "@/types/taxDeclaration";
import FieldError from "@/components/shared/FieldError";
import { previousEmployerTdsError } from "@/lib/taxPreviousEmployer";

interface Props {
  form: TaxFormState;
  onChange: (next: TaxFormState) => void;
}

export default function TaxPreviousEmployerFields({ form, onChange }: Props) {
  const previous = form.previousEmployer;
  const tdsError = previousEmployerTdsError(previous.income, previous.tds);

  function setPrevious(changes: Partial<TaxFormState["previousEmployer"]>) {
    onChange({ ...form, previousEmployer: { ...previous, ...changes } });
  }

  return (
    <section style={{ border: "1px solid var(--outline-v)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <h4 style={{ margin: 0, fontSize: 14 }}>{tr("Income from a previous employer")}</h4>
      <p style={{ margin: "4px 0 12px", fontSize: 12, color: "var(--on-variant)" }}>
        {tr("Joined this year? Enter what your previous employer paid you and the tax they deducted this financial year (from your Form 16 or last payslip). Leave blank if this is your first job this year.")}
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 200px), 1fr))", gap: 12 }}>
        <div className="field-group">
          <label className="field-label" htmlFor="tax-prev-name">{tr("Previous employer")}</label>
          <input id="tax-prev-name" className="field-input" value={previous.name} onChange={event => setPrevious({ name: event.target.value })} />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="tax-prev-income">{tr("Taxable income paid (₹)")}</label>
          <input id="tax-prev-income" className="field-input" type="number" min={0} placeholder={tr("₹ 0")} value={previous.income} onChange={event => setPrevious({ income: event.target.value })} />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="tax-prev-tds">{tr("Tax deducted (TDS) (₹)")}</label>
          <input id="tax-prev-tds" className={`field-input${tdsError ? " field-error" : ""}`} type="number" min={0} placeholder={tr("₹ 0")} value={previous.tds} onChange={event => setPrevious({ tds: event.target.value })} aria-invalid={!!tdsError} />
          <FieldError message={tdsError} />
        </div>
      </div>
    </section>
  );
}

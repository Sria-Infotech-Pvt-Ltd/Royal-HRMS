"use client";

// The itemised deduction groups of the tax declaration form (80C, NPS, 80D, loan
// interest, donations). Driven entirely by the server's schema so labels, proof hints
// and limits are never hard-coded here.

import type { TaxDeclarationSchema, TaxFormState, TaxSchemaGroup } from "@/types/taxDeclaration";
import { fieldCap, groupTotals, parseAmount } from "@/lib/taxDeclarationForm";

interface Props {
  schema: TaxDeclarationSchema;
  form: TaxFormState;
  onChange: (next: TaxFormState) => void;
}

function formatInr(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}`;
}

export default function TaxDeclarationSections({ schema, form, onChange }: Props) {
  function setAmount(key: string, text: string) {
    onChange({ ...form, amounts: { ...form.amounts, [key]: text } });
  }

  return (
    <>
      {schema.groups.map(group => (
        <GroupBlock key={group.key} group={group} schema={schema} form={form} onChange={onChange} onAmount={setAmount} />
      ))}
    </>
  );
}

function GroupBlock({ group, schema, form, onChange, onAmount }: Props & {
  group: TaxSchemaGroup;
  onAmount: (key: string, text: string) => void;
}) {
  const { declared, counted } = groupTotals(group, form);
  const isOverLimit = group.cap !== null && declared > group.cap;

  return (
    <section style={{ border: "1px solid var(--outline-v)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12, flexWrap: "wrap" }}>
        <h4 style={{ margin: 0, fontSize: 14 }}>{group.title}</h4>
        {group.cap !== null && (
          <span style={{ fontSize: 12, color: isOverLimit ? "var(--error)" : "var(--on-variant)" }}>
            {formatInr(counted)} of {formatInr(group.cap)}
            {isOverLimit && ` — only ${formatInr(group.cap)} will count`}
          </span>
        )}
      </div>
      {group.hint && <p style={{ margin: "4px 0 12px", fontSize: 12, color: "var(--on-variant)" }}>{group.hint}</p>}

      {group.key === "80d" && (
        <div style={{ display: "flex", gap: 20, flexWrap: "wrap", marginBottom: 12 }}>
          <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
            <input type="checkbox" checked={form.isSeniorSelfFamily} onChange={event => onChange({ ...form, isSeniorSelfFamily: event.target.checked })} />
            I, my spouse or a child is a senior citizen (60+)
          </label>
          <label style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 13 }}>
            <input type="checkbox" checked={form.isSeniorParents} onChange={event => onChange({ ...form, isSeniorParents: event.target.checked })} />
            A parent is a senior citizen (60+)
          </label>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12 }}>
        {group.fields.map(field => {
          const cap = fieldCap(field.key, schema, form);
          const amount = parseAmount(form.amounts[field.key] ?? "");
          const isOverFieldLimit = cap !== null && amount > cap;
          return (
            <div className="field-group" key={field.key}>
              <label className="field-label" htmlFor={`tax-${field.key}`}>{field.label}</label>
              <input
                id={`tax-${field.key}`}
                className={`field-input${isOverFieldLimit ? " field-error" : ""}`}
                type="number"
                min={0}
                placeholder="₹ 0"
                value={form.amounts[field.key] ?? ""}
                onChange={event => onAmount(field.key, event.target.value)}
              />
              <span style={{ fontSize: 11.5, color: isOverFieldLimit ? "var(--error)" : "var(--on-variant)", marginTop: 4 }}>
                {isOverFieldLimit && cap !== null ? `Only ${formatInr(cap)} will count. ` : ""}Proof: {field.proof}
              </span>
            </div>
          );
        })}
      </div>

      {group.key === "loans" && parseAmount(form.amounts["24B"] ?? "") > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 12, marginTop: 12 }}>
          <div className="field-group">
            <label className="field-label" htmlFor="tax-lender-name">Home loan lender&apos;s name <span style={{ color: "var(--error)" }}>*</span></label>
            <input
              id="tax-lender-name" className="field-input" value={form.homeLoan.lenderName}
              onChange={event => onChange({ ...form, homeLoan: { ...form.homeLoan, lenderName: event.target.value } })}
            />
          </div>
          <div className="field-group">
            <label className="field-label" htmlFor="tax-lender-pan">Lender&apos;s PAN <span style={{ color: "var(--error)" }}>*</span></label>
            <input
              id="tax-lender-pan" className="field-input" maxLength={10} placeholder="ABCDE1234F"
              style={{ textTransform: "uppercase" }} value={form.homeLoan.lenderPan}
              onChange={event => onChange({ ...form, homeLoan: { ...form.homeLoan, lenderPan: event.target.value } })}
            />
          </div>
        </div>
      )}
    </section>
  );
}

"use client";

// House-rent (HRA) part of the tax declaration — the particulars Form 124 asks for:
// rent paid, whether the city is a metro, and the landlord's name, address, PAN and
// relationship. The HRA exemption itself is worked out by payroll from this.

import { tr } from "@/lib/i18n/tr";
import type { TaxDeclarationSchema, TaxFormState } from "@/types/taxDeclaration";
import { parseAmount } from "@/lib/taxDeclarationForm";

interface Props {
  schema: TaxDeclarationSchema;
  form: TaxFormState;
  onChange: (next: TaxFormState) => void;
}

export default function TaxRentFields({ schema, form, onChange }: Props) {
  const { rent } = form;
  const monthlyRent = parseAmount(rent.monthlyRent);
  const yearlyRent = monthlyRent * (Number(rent.months) || 0);
  const isPanRequired = yearlyRent > schema.landlord_pan_threshold;

  function setRent(changes: Partial<TaxFormState["rent"]>) {
    onChange({ ...form, rent: { ...rent, ...changes } });
  }

  return (
    <section style={{ border: "1px solid var(--outline-v)", borderRadius: 12, padding: 16, marginBottom: 16 }}>
      <h4 style={{ margin: 0, fontSize: 14 }}>{tr("House rent — HRA exemption")}</h4>
      <p style={{ margin: "4px 0 12px", fontSize: 12, color: "var(--on-variant)" }}>
        {tr("Pay rent for a house you live in? Enter the details and payroll works out your HRA exemption. Proof: rent receipts or rent agreement. Leave the rent blank if you don't pay rent.")}
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 200px), 1fr))", gap: 12 }}>
        <div className="field-group">
          <label className="field-label" htmlFor="tax-rent-monthly">{tr("Monthly rent (₹)")}</label>
          <input id="tax-rent-monthly" className="field-input" type="number" min={0} placeholder={tr("₹ 0")} value={rent.monthlyRent} onChange={event => setRent({ monthlyRent: event.target.value })} />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="tax-rent-months">{tr("Months you pay rent this year")}</label>
          <input id="tax-rent-months" className="field-input" type="number" min={1} max={12} value={rent.months} onChange={event => setRent({ months: event.target.value })} />
        </div>
        <div className="field-group">
          <label className="field-label" htmlFor="tax-rent-city">{tr("City you live in")}</label>
          <select id="tax-rent-city" className="field-input field-select" value={rent.isMetro ? "metro" : "other"} onChange={event => setRent({ isMetro: event.target.value === "metro" })}>
            <option value="other">{tr("Other city")}</option>
            <option value="metro">{tr("Metro — {cities}", { cities: schema.metro_cities.join(", ") })}</option>
          </select>
        </div>
      </div>

      {monthlyRent > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(100%, 240px), 1fr))", gap: 12, marginTop: 12 }}>
          <div className="field-group">
            <label className="field-label" htmlFor="tax-landlord-name">{tr("Landlord's name")}</label>
            <input id="tax-landlord-name" className="field-input" value={rent.landlordName} onChange={event => setRent({ landlordName: event.target.value })} />
          </div>
          <div className="field-group">
            <label className="field-label" htmlFor="tax-landlord-relationship">{tr("Relationship with landlord")}</label>
            <select id="tax-landlord-relationship" className="field-input field-select" value={rent.landlordRelationship} onChange={event => setRent({ landlordRelationship: event.target.value })}>
              {schema.landlord_relationships.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label" htmlFor="tax-landlord-pan">
              {tr("Landlord's PAN")} {isPanRequired ? <span style={{ color: "var(--error)" }}>*</span> : tr("(needed above ₹1,00,000 a year)")}
            </label>
            <input
              id="tax-landlord-pan" className="field-input" maxLength={10} placeholder="ABCDE1234F"
              style={{ textTransform: "uppercase" }} value={rent.landlordPan}
              onChange={event => setRent({ landlordPan: event.target.value })}
            />
          </div>
          <div className="field-group" style={{ gridColumn: "1 / -1" }}>
            <label className="field-label" htmlFor="tax-landlord-address">{tr("Landlord's address")}</label>
            <input id="tax-landlord-address" className="field-input" value={rent.landlordAddress} onChange={event => setRent({ landlordAddress: event.target.value })} />
          </div>
        </div>
      )}
    </section>
  );
}

"use client";

import type { CompanySectionProps } from "@/types/company";

export default function SignatoryCard({ form, errors, canEdit, onFieldChange }: CompanySectionProps) {
  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-signature" /> Authorised Signatory</div>
      </div>
      <div style={{ padding: "20px 24px" }}>
        <div className="form-row cols-2 mb-16">
          <div className="field-group">
            <label className="field-label">Full Name</label>
            <input
              className="field-input"
              value={form.signatory_full_name}
              disabled={!canEdit}
              onChange={e => onFieldChange("signatory_full_name", e.target.value)}
            />
          </div>
          <div className="field-group">
            <label className="field-label">Designation</label>
            <input
              className="field-input"
              value={form.signatory_designation}
              disabled={!canEdit}
              onChange={e => onFieldChange("signatory_designation", e.target.value)}
              placeholder="e.g. Director, CFO"
            />
          </div>
        </div>
        <div className="form-row cols-2 mb-16">
          <div className="field-group">
            <label className="field-label">DIN / PAN</label>
            <input
              className="field-input"
              value={form.signatory_din_pan}
              disabled={!canEdit}
              onChange={e => onFieldChange("signatory_din_pan", e.target.value.toUpperCase())}
            />
          </div>
          <div className="field-group">
            <label className="field-label">Email</label>
            <input
              className={`field-input${errors.signatory_email ? " field-error" : ""}`}
              value={form.signatory_email}
              disabled={!canEdit}
              onChange={e => onFieldChange("signatory_email", e.target.value)}
              type="email"
            />
            {errors.signatory_email && <div className="field-error-msg">{errors.signatory_email}</div>}
          </div>
        </div>
        <label className="module-check">
          <input
            type="checkbox"
            checked={form.signatory_appears_on_invoices}
            disabled={!canEdit}
            onChange={e => onFieldChange("signatory_appears_on_invoices", e.target.checked)}
          />
          <span>Appears on invoices and payslips</span>
        </label>
      </div>
    </div>
  );
}

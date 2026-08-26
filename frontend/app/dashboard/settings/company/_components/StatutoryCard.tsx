"use client";

import type { CompanySectionProps } from "@/types/company";
import { COUNTRY_OPTIONS } from "../_data";

export default function StatutoryCard({ form, errors, canEdit, onFieldChange }: CompanySectionProps) {
  const isIndia = form.jurisdiction === "india";

  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-license" /> Legal &amp; Statutory</div>
      </div>
      <div className="form-row cols-2" style={{ padding: "20px 24px" }}>
        {isIndia ? (
          <>
            <div className="field-group">
              <label className="field-label">PAN <span style={{ color: "var(--error)" }}>*</span></label>
              <input
                className={`field-input${errors.pan ? " field-error" : ""}`}
                value={form.pan}
                disabled={!canEdit}
                onChange={e => onFieldChange("pan", e.target.value.toUpperCase())}
                placeholder="AAAAA0000A"
                maxLength={10}
              />
              {errors.pan && <div className="field-error-msg">{errors.pan}</div>}
            </div>
            <div className="field-group">
              <label className="field-label">TAN <span style={{ color: "var(--error)" }}>*</span></label>
              <input
                className={`field-input${errors.tan ? " field-error" : ""}`}
                value={form.tan}
                disabled={!canEdit}
                onChange={e => onFieldChange("tan", e.target.value.toUpperCase())}
                placeholder="PNEA12345B"
                maxLength={10}
              />
              {errors.tan && <div className="field-error-msg">{errors.tan}</div>}
            </div>
            <div className="field-group">
              <label className="field-label">CIN</label>
              <input
                className={`field-input${errors.cin ? " field-error" : ""}`}
                value={form.cin}
                disabled={!canEdit}
                onChange={e => onFieldChange("cin", e.target.value.toUpperCase())}
                placeholder="U74999MH2020PTC123456"
                maxLength={21}
              />
              {errors.cin && <div className="field-error-msg">{errors.cin}</div>}
            </div>
            <div className="field-group">
              <label className="field-label">ROC Jurisdiction</label>
              <input
                className="field-input"
                value={form.roc_jurisdiction}
                disabled={!canEdit}
                onChange={e => onFieldChange("roc_jurisdiction", e.target.value)}
                placeholder="e.g. Registrar of Companies, Hyderabad"
              />
            </div>
          </>
        ) : (
          <>
            <div className="field-group">
              <label className="field-label">Country of Registration <span style={{ color: "var(--error)" }}>*</span></label>
              <select
                className={`field-input${errors.country_of_registration ? " field-error" : ""}`}
                value={form.country_of_registration}
                disabled={!canEdit}
                onChange={e => onFieldChange("country_of_registration", e.target.value)}
              >
                <option value="">Select…</option>
                {COUNTRY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              {errors.country_of_registration && <div className="field-error-msg">{errors.country_of_registration}</div>}
            </div>
            <div className="field-group">
              <label className="field-label">Registration Number <span style={{ color: "var(--error)" }}>*</span></label>
              <input
                className={`field-input${errors.registration_number ? " field-error" : ""}`}
                value={form.registration_number}
                disabled={!canEdit}
                onChange={e => onFieldChange("registration_number", e.target.value)}
                placeholder="Company registration number"
              />
              {errors.registration_number && <div className="field-error-msg">{errors.registration_number}</div>}
            </div>
            <div className="field-group">
              <label className="field-label">EIN / Tax ID</label>
              <input
                className="field-input"
                value={form.ein}
                disabled={!canEdit}
                onChange={e => onFieldChange("ein", e.target.value)}
                placeholder="Employer Identification Number"
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

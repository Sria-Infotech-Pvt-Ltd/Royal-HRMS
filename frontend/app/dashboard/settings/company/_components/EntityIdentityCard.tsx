"use client";

import type { CompanySectionProps } from "@/types/company";
import { ENTITY_TYPE_OPTIONS_FOREIGN, ENTITY_TYPE_OPTIONS_INDIA } from "../_data";

export default function EntityIdentityCard({ form, errors, canEdit, onFieldChange }: CompanySectionProps) {
  const entityOptions = form.jurisdiction === "india" ? ENTITY_TYPE_OPTIONS_INDIA : ENTITY_TYPE_OPTIONS_FOREIGN;

  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-building" /> Entity &amp; Identity</div>
      </div>
      <div style={{ padding: "20px 24px" }}>
        {/* Jurisdiction toggle */}
        <div className="field-group mb-16">
          <label className="field-label">Jurisdiction</label>
          <div style={{ display: "flex", gap: 8 }}>
            {(["india", "foreign"] as const).map(j => (
              <button
                key={j}
                type="button"
                className={`btn btn-sm ${form.jurisdiction === j ? "btn-filled" : "btn-ghost"}`}
                disabled={!canEdit}
                onClick={() => {
                  onFieldChange("jurisdiction", j);
                  onFieldChange("entity_type", "");
                }}
              >
                {j === "india" ? "India" : "Foreign (outside India)"}
              </button>
            ))}
          </div>
        </div>

        <div className="form-row cols-2 mb-16">
          <div className="field-group">
            <label className="field-label">Company Name <span style={{ color: "var(--error)" }}>*</span></label>
            <input
              className={`field-input${errors.company_name ? " field-error" : ""}`}
              value={form.company_name}
              disabled={!canEdit}
              onChange={e => onFieldChange("company_name", e.target.value)}
              placeholder="Registered company name"
            />
            {errors.company_name && <div className="field-error-msg">{errors.company_name}</div>}
          </div>
          <div className="field-group">
            <label className="field-label">Trade Name</label>
            <input
              className="field-input"
              value={form.trade_name}
              disabled={!canEdit}
              onChange={e => onFieldChange("trade_name", e.target.value)}
              placeholder="DBA or brand name (optional)"
            />
          </div>
        </div>

        <div className="form-row cols-2 mb-16">
          <div className="field-group">
            <label className="field-label">Entity Type</label>
            <select
              className="field-input"
              value={form.entity_type}
              disabled={!canEdit}
              onChange={e => onFieldChange("entity_type", e.target.value)}
            >
              <option value="">Select…</option>
              {entityOptions.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">Date of Incorporation</label>
            <input
              className="field-input"
              type="date"
              value={form.date_of_incorporation}
              disabled={!canEdit}
              onChange={e => onFieldChange("date_of_incorporation", e.target.value)}
            />
          </div>
        </div>

        <div className="form-row cols-2">
          <label className="module-check" style={{ alignSelf: "start", marginTop: 22 }}>
            <input
              type="checkbox"
              checked={form.is_listed}
              disabled={!canEdit}
              onChange={e => onFieldChange("is_listed", e.target.checked)}
            />
            <span>Publicly listed company</span>
          </label>
          <div className="field-group">
            <label className="field-label">Holding Company (if a subsidiary)</label>
            <input
              className="field-input"
              value={form.holding_company_info}
              disabled={!canEdit}
              onChange={e => onFieldChange("holding_company_info", e.target.value)}
              placeholder="Parent company name and CIN"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

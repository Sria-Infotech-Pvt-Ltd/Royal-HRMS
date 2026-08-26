"use client";

import type { CompanySectionProps } from "@/types/company";
import { INDUSTRY_OPTIONS } from "../_data";

export default function BusinessProfileCard({ form, canEdit, onFieldChange }: CompanySectionProps) {
  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-briefcase" /> Business Profile</div>
      </div>
      <div style={{ padding: "20px 24px" }}>
        <div className="form-row cols-2 mb-16">
          <div className="field-group">
            <label className="field-label">Industry</label>
            <select
              className="field-input"
              value={form.industry}
              disabled={!canEdit}
              onChange={e => onFieldChange("industry", e.target.value)}
            >
              <option value="">Select…</option>
              {INDUSTRY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div className="field-group">
            <label className="field-label">NIC Code</label>
            <input
              className="field-input"
              value={form.nic_code}
              disabled={!canEdit}
              onChange={e => onFieldChange("nic_code", e.target.value)}
            />
          </div>
        </div>
        <div className="field-group">
          <label className="field-label">Nature of Business</label>
          <textarea
            className="field-input"
            value={form.nature_of_business}
            disabled={!canEdit}
            onChange={e => onFieldChange("nature_of_business", e.target.value)}
            rows={2}
            placeholder="Brief description of the business activity"
          />
        </div>
      </div>
    </div>
  );
}

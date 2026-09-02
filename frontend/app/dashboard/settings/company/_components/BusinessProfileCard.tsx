"use client";

import type { CompanySectionProps } from "@/types/company";
import ProfileCard from "./ProfileCard";
import { FINANCIAL_YEAR_OPTIONS, INDUSTRY_OPTIONS } from "../_data";

export default function BusinessProfileCard({ form, canEdit, onFieldChange, collapsed, onToggleCollapse }: CompanySectionProps) {
  return (
    <ProfileCard icon="ti-briefcase" title="Business profile" subtitle="What the company does, and how it accounts." collapsed={collapsed} onToggleCollapse={onToggleCollapse}>
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Industry <span style={{ color: "var(--error)" }}>*</span></label>
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
          <label className="field-label">NIC Code <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
          <input
            className="field-input"
            value={form.nic_code}
            disabled={!canEdit}
            onChange={e => onFieldChange("nic_code", e.target.value)}
          />
        </div>
      </div>
      <div className="field-group mb-16">
        <label className="field-label">Financial Year <span style={{ color: "var(--error)" }}>*</span></label>
        <select
          className="field-input"
          value={form.financial_year_start_month}
          disabled={!canEdit}
          onChange={e => onFieldChange("financial_year_start_month", e.target.value)}
        >
          {FINANCIAL_YEAR_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
      <div className="field-group">
        <label className="field-label">Nature of Business <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
        <textarea
          className="field-input"
          value={form.nature_of_business}
          disabled={!canEdit}
          onChange={e => onFieldChange("nature_of_business", e.target.value)}
          rows={2}
          placeholder="Brief description of the business activity"
        />
      </div>
    </ProfileCard>
  );
}

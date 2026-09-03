"use client";

import type { CompanySectionProps } from "@/types/company";
import ProfileCard from "./ProfileCard";
import { CURRENCY_OPTIONS, DATE_FORMAT_OPTIONS, TIMEZONE_OPTIONS } from "../_data";

export default function RegionalFormatsCard({ form, canEdit, onFieldChange, collapsed, onToggleCollapse }: CompanySectionProps) {
  return (
    <ProfileCard icon="ti-world" title="Regional & formats" subtitle="How amounts, dates, and times display across the app and on documents." collapsed={collapsed} onToggleCollapse={onToggleCollapse}>
      <div className="form-row cols-3 mb-8">
        <div className="field-group">
          <label className="field-label">Default Currency <span style={{ color: "var(--error)" }}>*</span></label>
          <select
            className="field-input field-select"
            value={form.default_currency}
            disabled={!canEdit}
            onChange={e => onFieldChange("default_currency", e.target.value)}
          >
            {CURRENCY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Date Format <span style={{ color: "var(--error)" }}>*</span></label>
          <select
            className="field-input field-select"
            value={form.date_format}
            disabled={!canEdit}
            onChange={e => onFieldChange("date_format", e.target.value)}
          >
            {DATE_FORMAT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Time Zone <span style={{ color: "var(--error)" }}>*</span></label>
          <select
            className="field-input field-select"
            value={form.timezone}
            disabled={!canEdit}
            onChange={e => onFieldChange("timezone", e.target.value)}
          >
            {TIMEZONE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>
      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
        Defaults follow the jurisdiction and country above. Override any of them if your reporting needs differ.
      </div>
    </ProfileCard>
  );
}

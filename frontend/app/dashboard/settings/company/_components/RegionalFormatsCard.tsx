"use client";

import type { CompanySectionProps } from "@/types/company";
import { CURRENCY_OPTIONS, DATE_FORMAT_OPTIONS, TIMEZONE_OPTIONS } from "../_data";

export default function RegionalFormatsCard({ form, canEdit, onFieldChange }: CompanySectionProps) {
  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-world" /> Regional &amp; Formats</div>
      </div>
      <div className="form-row cols-3" style={{ padding: "20px 24px" }}>
        <div className="field-group">
          <label className="field-label">Default Currency</label>
          <select
            className="field-input"
            value={form.default_currency}
            disabled={!canEdit}
            onChange={e => onFieldChange("default_currency", e.target.value)}
          >
            {CURRENCY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Date Format</label>
          <select
            className="field-input"
            value={form.date_format}
            disabled={!canEdit}
            onChange={e => onFieldChange("date_format", e.target.value)}
          >
            {DATE_FORMAT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">Timezone</label>
          <select
            className="field-input"
            value={form.timezone}
            disabled={!canEdit}
            onChange={e => onFieldChange("timezone", e.target.value)}
          >
            {TIMEZONE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
      </div>
    </div>
  );
}

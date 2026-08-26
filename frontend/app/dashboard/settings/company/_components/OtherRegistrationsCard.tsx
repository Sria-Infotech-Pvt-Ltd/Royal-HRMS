"use client";

import type { CompanySectionProps } from "@/types/company";
import { MSME_CLASS_OPTIONS } from "../_data";

export default function OtherRegistrationsCard({ form, canEdit, onFieldChange }: CompanySectionProps) {
  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-stamp" /> Other Registrations</div>
      </div>
      <div className="form-row cols-3" style={{ padding: "20px 24px" }}>
        <div className="field-group">
          <label className="field-label">Udyam / MSME Registration</label>
          <input
            className="field-input"
            value={form.udyam_msme}
            disabled={!canEdit}
            onChange={e => onFieldChange("udyam_msme", e.target.value)}
            placeholder="UDYAM-XX-00-0000000"
          />
        </div>
        <div className="field-group">
          <label className="field-label">MSME Class</label>
          <select
            className="field-input"
            value={form.msme_class}
            disabled={!canEdit}
            onChange={e => onFieldChange("msme_class", e.target.value)}
          >
            {MSME_CLASS_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </div>
        <div className="field-group">
          <label className="field-label">IEC (Import Export Code)</label>
          <input
            className="field-input"
            value={form.iec}
            disabled={!canEdit}
            onChange={e => onFieldChange("iec", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">EPFO Establishment Code</label>
          <input
            className="field-input"
            value={form.epfo_code}
            disabled={!canEdit}
            onChange={e => onFieldChange("epfo_code", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">ESIC Code</label>
          <input
            className="field-input"
            value={form.esic_code}
            disabled={!canEdit}
            onChange={e => onFieldChange("esic_code", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">Professional Tax Registration</label>
          <input
            className="field-input"
            value={form.professional_tax_reg}
            disabled={!canEdit}
            onChange={e => onFieldChange("professional_tax_reg", e.target.value)}
          />
        </div>
      </div>
    </div>
  );
}

"use client";

import type { CompanySectionProps } from "@/types/company";
import ProfileCard from "./ProfileCard";
import { MSME_CLASS_OPTIONS } from "../_data";

export default function OtherRegistrationsCard({ form, canEdit, onFieldChange }: CompanySectionProps) {
  return (
    <ProfileCard icon="ti-certificate" title="Other registrations" subtitle="Add only what applies. All optional.">
      <div className="form-row cols-2">
        <div className="field-group">
          <label className="field-label">Udyam / MSME <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
          <input
            className="field-input"
            value={form.udyam_msme}
            disabled={!canEdit}
            onChange={e => onFieldChange("udyam_msme", e.target.value)}
            placeholder="UDYAM-TS-00-0000000"
          />
        </div>
        <div className="field-group">
          <label className="field-label">MSME Class <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
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
          <label className="field-label">Import Export Code (IEC) <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
          <input
            className="field-input"
            value={form.iec}
            disabled={!canEdit}
            onChange={e => onFieldChange("iec", e.target.value)}
            placeholder="PAN-based"
          />
        </div>
        <div className="field-group">
          <label className="field-label">EPFO Code <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
          <input
            className="field-input"
            value={form.epfo_code}
            disabled={!canEdit}
            onChange={e => onFieldChange("epfo_code", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">ESIC Code <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
          <input
            className="field-input"
            value={form.esic_code}
            disabled={!canEdit}
            onChange={e => onFieldChange("esic_code", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">Professional Tax Reg. <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(state-wise, optional)</span></label>
          <input
            className="field-input"
            value={form.professional_tax_reg}
            disabled={!canEdit}
            onChange={e => onFieldChange("professional_tax_reg", e.target.value)}
          />
        </div>
      </div>
    </ProfileCard>
  );
}

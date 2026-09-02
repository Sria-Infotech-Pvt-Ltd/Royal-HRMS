"use client";

import type { CompanySectionProps } from "@/types/company";
import ProfileCard from "./ProfileCard";
import { MSME_CLASS_OPTIONS } from "../_data";

export default function OtherRegistrationsCard({ form, errors, canEdit, onFieldChange, collapsed, onToggleCollapse }: CompanySectionProps) {
  return (
    <ProfileCard icon="ti-certificate" title="Other registrations" subtitle="Add only what applies. All optional." collapsed={collapsed} onToggleCollapse={onToggleCollapse}>
      <div className="form-row cols-2">
        <div className="field-group">
          <label className="field-label">Udyam / MSME <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
          <input
            className={`field-input${errors.udyam_msme ? " field-error" : ""}`}
            value={form.udyam_msme}
            disabled={!canEdit}
            onChange={e => onFieldChange("udyam_msme", e.target.value.toUpperCase())}
            placeholder="UDYAM-TS-00-0000000"
          />
          {errors.udyam_msme && <div className="field-error-msg">{errors.udyam_msme}</div>}
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
            className={`field-input${errors.iec ? " field-error" : ""}`}
            value={form.iec}
            disabled={!canEdit}
            onChange={e => onFieldChange("iec", e.target.value.toUpperCase())}
            placeholder="PAN-based"
          />
          {errors.iec && <div className="field-error-msg">{errors.iec}</div>}
        </div>
        <div className="field-group">
          <label className="field-label">EPFO Code <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
          <input
            className={`field-input${errors.epfo_code ? " field-error" : ""}`}
            value={form.epfo_code}
            disabled={!canEdit}
            onChange={e => onFieldChange("epfo_code", e.target.value.toUpperCase())}
          />
          {errors.epfo_code && <div className="field-error-msg">{errors.epfo_code}</div>}
        </div>
        <div className="field-group">
          <label className="field-label">ESIC Code <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
          <input
            className={`field-input${errors.esic_code ? " field-error" : ""}`}
            value={form.esic_code}
            disabled={!canEdit}
            onChange={e => onFieldChange("esic_code", e.target.value)}
            placeholder="17 digits"
          />
          {errors.esic_code && <div className="field-error-msg">{errors.esic_code}</div>}
        </div>
        <div className="field-group">
          <label className="field-label">Professional Tax Reg. <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(state-wise, optional)</span></label>
          <input
            className={`field-input${errors.professional_tax_reg ? " field-error" : ""}`}
            value={form.professional_tax_reg}
            disabled={!canEdit}
            onChange={e => onFieldChange("professional_tax_reg", e.target.value.toUpperCase())}
          />
          {errors.professional_tax_reg && <div className="field-error-msg">{errors.professional_tax_reg}</div>}
        </div>
      </div>
    </ProfileCard>
  );
}

"use client";

import type { CompanySectionProps } from "@/types/company";
import ProfileCard from "./ProfileCard";
import ToggleSwitch from "@/components/ToggleSwitch";

export default function SignatoryCard({ form, errors, canEdit, onFieldChange, collapsed, onToggleCollapse }: CompanySectionProps) {
  return (
    <ProfileCard
      icon="ti-signature"
      title="Authorised signatory"
      subtitle="Who can legally sign invoices, contracts, and filings for the company. Not always a director."
      collapsed={collapsed}
      onToggleCollapse={onToggleCollapse}
    >
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Full Name <span style={{ color: "var(--error)" }}>*</span></label>
          <input
            className="field-input"
            value={form.signatory_full_name}
            disabled={!canEdit}
            onChange={e => onFieldChange("signatory_full_name", e.target.value)}
          />
        </div>
        <div className="field-group">
          <label className="field-label">Designation <span style={{ color: "var(--error)" }}>*</span></label>
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
          <label className="field-label">DIN / PAN <span style={{ color: "var(--error)" }}>*</span></label>
          <input
            className={`field-input${errors.signatory_din_pan ? " field-error" : ""}`}
            value={form.signatory_din_pan}
            disabled={!canEdit}
            onChange={e => onFieldChange("signatory_din_pan", e.target.value.toUpperCase())}
          />
          {errors.signatory_din_pan && <div className="field-error-msg">{errors.signatory_din_pan}</div>}
        </div>
        <div className="field-group">
          <label className="field-label">Signatory Email <span style={{ color: "var(--error)" }}>*</span></label>
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
      <ToggleSwitch
        checked={form.signatory_appears_on_invoices}
        disabled={!canEdit}
        onChange={checked => onFieldChange("signatory_appears_on_invoices", checked)}
        label={<>This signatory&apos;s name appears on issued invoices</>}
      />
    </ProfileCard>
  );
}

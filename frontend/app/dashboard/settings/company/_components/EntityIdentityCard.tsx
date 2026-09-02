"use client";

import type { CompanySectionProps } from "@/types/company";
import ProfileCard from "./ProfileCard";
import ToggleSwitch from "@/components/ToggleSwitch";
import {
  COUNTRY_OPTIONS, ENTITY_TYPE_OPTIONS_FOREIGN, ENTITY_TYPE_OPTIONS_INDIA,
  REGISTRATION_NUMBER_CONFIG, entityComplianceHint, parseCin, parsePan,
} from "../_data";

function Chip({ label, value, error }: { label: string; value: string; error?: boolean }) {
  return (
    <div style={{
      padding: "4px 10px", borderRadius: 6, fontSize: 11,
      background: error ? "var(--error-c)" : "var(--bg-low)",
      color: error ? "var(--error)" : "var(--on-variant)",
      border: `1px solid ${error ? "var(--error)" : "var(--outline-v)"}`,
    }}>
      <span style={{ opacity: 0.75 }}>{label}: </span>
      <span style={{ fontWeight: 600 }}>{value}</span>
    </div>
  );
}

export default function EntityIdentityCard({ form, errors, canEdit, onFieldChange, collapsed, onToggleCollapse }: CompanySectionProps) {
  const isIndia = form.jurisdiction === "india";
  const regConfig = isIndia ? (REGISTRATION_NUMBER_CONFIG[form.entity_type] ?? null) : null;
  // The CIN structure-decode chips below only mean anything for an actual
  // CIN — an LLPIN or a generic Partnership/Trust filing number doesn't
  // encode a listing flag / state code / registration year the same way.
  const cin = regConfig?.label === "CIN" ? parseCin(form.cin) : null;
  const pan = isIndia ? parsePan(form.pan, form.entity_type) : null;
  const entityLabel = (isIndia ? ENTITY_TYPE_OPTIONS_INDIA : ENTITY_TYPE_OPTIONS_FOREIGN)
    .find(o => o.value === form.entity_type)?.label ?? "";
  const hint = entityComplianceHint(form.jurisdiction, form.entity_type, entityLabel);

  return (
    <ProfileCard icon="ti-building" title="Entity & identity" subtitle="Legal identity and statutory registration numbers." collapsed={collapsed} onToggleCollapse={onToggleCollapse}>
      {hint && (
        <div style={{
          display: "flex", gap: 8, alignItems: "flex-start", padding: "10px 14px",
          background: "rgba(30,78,140,0.06)", border: "1px solid rgba(30,78,140,0.15)",
          borderRadius: 8, marginBottom: 16, fontSize: 12, color: "var(--on-bg)",
        }}>
          <i className="ti ti-info-circle" style={{ fontSize: 14, color: "var(--primary)", marginTop: 1 }} />
          <span>{hint}</span>
        </div>
      )}

      {!isIndia && (
        <div className="field-group mb-16">
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
      )}

      <div className="field-group mb-16">
        <label className="field-label">Legal Name <span style={{ color: "var(--error)" }}>*</span></label>
        <input
          className={`field-input${errors.company_name ? " field-error" : ""}`}
          value={form.company_name}
          disabled={!canEdit}
          onChange={e => onFieldChange("company_name", e.target.value)}
          placeholder="Registered company name"
        />
        {errors.company_name && <div className="field-error-msg">{errors.company_name}</div>}
      </div>

      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Trade / Brand Name</label>
          <input
            className="field-input"
            value={form.trade_name}
            disabled={!canEdit}
            onChange={e => onFieldChange("trade_name", e.target.value)}
            placeholder="DBA or brand name (optional)"
          />
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

      {isIndia ? (
        <>
          {regConfig ? (
            <div className="form-row cols-2 mb-8">
              <div className="field-group">
                <label className="field-label">{regConfig.label} {regConfig.required && <span style={{ color: "var(--error)" }}>*</span>}</label>
                <input
                  className={`field-input${errors.cin ? " field-error" : ""}`}
                  value={form.cin}
                  disabled={!canEdit}
                  onChange={e => onFieldChange("cin", e.target.value.toUpperCase())}
                  placeholder={regConfig.placeholder}
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
            </div>
          ) : (
            <div className="field-group mb-8">
              <label className="field-label">ROC Jurisdiction</label>
              <input
                className="field-input"
                value={form.roc_jurisdiction}
                disabled={!canEdit}
                onChange={e => onFieldChange("roc_jurisdiction", e.target.value)}
                placeholder="e.g. Registrar of Companies, Hyderabad"
              />
            </div>
          )}
          {cin && (
            <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
              <Chip label="Listing" value={cin.listing} />
              <Chip label="State" value={cin.stateCode} />
              <Chip label="Reg. year" value={cin.year} />
            </div>
          )}

          <div className="form-row cols-2 mb-8">
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
              <label className="field-label">TAN <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(for TDS)</span></label>
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
          </div>
          {pan && (
            <div style={{ display: "flex", gap: 8, marginBottom: 16, flexWrap: "wrap" }}>
              <Chip label="Holder (4th char)" value={`${pan.holderChar} · ${pan.holderType}`} />
              {pan.expectedChar && (
                <Chip
                  label="Entity match"
                  value={pan.holderChar === pan.expectedChar ? "✓ matches" : `✗ expected ${pan.expectedChar}`}
                  error={pan.holderChar !== pan.expectedChar}
                />
              )}
            </div>
          )}

          <div className="mb-16">
            <ToggleSwitch
              checked={form.is_listed}
              disabled={!canEdit}
              onChange={checked => onFieldChange("is_listed", checked)}
              label="Publicly listed company"
            />
          </div>
        </>
      ) : (
        <>
          <div className="form-row cols-2 mb-16">
            <div className="field-group">
              <label className="field-label">Registration / Incorp. No. <span style={{ color: "var(--error)" }}>*</span></label>
              <input
                className={`field-input${errors.registration_number ? " field-error" : ""}`}
                value={form.registration_number}
                disabled={!canEdit}
                onChange={e => onFieldChange("registration_number", e.target.value)}
              />
              {errors.registration_number && <div className="field-error-msg">{errors.registration_number}</div>}
            </div>
            <div className="field-group">
              <label className="field-label">Registry / Authority</label>
              <input
                className="field-input"
                value={form.roc_jurisdiction}
                disabled={!canEdit}
                onChange={e => onFieldChange("roc_jurisdiction", e.target.value)}
              />
            </div>
          </div>
          <div className="field-group mb-16">
            <label className="field-label">EIN {form.country_of_registration === "US" && <span style={{ color: "var(--error)" }}>*</span>}</label>
            <input
              className={`field-input${errors.ein ? " field-error" : ""}`}
              value={form.ein}
              disabled={!canEdit}
              onChange={e => onFieldChange("ein", e.target.value)}
              placeholder="Employer Identification Number"
            />
            {errors.ein && <div className="field-error-msg">{errors.ein}</div>}
          </div>
          <div className="mb-16">
            <ToggleSwitch
              checked={form.is_listed}
              disabled={!canEdit}
              onChange={checked => onFieldChange("is_listed", checked)}
              label="Publicly listed company"
            />
          </div>
        </>
      )}

      <div className="field-group">
        <label className="field-label">Holding / Parent Company <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(if a subsidiary)</span></label>
        <input
          className="field-input"
          value={form.holding_company_info}
          disabled={!canEdit}
          onChange={e => onFieldChange("holding_company_info", e.target.value)}
          placeholder="Parent company name and CIN"
        />
      </div>
    </ProfileCard>
  );
}

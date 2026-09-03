"use client";

import type { CompanySectionProps } from "@/types/company";
import ProfileCard from "./ProfileCard";
import ToggleSwitch from "@/components/ToggleSwitch";
import { STATES } from "../_data";

export default function AddressCard({ form, errors, canEdit, onFieldChange, collapsed, onToggleCollapse }: CompanySectionProps) {
  const isIndia = form.jurisdiction === "india";
  const sameAsRegistered = form.communication_address_same_as_registered;

  return (
    <ProfileCard
      icon="ti-map-pin"
      title="Registered office"
      subtitle={isIndia ? "The statutory address on record. Must be in India." : "The registered address in the company's home country."}
      collapsed={collapsed}
      onToggleCollapse={onToggleCollapse}
    >
      <div className="field-group mb-16">
        <label className="field-label">Address Line 1 <span style={{ color: "var(--error)" }}>*</span></label>
        <textarea
          className={`field-input${errors.address ? " field-error" : ""}`}
          value={form.address}
          disabled={!canEdit}
          onChange={e => onFieldChange("address", e.target.value)}
          placeholder="Street address, building, floor…"
          rows={2}
        />
        {errors.address && <div className="field-error-msg">{errors.address}</div>}
      </div>
      <div className="form-row cols-3 mb-16">
        <div className="field-group">
          <label className="field-label">City <span style={{ color: "var(--error)" }}>*</span></label>
          <input
            className={`field-input${errors.city ? " field-error" : ""}`}
            value={form.city}
            disabled={!canEdit}
            onChange={e => onFieldChange("city", e.target.value)}
            placeholder="Hyderabad"
          />
          {errors.city && <div className="field-error-msg">{errors.city}</div>}
        </div>
        <div className="field-group">
          <label className="field-label">State <span style={{ color: "var(--error)" }}>*</span></label>
          {isIndia ? (
            <select
              className="field-input field-select"
              value={form.state}
              disabled={!canEdit}
              onChange={e => onFieldChange("state", e.target.value)}
            >
              <option value="">Select…</option>
              {STATES.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          ) : (
            <input
              className="field-input"
              value={form.state}
              disabled={!canEdit}
              onChange={e => onFieldChange("state", e.target.value)}
              placeholder="State / Province"
            />
          )}
        </div>
        <div className="field-group">
          <label className="field-label">PIN <span style={{ color: "var(--error)" }}>*</span></label>
          <input
            className={`field-input${errors.pin_code ? " field-error" : ""}`}
            value={form.pin_code}
            disabled={!canEdit}
            onChange={e => onFieldChange(
              "pin_code",
              isIndia ? e.target.value.replace(/\D/g, "").slice(0, 6) : e.target.value,
            )}
            placeholder={isIndia ? "500081" : "Postal code"}
            maxLength={isIndia ? 6 : 12}
          />
          {errors.pin_code && <div className="field-error-msg">{errors.pin_code}</div>}
        </div>
      </div>

      <div className="mb-16">
        <ToggleSwitch
          checked={sameAsRegistered}
          disabled={!canEdit}
          onChange={checked => onFieldChange("communication_address_same_as_registered", checked)}
          label="Communication address is the same as registered office"
        />
      </div>

      {!sameAsRegistered && (
        <>
          <div className="field-group mb-16">
            <label className="field-label">Communication Address <span style={{ color: "var(--error)" }}>*</span></label>
            <textarea
              className={`field-input${errors.communication_address ? " field-error" : ""}`}
              value={form.communication_address}
              disabled={!canEdit}
              onChange={e => onFieldChange("communication_address", e.target.value)}
              placeholder="Street address, building, floor…"
              rows={2}
            />
            {errors.communication_address && <div className="field-error-msg">{errors.communication_address}</div>}
          </div>
          <div className="form-row cols-3">
            <div className="field-group">
              <label className="field-label">City <span style={{ color: "var(--error)" }}>*</span></label>
              <input
                className={`field-input${errors.communication_city ? " field-error" : ""}`}
                value={form.communication_city}
                disabled={!canEdit}
                onChange={e => onFieldChange("communication_city", e.target.value)}
              />
              {errors.communication_city && <div className="field-error-msg">{errors.communication_city}</div>}
            </div>
            <div className="field-group">
              <label className="field-label">State</label>
              {isIndia ? (
                <select
                  className="field-input field-select"
                  value={form.communication_state}
                  disabled={!canEdit}
                  onChange={e => onFieldChange("communication_state", e.target.value)}
                >
                  <option value="">Select…</option>
                  {STATES.map(s => <option key={s} value={s}>{s}</option>)}
                </select>
              ) : (
                <input
                  className="field-input"
                  value={form.communication_state}
                  disabled={!canEdit}
                  onChange={e => onFieldChange("communication_state", e.target.value)}
                />
              )}
            </div>
            <div className="field-group">
              <label className="field-label">PIN</label>
              <input
                className={`field-input${errors.communication_pin_code ? " field-error" : ""}`}
                value={form.communication_pin_code}
                disabled={!canEdit}
                onChange={e => onFieldChange(
                  "communication_pin_code",
                  isIndia ? e.target.value.replace(/\D/g, "").slice(0, 6) : e.target.value,
                )}
                maxLength={isIndia ? 6 : 12}
              />
              {errors.communication_pin_code && <div className="field-error-msg">{errors.communication_pin_code}</div>}
            </div>
          </div>
        </>
      )}
    </ProfileCard>
  );
}

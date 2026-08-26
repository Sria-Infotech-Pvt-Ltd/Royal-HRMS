"use client";

import type { CompanySectionProps } from "@/types/company";
import { STATES } from "../_data";

export default function AddressCard({ form, errors, canEdit, onFieldChange }: CompanySectionProps) {
  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-map-pin" /> Registered Address</div>
      </div>
      <div style={{ padding: "20px 24px" }}>
        <div className="field-group mb-16">
          <label className="field-label">Address <span style={{ color: "var(--error)" }}>*</span></label>
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
        <div className="form-row cols-3">
          <div className="field-group">
            <label className="field-label">City <span style={{ color: "var(--error)" }}>*</span></label>
            <input
              className={`field-input${errors.city ? " field-error" : ""}`}
              value={form.city}
              disabled={!canEdit}
              onChange={e => onFieldChange("city", e.target.value)}
              placeholder="Mumbai"
            />
            {errors.city && <div className="field-error-msg">{errors.city}</div>}
          </div>
          <div className="field-group">
            <label className="field-label">State / UT</label>
            {form.jurisdiction === "india" ? (
              <select
                className="field-input"
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
            <label className="field-label">PIN / Postal Code</label>
            <input
              className={`field-input${errors.pin_code ? " field-error" : ""}`}
              value={form.pin_code}
              disabled={!canEdit}
              onChange={e => onFieldChange(
                "pin_code",
                form.jurisdiction === "india" ? e.target.value.replace(/\D/g, "").slice(0, 6) : e.target.value,
              )}
              placeholder={form.jurisdiction === "india" ? "400001" : "Postal code"}
              maxLength={form.jurisdiction === "india" ? 6 : 12}
            />
            {errors.pin_code && <div className="field-error-msg">{errors.pin_code}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

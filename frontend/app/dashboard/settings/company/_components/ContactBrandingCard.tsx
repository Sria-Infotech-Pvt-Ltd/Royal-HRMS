"use client";

import type { RefObject } from "react";
import type { CompanySectionProps } from "@/types/company";
import ProfileCard from "./ProfileCard";

interface Props extends CompanySectionProps {
  displayLogo: string | null;
  fileRef: RefObject<HTMLInputElement | null>;
  onLogoChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onLogoRemove: () => void;
}

export default function ContactBrandingCard({
  form, errors, canEdit, onFieldChange, displayLogo, fileRef, onLogoChange, onLogoRemove, collapsed, onToggleCollapse,
}: Props) {
  const initial = form.company_name.trim().charAt(0).toUpperCase() || "?";

  return (
    <ProfileCard icon="ti-mail" title="Contact & branding" subtitle="Public-facing details shown in the app and on documents." collapsed={collapsed} onToggleCollapse={onToggleCollapse}>
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">Primary Email <span style={{ color: "var(--error)" }}>*</span></label>
          <input
            className={`field-input${errors.primary_email ? " field-error" : ""}`}
            value={form.primary_email}
            disabled={!canEdit}
            onChange={e => onFieldChange("primary_email", e.target.value)}
            placeholder="info@company.com"
            type="email"
          />
          {errors.primary_email && <div className="field-error-msg">{errors.primary_email}</div>}
        </div>
        <div className="field-group">
          <label className="field-label">Phone <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
          <input
            className={`field-input${errors.official_phone ? " field-error" : ""}`}
            value={form.official_phone}
            disabled={!canEdit}
            onChange={e => onFieldChange("official_phone", e.target.value)}
            placeholder="+91 40 1234 5678"
            type="tel"
          />
          {errors.official_phone && <div className="field-error-msg">{errors.official_phone}</div>}
        </div>
      </div>

      <div className="field-group mb-16">
        <label className="field-label">Website <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span></label>
        <input
          className={`field-input${errors.website ? " field-error" : ""}`}
          value={form.website}
          disabled={!canEdit}
          onChange={e => onFieldChange("website", e.target.value)}
          placeholder="www.company.com"
          type="text"
        />
        {errors.website && <div className="field-error-msg">{errors.website}</div>}
      </div>

      <div className="field-group">
        <label className="field-label">Company Logo</label>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 44, height: 44, borderRadius: "50%", overflow: "hidden", flexShrink: 0,
            background: displayLogo ? "var(--bg-low)" : "rgba(30,78,140,0.12)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            {displayLogo
              ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img src={displayLogo} alt="Logo" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              )
              : <span style={{ fontWeight: 700, fontSize: 18, color: "var(--primary)" }}>{initial}</span>
            }
          </div>
          {canEdit && (
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-ghost btn-sm" type="button" onClick={() => fileRef.current?.click()}>
                {displayLogo ? "Change logo" : "Upload logo"}
              </button>
              {displayLogo && (
                <button className="btn btn-ghost btn-sm" type="button" onClick={onLogoRemove}>
                  <i className="ti ti-trash" />
                </button>
              )}
            </div>
          )}
          {canEdit && (
            <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp,image/svg+xml" style={{ display: "none" }} onChange={onLogoChange} />
          )}
        </div>
        <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 6 }}>
          JPEG, PNG, WebP or SVG · Max 5 MB
        </div>
      </div>
    </ProfileCard>
  );
}

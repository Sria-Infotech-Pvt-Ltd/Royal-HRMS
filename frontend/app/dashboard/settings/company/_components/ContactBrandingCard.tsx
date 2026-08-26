"use client";

import type { RefObject } from "react";
import type { CompanySectionProps } from "@/types/company";

interface Props extends CompanySectionProps {
  displayLogo: string | null;
  fileRef: RefObject<HTMLInputElement | null>;
  onLogoChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onLogoRemove: () => void;
}

export default function ContactBrandingCard({
  form, errors, canEdit, onFieldChange, displayLogo, fileRef, onLogoChange, onLogoRemove,
}: Props) {
  return (
    <div className="card mb-24">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-phone" /> Contact &amp; Branding</div>
      </div>
      <div style={{ padding: "20px 24px" }}>
        {/* Logo upload */}
        <div style={{ display: "flex", alignItems: "flex-start", gap: 20, marginBottom: 24, paddingBottom: 20, borderBottom: "1px solid var(--outline-v)" }}>
          <div style={{
            width: 80, height: 80, borderRadius: 10,
            border: "1.5px dashed var(--outline-v)", overflow: "hidden",
            background: displayLogo
              ? "repeating-conic-gradient(#e5e7eb 0% 25%, #fff 0% 50%) 0 0 / 12px 12px"
              : "var(--bg-low)",
            flexShrink: 0,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            {displayLogo
              ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img src={displayLogo} alt="Logo" style={{ width: "100%", height: "100%", objectFit: "contain" }} />
              )
              : <i className="ti ti-photo" style={{ fontSize: 28, color: "var(--outline)" }} />
            }
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 3 }}>Company Logo</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 10 }}>
              Used on payslips and other documents issued in your name · JPEG, PNG, WebP or SVG · Max 5 MB
            </div>
            {canEdit && (
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn btn-ghost btn-sm" type="button" onClick={() => fileRef.current?.click()}>
                  <i className="ti ti-upload" /> {displayLogo ? "Change" : "Upload"}
                </button>
                {displayLogo && (
                  <button className="btn btn-ghost btn-sm" type="button" onClick={onLogoRemove}>
                    <i className="ti ti-trash" /> Remove
                  </button>
                )}
              </div>
            )}
            {canEdit && (
              <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp,image/svg+xml" style={{ display: "none" }} onChange={onLogoChange} />
            )}
          </div>
        </div>

        <div className="form-row cols-2 mb-16">
          <div className="field-group">
            <label className="field-label">Primary Email</label>
            <input
              className={`field-input${errors.primary_email ? " field-error" : ""}`}
              value={form.primary_email}
              disabled={!canEdit}
              onChange={e => onFieldChange("primary_email", e.target.value)}
              placeholder="contact@company.com"
              type="email"
            />
            {errors.primary_email && <div className="field-error-msg">{errors.primary_email}</div>}
          </div>
          <div className="field-group">
            <label className="field-label">Official Phone</label>
            <input
              className={`field-input${errors.official_phone ? " field-error" : ""}`}
              value={form.official_phone}
              disabled={!canEdit}
              onChange={e => onFieldChange("official_phone", e.target.value)}
              placeholder="+91 98765 43210"
              type="tel"
            />
            {errors.official_phone && <div className="field-error-msg">{errors.official_phone}</div>}
          </div>
        </div>

        <div className="field-group">
          <label className="field-label">Website</label>
          <input
            className={`field-input${errors.website ? " field-error" : ""}`}
            value={form.website}
            disabled={!canEdit}
            onChange={e => onFieldChange("website", e.target.value)}
            placeholder="https://airahrms.com"
            type="url"
          />
          {errors.website && <div className="field-error-msg">{errors.website}</div>}
        </div>
      </div>
    </div>
  );
}

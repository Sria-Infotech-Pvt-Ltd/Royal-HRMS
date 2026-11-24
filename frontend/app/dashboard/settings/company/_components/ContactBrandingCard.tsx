"use client";

import type { RefObject } from "react";
import type { CompanySectionProps } from "@/types/company";
import { PORTAL_URL_HELP } from "@/lib/portalUrl";
import ProfileCard from "./ProfileCard";
import { useT } from "@/hooks/useI18n";

interface Props extends CompanySectionProps {
  displayLogo: string | null;
  fileRef: RefObject<HTMLInputElement | null>;
  onLogoChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onLogoRemove: () => void;
}

export default function ContactBrandingCard({
  form, errors, canEdit, onFieldChange, displayLogo, fileRef, onLogoChange, onLogoRemove, collapsed, onToggleCollapse,
}: Props) {
  const t = useT();
  const initial = form.company_name.trim().charAt(0).toUpperCase() || "?";

  return (
    <ProfileCard icon="ti-mail" title={t("Contact & branding")} subtitle={t("Public-facing details shown in the app and on documents.")} collapsed={collapsed} onToggleCollapse={onToggleCollapse}>
      <div className="form-row cols-2 mb-16">
        <div className="field-group">
          <label className="field-label">{t("Primary Email")} <span style={{ color: "var(--error)" }}>*</span></label>
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
          <label className="field-label">{t("Phone")} <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>{t("(optional)")}</span></label>
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
        <label className="field-label">{t("Website")} <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>{t("(optional)")}</span></label>
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

      <div className="field-group mb-16" data-testid="portal-url-field">
        <label className="field-label" htmlFor="company-portal-url">{t("Employee Portal URL")}</label>
        <input
          id="company-portal-url"
          className={`field-input${errors.portal_url ? " field-error" : ""}`}
          value={form.portal_url ?? ""}
          disabled={!canEdit}
          onChange={e => onFieldChange("portal_url", e.target.value)}
          placeholder="https://aira.nxsys.in"
          type="text"
        />
        {errors.portal_url
          ? <div className="field-error-msg">{errors.portal_url}</div>
          : <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 6 }}>{t(PORTAL_URL_HELP)}</div>}
      </div>

      <div className="field-group">
        <label className="field-label">{t("Company Logo")}</label>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 44, height: 44, borderRadius: "50%", overflow: "hidden", flexShrink: 0,
            background: displayLogo ? "var(--bg-low)" : "color-mix(in srgb, var(--brand) 12%, transparent)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            {displayLogo
              ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img src={displayLogo} alt={t("Logo")} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              )
              : <span style={{ fontWeight: 700, fontSize: 18, color: "var(--primary)" }}>{initial}</span>
            }
          </div>
          {canEdit && (
            <div style={{ display: "flex", gap: 8 }}>
              <button className="btn btn-ghost btn-sm" type="button" onClick={() => fileRef.current?.click()}>
                {displayLogo ? t("Change logo") : t("Upload logo")}
              </button>
              {displayLogo && (
                <button className="btn btn-ghost btn-sm" type="button" onClick={onLogoRemove} aria-label={t("Delete")}>
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
          {t("JPEG, PNG, WebP or SVG · Max 5 MB")}
        </div>
      </div>
    </ProfileCard>
  );
}

"use client";

// Geofence fields of the Company Code form (shown inside the folded Attendance area row): the on/off switch, the office coordinates, a map preview and the allowed radius.

import ToggleSwitch from "@/components/ToggleSwitch";
import { useT } from "@/hooks/useI18n";
import type { BranchForm } from "./_data";
import { Field } from "./BranchFormUi";
import BranchLocationPreview from "./BranchLocationPreview";
import { RADIUS_MAX, RADIUS_MIN, RADIUS_PRESETS, RADIUS_SLIDER_MAX } from "./branchFormCopy";

interface Props {
  form: BranchForm;
  onChange: (patch: Partial<BranchForm>) => void;
  clearErrors: (...keys: string[]) => void;
  errors: Record<string, string>;
}

export default function BranchGeofenceSection({ form, onChange, clearErrors, errors }: Props) {
  const t = useT();
  const radius = Number(form.allowed_radius_meters);
  const setRadius = (value: string) => { clearErrors("allowed_radius_meters"); onChange({ allowed_radius_meters: value }); };
  return (
    <div>
      <ToggleSwitch
        label={t("Enable Geofencing")} checked={form.geofencing_enabled}
        onChange={checked => { clearErrors("latitude", "longitude", "allowed_radius_meters"); onChange({ geofencing_enabled: checked }); }}
      />

      {form.geofencing_enabled && (
        <div style={{ marginTop: 16 }}>
          <div className="form-row cols-2">
            <Field label={t("Latitude")} required error={errors.latitude} htmlFor="bf-lat">
              <input
                id="bf-lat" type="number" step="any" className={`field-input${errors.latitude ? " field-error" : ""}`} value={form.latitude} placeholder={t("Latitude of the office entrance")}
                onChange={event => { clearErrors("latitude"); onChange({ latitude: event.target.value }); }}
              />
            </Field>
            <Field label={t("Longitude")} required error={errors.longitude} htmlFor="bf-lng">
              <input
                id="bf-lng" type="number" step="any" className={`field-input${errors.longitude ? " field-error" : ""}`} value={form.longitude} placeholder={t("Longitude of the office entrance")}
                onChange={event => { clearErrors("longitude"); onChange({ longitude: event.target.value }); }}
              />
            </Field>
          </div>
          <div style={{ fontSize: 11, color: "var(--on-variant)", margin: "-6px 0 14px" }}>
            <i className="ti ti-info-circle" aria-hidden="true" style={{ marginRight: 4 }} />
            {t("Tip: in Google Maps, right-click the office and copy the numbers, or use “Use my current location” below.")}
          </div>
          <BranchLocationPreview
            latitude={form.latitude} longitude={form.longitude} stateId={form.state} cityId={form.city} radiusMeters={form.allowed_radius_meters}
            onUseLocation={(latitude, longitude) => { clearErrors("latitude", "longitude"); onChange({ latitude, longitude }); }}
          />

          <Field label={t("Allowed Radius (metres)")} required error={errors.allowed_radius_meters} htmlFor="bf-radius">
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 10 }}>
              {RADIUS_PRESETS.map(preset => (
                <button
                  key={preset} type="button" className={radius === preset ? "btn btn-filled" : "btn btn-ghost"} aria-pressed={radius === preset}
                  style={{ padding: "4px 12px", fontSize: 12 }} onClick={() => setRadius(String(preset))}
                >
                  {t("{radius} m", { radius: preset })}
                </button>
              ))}
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <input
                type="range" aria-label={t("Allowed radius slider")} min={RADIUS_MIN} max={RADIUS_SLIDER_MAX} step={10} style={{ flex: 1 }}
                value={Math.min(Math.max(radius || RADIUS_MIN, RADIUS_MIN), RADIUS_SLIDER_MAX)} onChange={event => setRadius(event.target.value)}
              />
              <input
                id="bf-radius" type="number" min={RADIUS_MIN} max={RADIUS_MAX} style={{ width: 96 }} className={`field-input${errors.allowed_radius_meters ? " field-error" : ""}`}
                value={form.allowed_radius_meters} onChange={event => setRadius(event.target.value)}
              />
            </div>
          </Field>
        </div>
      )}
    </div>
  );
}

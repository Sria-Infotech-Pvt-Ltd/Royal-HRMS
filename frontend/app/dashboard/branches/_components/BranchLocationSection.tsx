"use client";

// Location section of the Company Code form: state, city (or a new city), and the state's GST registration.

import { useT } from "@/hooks/useI18n";
import type { GSTRegistration } from "@/types/company";
import { OTHER_CITY, type BranchForm, type CityObj, type StateObj } from "./_data";
import { Field, FormSection } from "./BranchFormUi";
import { SECTION_COPY } from "./branchFormCopy";

export interface GstContext {
  stateName: string | undefined;
  options: GSTRegistration[];
  missing: boolean;
  choiceRequired: boolean;
}

interface Props {
  form: BranchForm;
  onChange: (patch: Partial<BranchForm>) => void;
  clearErrors: (...keys: string[]) => void;
  errors: Record<string, string>;
  states: StateObj[];
  cities: CityObj[];
  citiesLoading: boolean;
  newCityName: string;
  setNewCityName: (value: string) => void;
  gst: GstContext;
}

const registrationLabel = (registration: GSTRegistration) => `${registration.gstin}${registration.place_of_business ? ` — ${registration.place_of_business}` : ""}`;

export default function BranchLocationSection({ form, onChange, clearErrors, errors, states, cities, citiesLoading, newCityName, setNewCityName, gst }: Props) {
  const t = useT();
  return (
    <FormSection id="bf-location" title={t(SECTION_COPY.location.title)} subtitle={t(SECTION_COPY.location.hint)}>
      <div className="form-row cols-2">
        <Field label={t("State/Region")} required error={errors.state} htmlFor="bf-state">
          <select
            id="bf-state" className={`field-input field-select${errors.state ? " field-error" : ""}`} value={form.state}
            onChange={event => {
              clearErrors("state", "city", "new_city_name", "gst_registration");
              setNewCityName("");
              onChange({ state: event.target.value, city: "", gst_registration: "" });
            }}
          >
            <option value="">{t("Select State")}</option>
            {states.map(state => <option key={state.id} value={state.id}>{state.name}</option>)}
          </select>
        </Field>
        <Field label={t("City")} required error={errors.city} htmlFor="bf-city">
          <select
            id="bf-city" className={`field-input field-select${errors.city ? " field-error" : ""}`} value={form.city} disabled={!form.state || citiesLoading}
            onChange={event => {
              clearErrors("city", "branch_code", "new_city_name");
              if (event.target.value !== OTHER_CITY) setNewCityName("");
              onChange({ city: event.target.value });
            }}
          >
            <option value="">{!form.state ? t("Select a state first") : citiesLoading ? t("Loading cities…") : t("Select City")}</option>
            {cities.map(city => <option key={city.id} value={city.id}>{city.name}</option>)}
            {form.state && <option value={OTHER_CITY}>{t("Other (type city name)")}</option>}
          </select>
          {form.city === OTHER_CITY && (
            <div style={{ marginTop: 8 }}>
              <input
                type="text" aria-label={t("New city name")} className={`field-input${errors.new_city_name ? " field-error" : ""}`} value={newCityName}
                placeholder={t("Enter new city name")} maxLength={100}
                onChange={event => {
                  clearErrors("new_city_name", "branch_code");
                  setNewCityName(event.target.value.replace(/[^A-Za-z '-]/g, ""));
                }}
              />
              {errors.new_city_name && <p className="field-error-msg">{errors.new_city_name}</p>}
            </div>
          )}
        </Field>
      </div>

      {gst.missing && (
        <div className="alert alert-warn" style={{ alignItems: "flex-start", marginTop: 4 }}>
          <i className="ti ti-alert-triangle" />
          <div>
            {t("There is no GST registration for")} <strong>{gst.stateName}</strong> {t("yet. This office will need one.")}{" "}
            <a href="/dashboard/settings/company" target="_blank" rel="noopener noreferrer" style={{ fontWeight: 600 }}>{t("Add one in Company Profile")}</a>
          </div>
        </div>
      )}

      {gst.options.length === 1 && (
        <div style={{ fontSize: 13, color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 6, marginTop: 4 }}>
          <i className="ti ti-receipt-tax" aria-hidden="true" style={{ fontSize: 14 }} />
          <span style={{ fontFamily: "monospace" }}>{gst.options[0].gstin}</span>
          <span>({gst.stateName}{gst.options[0].place_of_business ? ` — ${gst.options[0].place_of_business}` : ""}) {t("— only one on file, used automatically")}</span>
        </div>
      )}

      {gst.options.length > 1 && (
        <Field
          label={t("GST Registration")} required={gst.choiceRequired} error={errors.gst_registration} htmlFor="bf-gst"
          hint={t("{stateName} has {count} GST registrations. Pick the one this office uses.", { stateName: gst.stateName ?? "", count: gst.options.length })}
        >
          <select
            id="bf-gst" className={`field-input field-select${errors.gst_registration ? " field-error" : ""}`} value={form.gst_registration}
            onChange={event => { clearErrors("gst_registration"); onChange({ gst_registration: event.target.value }); }}
          >
            <option value="">{t("Select which GST registration this Company Code uses…")}</option>
            {gst.options.map(registration => <option key={registration.id} value={registration.id}>{registrationLabel(registration)}</option>)}
          </select>
        </Field>
      )}
    </FormSection>
  );
}

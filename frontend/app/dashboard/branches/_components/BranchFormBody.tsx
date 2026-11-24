"use client";

// The body of the Add / Edit Company Code modal, on ONE screen: a one-line summary, then Where is it, Name and address and Office
// settings in plain order. The two optional parts (Company Code Admin, Attendance area) are folded rows that say what is set and
// open when clicked, or by themselves when they hold a problem. It changes no rules: BranchManagement owns the form, the
// validation and the save.

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import { tr } from "@/lib/i18n/tr";
import { OTHER_CITY, isLeaderActive, type ApiEmployeeOption, type BranchAdminSeat, type BranchForm, type CityObj, type CurrentBranchAdmin, type LeaderForm, type StateObj } from "./_data";
import BranchDetailsSection from "./BranchDetailsSection";
import { CollapsibleSection } from "./BranchFormUi";
import BranchFormSummary from "./BranchFormSummary";
import BranchGeofenceSection from "./BranchGeofenceSection";
import BranchLocationSection, { type GstContext } from "./BranchLocationSection";
import BranchSettingsSection from "./BranchSettingsSection";
import LeaderFields from "./LeaderFields";
import { SECTION_COPY, geofenceSummary } from "./branchFormCopy";

export interface BranchAdminProps {
  form: LeaderForm;
  setForm: (updater: (form: LeaderForm) => LeaderForm) => void;
  employees: ApiEmployeeOption[];
  seats: BranchAdminSeat[];
  errors: Record<string, string>;
  /** Edit only: who holds the branch-wide seat now. */
  currentAdmin: CurrentBranchAdmin | null;
}

interface Props {
  form: BranchForm;
  onChange: (patch: Partial<BranchForm>) => void;
  clearErrors: (...keys: string[]) => void;
  errors: Record<string, string>;
  states: StateObj[];
  cities: CityObj[];
  citiesLoading: boolean;
  codeLoading: boolean;
  newCityName: string;
  setNewCityName: (value: string) => void;
  gst: GstContext;
  admin: BranchAdminProps;
}

const GEOFENCE_FIELDS = ["latitude", "longitude", "allowed_radius_meters"];

function adminSummary(admin: BranchAdminProps): string {
  if (isLeaderActive(admin.form)) return admin.form.mode === "new" ? tr("A new person will be invited when you save") : tr("An existing employee will be moved here when you save");
  return admin.currentAdmin ? tr("Current admin: {name}", { name: admin.currentAdmin.employee.full_name }) : tr("Not assigned");
}

export default function BranchFormBody({ form, onChange, clearErrors, errors, states, cities, citiesLoading, codeLoading, newCityName, setNewCityName, gst, admin }: Props) {
  const t = useT();
  // Folded unless something is already set. The form is only mounted once an edit's saved details have loaded.
  const [adminOpen, setAdminOpen] = useState(() => isLeaderActive(admin.form) || admin.currentAdmin !== null);
  const [geofenceOpen, setGeofenceOpen] = useState(() => form.geofencing_enabled);
  const adminHasError = Object.keys(admin.errors).length > 0;
  const geofenceHasError = GEOFENCE_FIELDS.some(field => errors[field]);

  const stateName = states.find(state => String(state.id) === form.state)?.name ?? "";
  const cityName = form.city === OTHER_CITY ? newCityName.trim() : cities.find(city => String(city.id) === form.city)?.name ?? "";
  const placeLabel = [cityName, stateName].filter(Boolean).join(", ");

  return (
    <>
      <BranchFormSummary form={form} placeLabel={placeLabel} codeLoading={codeLoading} />
      <BranchLocationSection
        form={form} onChange={onChange} clearErrors={clearErrors} errors={errors} states={states} cities={cities}
        citiesLoading={citiesLoading} newCityName={newCityName} setNewCityName={setNewCityName} gst={gst}
      />
      <BranchDetailsSection form={form} onChange={onChange} clearErrors={clearErrors} errors={errors} codeLoading={codeLoading} />
      <BranchSettingsSection form={form} onChange={onChange} />

      <div style={{ marginTop: 26, paddingTop: 22, borderTop: "1px solid var(--outline-v)" }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: ".05em" }}>{t("Optional")}</div>
        {/* Shown on Add and Edit alike; Edit prefills the current admin (see loadEditDetails). */}
        <CollapsibleSection
          id="bf-admin" icon="ti-user-shield" title={t(SECTION_COPY.admin.title)} summary={adminSummary(admin)}
          open={adminOpen || adminHasError} onToggle={() => setAdminOpen(open => !open)}
        >
          <p style={{ margin: "0 0 14px", fontSize: 12.5, color: "var(--on-variant)" }}>{t(SECTION_COPY.admin.hint)}</p>
          <LeaderFields
            label={t("Company Code Admin")} form={admin.form} setForm={admin.setForm} employees={admin.employees} seats={admin.seats}
            errors={admin.errors} prefix="branchAdmin" currentAdmin={admin.currentAdmin}
          />
        </CollapsibleSection>
        <CollapsibleSection
          id="bf-geofence" icon="ti-radar-2" title={t(SECTION_COPY.geofence.title)} summary={geofenceSummary(form.geofencing_enabled, form.allowed_radius_meters)}
          open={geofenceOpen || geofenceHasError} onToggle={() => setGeofenceOpen(open => !open)}
        >
          <p style={{ margin: "0 0 14px", fontSize: 12.5, color: "var(--on-variant)" }}>{t(SECTION_COPY.geofence.hint)}</p>
          <BranchGeofenceSection form={form} onChange={onChange} clearErrors={clearErrors} errors={errors} />
        </CollapsibleSection>
      </div>
    </>
  );
}

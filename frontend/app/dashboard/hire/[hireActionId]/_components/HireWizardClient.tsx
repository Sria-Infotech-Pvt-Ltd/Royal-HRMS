"use client";

// The Hire wizard — Stage 2 of the two-stage Hire flow. Reuses the exact
// same prop-driven step components the existing onboarding wizards already
// use (DynamicStepFields/EducationChecklist/ExperienceList/
// FamilyNominationStep/AssetsList), but everything here is saved into the
// HireAction's own draft_data blob (PATCH /hire-actions/<id>/) instead of
// each step's own per-employee REST endpoint — there is no employee row to
// attach those to until "Hire employee" on the Review step actually
// creates one (HireActionCompleteView applies every list here to real rows
// at that point). Sequential step-locking mirrors the self-service
// wizard's own StepIndicator/highestSaved pattern, not the HR-onboarding
// wizard's free-jump one — see the approved plan for why.
import { useEffect, useMemo, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { ProfileForm } from "@/app/onboarding/_types";
import type { OnboardingFieldConfigByStep, EducationExperienceFieldConfigResponse } from "@/types/onboardingFieldConfig";
import DynamicStepFields from "@/app/onboarding/_components/DynamicStepFields";
import EducationChecklist, { type EducationEntry } from "@/app/onboarding/_components/EducationChecklist";
import ExperienceList, { type ExperienceEntry } from "@/app/onboarding/_components/ExperienceList";
import FamilyNominationStep, { type FamilyEntry, type NomineeEntry } from "@/app/onboarding/_components/FamilyNominationStep";
import AssetsList, { type AssetEntry } from "@/app/onboarding/_components/AssetsList";
import EmergencyContactsList, { type EmergencyContactEntry } from "./EmergencyContactsList";
import AddressFields, { EMPTY_ADDRESS_EXTRAS, type AddressExtras } from "./AddressFields";
import ScanFillModal, { type ScanSuggestions } from "./ScanFillModal";
import EmployeePhotoUpload from "./EmployeePhotoUpload";
import HireWizardSidebar from "./HireWizardSidebar";
import EmploymentStep, { EMPTY_EMPLOYMENT, type EmploymentDraft } from "./EmploymentStep";
import BasicPayStep, { EMPTY_BASIC_PAY, type BasicPayDraft } from "./BasicPayStep";
import StatutoryAccountsStep, { EMPTY_STATUTORY, type StatutoryDraft } from "./StatutoryAccountsStep";
import DocumentsChecklistStep, { REQUIRED_DOC_KEYS, EMPTY_VERIFICATION, type VerificationDraft } from "./DocumentsChecklistStep";
import ReviewStep from "./ReviewStep";
import {
  EMPTY_FORM,
  type IdentityExtras,
  EMPTY_IDENTITY_EXTRAS,
  EMERGENCY_BUILTIN_KEYS,
  ADDRESS_BUILTIN_KEYS,
  emptyEmergencyContact,
  type HireActionData,
  STEPS,
} from "./_wizardData";

export default function HireWizardClient({ hireActionId, onClose, onHired }: { hireActionId: string; onClose: () => void; onHired: () => void }) {
  const [action, setAction] = useState<HireActionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState(0);
  const [highestSaved, setHighestSaved] = useState(-1);
  const [stepErr, setStepErr] = useState("");

  const [salutation, setSalutation] = useState("");
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [lastName, setLastName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [nationality, setNationality] = useState("Indian");
  const [placeOfBirth, setPlaceOfBirth] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [identityExtras, setIdentityExtras] = useState<IdentityExtras>(EMPTY_IDENTITY_EXTRAS);
  const [emergencyContacts, setEmergencyContacts] = useState<EmergencyContactEntry[]>([emptyEmergencyContact("temp-ec-1", true)]);
  const [addressExtras, setAddressExtras] = useState<AddressExtras>(EMPTY_ADDRESS_EXTRAS);
  const [showScanFill, setShowScanFill] = useState(false);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [form, setForm] = useState<ProfileForm>(EMPTY_FORM);
  const [employment, setEmployment] = useState<EmploymentDraft>(EMPTY_EMPLOYMENT);
  const [basicPay, setBasicPay] = useState<BasicPayDraft>(EMPTY_BASIC_PAY);
  const [statutory, setStatutory] = useState<StatutoryDraft>(EMPTY_STATUTORY);
  const [familyEntries, setFamilyEntries] = useState<FamilyEntry[]>([]);
  const [nomineeEntries, setNomineeEntries] = useState<NomineeEntry[]>([]);
  const [educationEntries, setEducationEntries] = useState<EducationEntry[]>([]);
  const [experienceEntries, setExperienceEntries] = useState<ExperienceEntry[]>([]);
  const [assetEntries, setAssetEntries] = useState<AssetEntry[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<Set<string>>(new Set());
  const [verification, setVerification] = useState<VerificationDraft>(EMPTY_VERIFICATION);

  const [fieldConfig, setFieldConfig] = useState<OnboardingFieldConfigByStep>({});
  const [eduExpFieldConfig, setEduExpFieldConfig] = useState<EducationExperienceFieldConfigResponse>({ education: [], experience: [] });

  const [hiring, setHiring] = useState(false);
  const [hireError, setHireError] = useState<string | null>(null);

  let tempId = 0;
  const nextTempId = () => `temp-${++tempId}`;

  useEffect(() => {
    Promise.all([
      clientApi.get<{ data: HireActionData }>(API.hireActions.detail(hireActionId)),
      clientApi.get<{ data: OnboardingFieldConfigByStep }>(API.onboarding.fieldConfig),
      clientApi.get<{ data: EducationExperienceFieldConfigResponse }>(API.onboarding.educationExperienceFieldConfig),
    ]).then(([a, fc, efc]) => {
      const data = a.data.data;
      setAction(data);
      setPhotoUrl(data.photo_url);
      setFieldConfig(fc.data?.data ?? {});
      setEduExpFieldConfig(efc.data?.data ?? { education: [], experience: [] });

      const d = data.draft_data || {};
      setSalutation(String(d.salutation ?? ""));
      setFirstName(String(d.first_name ?? ""));
      setMiddleName(String(d.middle_name ?? ""));
      setLastName(String(d.last_name ?? ""));
      setDisplayName(String(d.display_name ?? ""));
      setNationality(String(d.nationality ?? "Indian"));
      setPlaceOfBirth(String(d.place_of_birth ?? ""));
      setEmail(String(d.email ?? ""));
      setPhone(String(d.phone ?? ""));
      setIdentityExtras(x => ({ ...x, ...(d as Partial<IdentityExtras>) }));
      const savedContacts = d.emergency_contacts as EmergencyContactEntry[] | undefined;
      if (savedContacts && savedContacts.length > 0) setEmergencyContacts(savedContacts);
      setAddressExtras(x => ({ ...x, ...(d as Partial<AddressExtras>) }));
      setForm(f => ({ ...f, ...(d as Partial<ProfileForm>) }));
      setEmployment(e => ({ ...e, ...(d as Partial<EmploymentDraft>), employment_type: data.employment_type }));
      setBasicPay(b => ({ ...b, ...(d as Partial<BasicPayDraft>) }));
      setStatutory(s => ({ ...s, ...(d as Partial<StatutoryDraft>) }));
      setFamilyEntries((d.family_entries as FamilyEntry[]) ?? []);
      setNomineeEntries((d.nominee_entries as NomineeEntry[]) ?? []);
      setEducationEntries((d.education_entries as EducationEntry[]) ?? []);
      setExperienceEntries((d.experience_entries as ExperienceEntry[]) ?? []);
      setAssetEntries((d.asset_entries as AssetEntry[]) ?? []);
      setSelectedDocs(new Set((d.selected_doc_keys as string[]) ?? []));
      setVerification(v => ({ ...v, ...(d as Partial<VerificationDraft>) }));
    }).finally(() => setLoading(false));
  }, [hireActionId]);

  // Father's/mother's name in step 1 are read-only ("FROM FAMILY") — they
  // mirror whatever Father/Mother entries exist in step 4's family list,
  // the same source of truth EPF Form 2 needs, rather than being typed twice.
  useEffect(() => {
    const father = familyEntries.find(f => f.relationship === "father");
    const mother = familyEntries.find(f => f.relationship === "mother");
    if (father && father.name !== form.father_name) setForm(f => ({ ...f, father_name: father.name }));
    if (mother && mother.name !== identityExtras.mother_name) setIdentityExtras(x => ({ ...x, mother_name: mother.name }));
  }, [familyEntries]); // eslint-disable-line react-hooks/exhaustive-deps

  // EmployeeProfile only has one emergency-contact slot — whichever card is
  // marked Primary is what's actually applied at Stage 2, kept in sync here
  // so the existing form.emergency_* -> _PROFILE_FIELDS mapping still works.
  useEffect(() => {
    const primary = emergencyContacts.find(c => c.is_primary) ?? emergencyContacts[0];
    if (!primary) return;
    setForm(f => (
      f.emergency_name === primary.name && f.emergency_relationship === primary.relationship &&
      f.emergency_phone === primary.phone && f.emergency_email === primary.email
        ? f
        : { ...f, emergency_name: primary.name, emergency_relationship: primary.relationship, emergency_phone: primary.phone, emergency_email: primary.email }
    ));
  }, [emergencyContacts]);

  function addEmergencyContact() {
    setEmergencyContacts(p => [...p, emptyEmergencyContact(nextTempId(), p.length === 0)]);
  }
  function updateEmergencyContact(id: string, field: keyof EmergencyContactEntry, value: string | boolean) {
    setEmergencyContacts(p => p.map(c => c.id === id ? { ...c, [field]: value } : c));
  }
  function removeEmergencyContact(id: string) {
    setEmergencyContacts(p => {
      const next = p.filter(c => c.id !== id);
      if (next.length > 0 && !next.some(c => c.is_primary)) next[0].is_primary = true;
      return next;
    });
  }
  function setPrimaryEmergencyContact(id: string) {
    setEmergencyContacts(p => p.map(c => ({ ...c, is_primary: c.id === id })));
  }

  async function patchAction(payload: Record<string, unknown>) {
    const { data } = await clientApi.patch<{ data: HireActionData }>(API.hireActions.detail(hireActionId), payload);
    setAction(data.data);
    return data.data;
  }

  async function setEmploymentType(type: string) {
    if (action?.employment_type) return; // locked once set
    try {
      await patchAction({ employment_type: type });
      setEmployment(e => ({ ...e, employment_type: type }));
    } catch (e) {
      setStepErr((e as { message?: string })?.message || "Could not set employment type.");
    }
  }

  // Applies whichever checkboxes the user kept selected in the Scan & fill
  // modal — every value here came from a real regex match against text
  // genuinely extracted from the uploaded document (see
  // apps.accounts.views_hire_scan._extract_fields), never invented.
  function applyScanSuggestions(picked: ScanSuggestions) {
    if (picked.full_name) {
      const parts = picked.full_name.trim().split(/\s+/);
      setFirstName(parts[0] ?? "");
      setLastName(parts.slice(1).join(" "));
    }
    if (picked.email) setEmail(picked.email);
    if (picked.phone) setPhone(picked.phone);
    if (picked.date_of_birth) setForm(f => ({ ...f, date_of_birth: picked.date_of_birth! }));
    if (picked.current_pin_code) setForm(f => ({ ...f, current_pin_code: picked.current_pin_code! }));
    if (picked.pan_number) setStatutory(s => ({ ...s, pan_number: picked.pan_number! }));
    if (picked.aadhaar_number) setStatutory(s => ({ ...s, aadhaar_number: picked.aadhaar_number! }));
  }

  function validateCurrentStep(): string | null {
    switch (tab) {
      case 0:
        if (!firstName.trim() || !lastName.trim()) return "First name and last name are required.";
        if (!email.trim()) return "Email is required.";
        return null;
      case 1:
        if (!employment.employment_type) return "Select an employment type.";
        if (!employment.role) return "Select a role.";
        if (!employment.branch) return "Select a company code.";
        return null;
      case 3:
        if (!statutory.pan_number.trim() || !statutory.aadhaar_number.trim()) return "PAN and Aadhaar are required.";
        return null;
      default:
        return null;
    }
  }

  async function handleNext() {
    const err = validateCurrentStep();
    if (err) { setStepErr(err); return; }
    setStepErr("");
    try {
      await patchAction({
        salutation, first_name: firstName, middle_name: middleName, last_name: lastName,
        display_name: displayName, nationality, place_of_birth: placeOfBirth, email, phone,
        ...identityExtras,
        ...addressExtras,
        ...form,
        role: employment.role, branch: employment.branch, work_email: employment.work_email,
        reporting_manager_id: employment.reporting_manager_id, dotted_line_manager_id: employment.dotted_line_manager_id,
        work_location: employment.work_location, work_mode: employment.work_mode,
        probation_period_months: employment.probation_period_months, notice_period_days: employment.notice_period_days,
        weekly_off_policy: employment.weekly_off_policy, working_hours_policy: employment.working_hours_policy,
        salary_structure: employment.salary_structure, annual_ctc: employment.annual_ctc,
        pay_group: employment.pay_group, attendance_scheme: employment.attendance_scheme, leave_plan: employment.leave_plan,
        tax_regime: basicPay.tax_regime, payment_method: basicPay.payment_method,
        ...statutory,
        emergency_contacts: emergencyContacts,
        family_entries: familyEntries, nominee_entries: nomineeEntries,
        education_entries: educationEntries, experience_entries: experienceEntries,
        asset_entries: assetEntries, selected_doc_keys: Array.from(selectedDocs),
        ...verification,
      });
      setHighestSaved(h => Math.max(h, tab));
      setTab(t => Math.min(t + 1, STEPS.length - 1));
    } catch (e) {
      setStepErr((e as { message?: string })?.message || "Could not save this step.");
    }
  }

  async function handleHire() {
    setHiring(true);
    setHireError(null);
    try {
      await clientApi.post(API.hireActions.complete(hireActionId));
      onHired();
    } catch (e) {
      setHireError((e as { message?: string })?.message || "Could not hire this employee.");
    } finally {
      setHiring(false);
    }
  }

  const missingByStep = useMemo(() => {
    const m: Record<number, string[]> = {};
    m[0] = [!firstName.trim() && "First name", !lastName.trim() && "Last name", !form.date_of_birth && "Date of birth"].filter(Boolean) as string[];
    m[1] = [!employment.employment_type && "Employment type", !employment.role && "Reporting manager"].filter(Boolean) as string[];
    return m;
  }, [firstName, lastName, form.date_of_birth, employment.employment_type, employment.role]);

  if (loading || !action) {
    return (
      <Modal title="Hire an employee" onClose={onClose}>
        <div style={{ padding: 40, textAlign: "center", color: loading ? "var(--on-variant)" : "var(--error)" }}>
          {loading ? "Loading…" : "Hire action not found."}
        </div>
      </Modal>
    );
  }

  const progressPct = Math.round(((highestSaved + 1) / STEPS.length) * 100);

  return (
    <>
    <Modal
      title={
        <div>
          <div className="text-[18px] font-bold">
            Hire an <span style={{ color: "var(--primary)", fontStyle: "italic" }}>employee</span>
          </div>
          <div className="text-[12px] mt-0.5" style={{ color: "var(--on-variant)", fontWeight: 400 }}>
            Hire · {action.reason_display} · effective {action.effective_from} · {action.position_title}. Employee number is reserved once employment type is set.
          </div>
        </div>
      }
      onClose={onClose}
      size="lg"
      maxWidth={1100}
      scrollBody
      footer={tab < 8 ? (
        <div className="flex items-center gap-4 w-full">
          <div className="flex-1">
            <div className="h-1.5 rounded-full" style={{ background: "var(--outline-v)" }}>
              <div className="h-1.5 rounded-full" style={{ width: `${progressPct}%`, background: "var(--primary)" }} />
            </div>
            <div className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>{progressPct}% complete</div>
          </div>
          <button onClick={onClose} className="btn btn-ghost">Discard</button>
          <button onClick={() => patchAction({}).catch(() => {})} className="btn btn-ghost">Save draft</button>
          <button onClick={() => setShowScanFill(true)} className="btn btn-ghost">Scan &amp; fill</button>
          {tab > 0 && <button onClick={() => setTab(t => Math.max(0, t - 1))} className="btn btn-ghost">Back</button>}
          <button onClick={handleNext} className="btn btn-filled">Next →</button>
        </div>
      ) : (
        <button onClick={onClose} className="btn btn-ghost">Close</button>
      )}
    >
      <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
        <HireWizardSidebar steps={STEPS} currentStep={tab} highestSaved={highestSaved}
          onStepClick={i => { if (i <= highestSaved + 1) setTab(i); }} missingByStep={missingByStep} />

        <div className="wiz-main" style={{ flex: 1, minWidth: 0 }}>
          <div className="stephead" style={{ padding: 0, marginBottom: 12 }}>
            <div>
              <h3>{STEPS[tab].label.split(" ").slice(0, -1).join(" ")} <em className="hl">{STEPS[tab].label.split(" ").slice(-1)}</em></h3>
              <p>{STEPS[tab].sub}</p>
            </div>
            <div className="stepcount">{String(tab + 1).padStart(2, "0")} / {String(STEPS.length).padStart(2, "0")}</div>
          </div>
          {stepErr && (
            <div className="flex items-start gap-2 px-3.5 py-2.5 rounded-lg border border-[var(--error-c)] mb-4"
              style={{ background: "var(--error-c)", color: "var(--error)" }}>
              <i className="ti ti-alert-circle text-[14px] mt-0.5 flex-shrink-0" />
              <span className="text-[13px]">{stepErr}</span>
            </div>
          )}

          {tab === 0 && (
            <div className="mstep on">
              <EmployeePhotoUpload hireActionId={hireActionId} photoUrl={photoUrl} onPhotoChange={setPhotoUrl} />

              <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Identity</div>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Salutation <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>optional</span></label>
                  <select value={salutation} onChange={e => setSalutation(e.target.value)} className="field-input field-select">
                    <option value="">Select</option>
                    {["Mr.", "Ms.", "Mrs.", "Dr."].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">First name <span style={{ color: "var(--error)" }}>*</span></label>
                  <input value={firstName} onChange={e => setFirstName(e.target.value)} placeholder="e.g. Rahul" className="field-input" />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Middle name <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>optional</span></label>
                  <input value={middleName} onChange={e => setMiddleName(e.target.value)} placeholder="e.g. Kumar" className="field-input" />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 mb-5">
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Last name <span style={{ color: "var(--error)" }}>*</span></label>
                  <input value={lastName} onChange={e => setLastName(e.target.value)} placeholder="e.g. Sharma" className="field-input" />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Display name <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>auto</span></label>
                  <div className="flex gap-2">
                    <input value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder="Generated from name" className="field-input" />
                    <button type="button" onClick={() => setDisplayName([salutation, firstName, middleName, lastName].filter(Boolean).join(" "))}
                      className="btn btn-ghost btn-sm" style={{ whiteSpace: "nowrap" }}>+ Suggest</button>
                  </div>
                  <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Shown across the app and in approvals.</p>
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Employee number <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>auto</span></label>
                  <div className="field-input" style={{ background: "var(--bg-low)", color: action.reserved_employee_id ? "var(--on-bg)" : "var(--on-variant)" }}>
                    {action.reserved_employee_id || "Assigned on employment type"}
                  </div>
                  <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Each employment type has its own series — set the type in step 2 and the number is reserved here.</p>
                </div>
              </div>

              <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Basic details</div>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Date of birth <span style={{ color: "var(--error)" }}>*</span></label>
                  <input type="date" value={form.date_of_birth} onChange={e => setForm(f => ({ ...f, date_of_birth: e.target.value }))} className="field-input" />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Gender <span style={{ color: "var(--error)" }}>*</span></label>
                  <select value={form.gender} onChange={e => setForm(f => ({ ...f, gender: e.target.value }))} className="field-input field-select">
                    <option value="">Select</option>
                    <option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Blood group <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>optional</span></label>
                  <select value={form.blood_group} onChange={e => setForm(f => ({ ...f, blood_group: e.target.value }))} className="field-input field-select">
                    <option value="">Select</option>
                    {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map(b => <option key={b} value={b}>{b}</option>)}
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 mb-5">
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Marital status</label>
                  <select value={form.marital_status} onChange={e => setForm(f => ({ ...f, marital_status: e.target.value }))} className="field-input field-select">
                    <option value="single">Single</option><option value="married">Married</option>
                  </select>
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Nationality <span style={{ color: "var(--error)" }}>*</span></label>
                  <input value={nationality} onChange={e => setNationality(e.target.value)} className="field-input" />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Place of birth <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>optional</span></label>
                  <div className="flex gap-2">
                    <input value={placeOfBirth} onChange={e => setPlaceOfBirth(e.target.value)} placeholder="City / town" className="field-input" />
                    <button type="button" onClick={() => setPlaceOfBirth(form.current_village || form.current_district)}
                      className="btn btn-ghost btn-sm" style={{ whiteSpace: "nowrap" }}>+ Suggest</button>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 mb-5">
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Father&apos;s name <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>from family</span></label>
                  <div className="field-input" style={{ background: "var(--bg-low)", color: form.father_name ? "var(--on-bg)" : "var(--on-variant)" }}>
                    {form.father_name || "Set in step 4"}
                  </div>
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Mother&apos;s name <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>from family</span></label>
                  <div className="field-input" style={{ background: "var(--bg-low)", color: identityExtras.mother_name ? "var(--on-bg)" : "var(--on-variant)" }}>
                    {identityExtras.mother_name || "Set in step 4"}
                  </div>
                  <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Required on EPF Form 2.</p>
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Languages known <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>optional</span></label>
                  <div className="flex gap-2">
                    <input value={identityExtras.languages_known} onChange={e => setIdentityExtras(x => ({ ...x, languages_known: e.target.value }))}
                      placeholder="e.g. Telugu, Hindi, English" className="field-input" />
                    <button type="button" onClick={() => setIdentityExtras(x => ({ ...x, languages_known: x.languages_known || "Telugu, Hindi, English" }))}
                      className="btn btn-ghost btn-sm" style={{ whiteSpace: "nowrap" }}>+ Suggest</button>
                  </div>
                </div>
              </div>

              <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Statutory declarations</div>
              <div className="grid grid-cols-2 gap-3 mb-5">
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    Specially abled
                    <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: "0.03em", textTransform: "uppercase", color: "var(--warn)", background: "var(--warn-c)", borderRadius: 99, padding: "1px 6px" }}>RPwD</span>
                  </label>
                  <select value={identityExtras.specially_abled} onChange={e => setIdentityExtras(x => ({ ...x, specially_abled: e.target.value }))} className="field-input field-select">
                    <option value="no">No</option><option value="yes">Yes</option>
                  </select>
                  <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Record-keeping obligation under the RPwD Act 2016.</p>
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    International worker
                    <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: "0.03em", textTransform: "uppercase", color: "var(--warn)", background: "var(--warn-c)", borderRadius: 99, padding: "1px 6px" }}>GOI</span>
                  </label>
                  <select value={identityExtras.international_worker} onChange={e => setIdentityExtras(x => ({ ...x, international_worker: e.target.value }))} className="field-input field-select">
                    <option value="no">No</option><option value="yes">Yes</option>
                  </select>
                  <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Mandatory declaration on EPF Form 11.</p>
                </div>
              </div>

              <div className="text-[11px] font-bold uppercase tracking-wide mb-1" style={{ color: "var(--on-variant)" }}>Voluntary self-declaration</div>
              <p className="text-[11.5px] mb-2" style={{ color: "var(--on-variant)" }}>
                Not required of a private employer. Collect only where a government, PSU or aided establishment must report it, or a state incentive scheme requires it. Self-declared, and hidden from reporting managers.
              </p>
              <div className="grid grid-cols-3 gap-3 mb-5">
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Category / community <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>optional</span></label>
                  <select value={identityExtras.category} onChange={e => setIdentityExtras(x => ({ ...x, category: e.target.value }))} className="field-input field-select">
                    <option value="prefer_not_to_say">Prefer not to say</option>
                    <option value="general">General</option>
                    <option value="obc">OBC</option>
                    <option value="sc">SC</option>
                    <option value="st">ST</option>
                    <option value="other">Other</option>
                  </select>
                </div>
              </div>

              <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Contact</div>
              <div className="grid grid-cols-3 gap-3 mb-5">
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Personal email <span style={{ color: "var(--error)" }}>*</span></label>
                  <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@example.com" className="field-input" />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Mobile number <span style={{ color: "var(--error)" }}>*</span></label>
                  <input value={phone} onChange={e => setPhone(e.target.value)} placeholder="+91 90000 00000" className="field-input" />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Alternate mobile <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>optional</span></label>
                  <input value={identityExtras.alternate_mobile} onChange={e => setIdentityExtras(x => ({ ...x, alternate_mobile: e.target.value }))}
                    placeholder="Optional" className="field-input" />
                </div>
              </div>

              <AddressFields
                form={form}
                extras={addressExtras}
                onFieldChange={(k, v) => setForm(f => ({ ...f, [k]: v }))}
                onExtrasChange={(k, v) => setAddressExtras(x => ({ ...x, [k]: v }))}
              />

              <DynamicStepFields
                configs={[...(fieldConfig["0"] ?? []), ...(fieldConfig["3"] ?? [])]
                  .filter(c => c.visible && !EMERGENCY_BUILTIN_KEYS.has(c.field_key) && !ADDRESS_BUILTIN_KEYS.has(c.field_key))}
                form={form} customValues={{}}
                onBuiltinChange={(k, v) => setForm(f => ({ ...f, [k]: v }))}
                onCustomChange={() => {}}
                customFileValues={[]} uploadingFileKey={null} fileUploadError={null}
                onCustomFileUpload={() => {}} onCustomFileDelete={() => {}}
              />

              <EmergencyContactsList
                entries={emergencyContacts}
                onAdd={addEmergencyContact}
                onFieldChange={updateEmergencyContact}
                onRemove={removeEmergencyContact}
                onSetPrimary={setPrimaryEmergencyContact}
              />
            </div>
          )}

          {tab === 1 && (
            <EmploymentStep
              value={employment} onChange={setEmployment} onSetEmploymentType={setEmploymentType}
              employmentTypeLocked={!!action.employment_type}
              positionTitle={action.position_title} orgUnitName={action.org_unit_name} grade={action.grade}
              costCenter=""
            />
          )}

          {tab === 2 && (
            <BasicPayStep annualCtc={employment.annual_ctc} salaryStructureId={employment.salary_structure}
              branchName={employment.branch} value={basicPay} onChange={setBasicPay} />
          )}

          {tab === 3 && <StatutoryAccountsStep value={statutory} onChange={setStatutory} />}

          {tab === 4 && (
            <FamilyNominationStep
              familyEntries={familyEntries} nomineeEntries={nomineeEntries}
              onAddFamily={() => setFamilyEntries(p => [...p, { id: nextTempId(), name: "", relationship: "child", date_of_birth: "", gender: "", blood_group: "", is_dependent: false }])}
              onFamilyFieldChange={(id, field, value) => setFamilyEntries(p => p.map(e => e.id === id ? { ...e, [field]: value } : e))}
              onRemoveFamily={id => setFamilyEntries(p => p.filter(e => e.id !== id))}
              onAddNominee={() => setNomineeEntries(p => [...p, { id: nextTempId(), family_member: "", scheme: "epf_eps", share_percentage: "0" }])}
              onNomineeFieldChange={(id, field, value) => setNomineeEntries(p => p.map(e => e.id === id ? { ...e, [field]: value } : e))}
              onRemoveNominee={id => setNomineeEntries(p => p.filter(e => e.id !== id))}
              error={null}
            />
          )}

          {tab === 5 && (
            <div className="mstep on">
              <EducationChecklist
                entries={educationEntries} fieldConfig={eduExpFieldConfig.education}
                onAdd={() => setEducationEntries(p => [...p, { id: nextTempId(), level: "", custom_level_label: "", institution: "", specialization: "", percentage: "", start_date: "", end_date: "" }])}
                onFieldChange={(id, field, value) => setEducationEntries(p => p.map(e => e.id === id ? { ...e, [field]: value } : e))}
                onRemove={id => setEducationEntries(p => p.filter(e => e.id !== id))}
                error={null}
              />
              <ExperienceList
                totalExperienceYears={null} entries={experienceEntries} fieldConfig={eduExpFieldConfig.experience}
                onAdd={() => setExperienceEntries(p => [...p, { id: nextTempId(), employer_name: "", designation: "", employment_type: "full_time", start_date: "", end_date: "", is_current: false, responsibilities: "", reason_for_leaving: "" }])}
                onFieldChange={(id, field, value) => setExperienceEntries(p => p.map(e => e.id === id ? { ...e, [field]: value } : e))}
                onRemove={id => setExperienceEntries(p => p.filter(e => e.id !== id))}
                error={null}
              />
            </div>
          )}

          {tab === 6 && (
            <DocumentsChecklistStep
              selected={selectedDocs}
              onToggle={key => setSelectedDocs(p => {
                const next = new Set(p);
                if (next.has(key)) next.delete(key); else next.add(key);
                return next;
              })}
              verification={verification} onVerificationChange={setVerification}
            />
          )}

          {tab === 7 && (
            <div className="mstep on">
              <div className="hint" style={{ marginBottom: 12 }}>Optional at hiring time — assets are usually issued on the joining date.</div>
              <AssetsList
                entries={assetEntries}
                onAdd={() => setAssetEntries(p => [...p, { id: nextTempId(), asset_type: "laptop", tag_number: "", condition: "new", issue_when: "later" }])}
                onFieldChange={(id, field, value) => setAssetEntries(p => p.map(e => e.id === id ? { ...e, [field]: value } : e))}
                onRemove={id => setAssetEntries(p => p.filter(e => e.id !== id))}
                error={null}
                showIssueToggle
              />
            </div>
          )}

          {tab === 8 && (
            <ReviewStep
              reservedEmployeeId={action.reserved_employee_id} positionTitle={action.position_title}
              orgUnitName={action.org_unit_name} grade={action.grade} effectiveFrom={action.effective_from}
              firstName={firstName} lastName={lastName} form={form} employment={employment} basicPay={basicPay}
              statutory={statutory} emergencyContactCount={emergencyContacts.length}
              panNumber={statutory.pan_number} aadhaarNumber={statutory.aadhaar_number}
              familyEntries={familyEntries} nomineeEntries={nomineeEntries}
              educationEntries={educationEntries} experienceEntries={experienceEntries} assetEntries={assetEntries}
              uploadedDocTypes={selectedDocs} requiredDocTypes={REQUIRED_DOC_KEYS}
              onHire={handleHire} hiring={hiring} hireError={hireError}
            />
          )}

        </div>
      </div>
    </Modal>

    {showScanFill && (
      <ScanFillModal
        hireActionId={hireActionId}
        onClose={() => setShowScanFill(false)}
        onApply={applyScanSuggestions}
      />
    )}
    </>
  );
}

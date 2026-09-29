"use client";

// The Hire wizard — Stage 2 of the two-stage Hire flow. Reuses the exact
// same prop-driven step components the existing onboarding wizards already
// use (DynamicStepFields/EducationChecklist/ExperienceList/
// FamilyNominationStep/AssetsList), but everything here is saved into the
// HireAction's own draft_data blob (PATCH /hire-actions/<id>/) instead of
// each step's own per-employee REST endpoint — there is no employee row to
// attach those to until "Hire employee" on the Review step actually
// creates one (HireActionCompleteView applies every list here to real rows
// at that point). Steps are free-jump from the sidebar (HR can jump ahead
// to Documents/Review without filling every earlier step first) — same
// pattern as the HR-onboarding wizard, not the self-service wizard's
// sequential step-locking.
import { useEffect, useMemo, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import PhoneInput, { nationalDigitCount, isPlausibleNationalNumber } from "@/components/PhoneInput";
import LanguagesSelect from "@/components/LanguagesSelect";
import CountrySelect from "@/components/CountrySelect";
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
import DocumentsChecklistStep, { REQUIRED_DOC_KEYS, REQUIRED_DOC_LABELS, EMPTY_VERIFICATION, type VerificationDraft, type HireDocument } from "./DocumentsChecklistStep";
import ReviewStep from "./ReviewStep";
import {
  EMPTY_FORM,
  type IdentityExtras,
  EMPTY_IDENTITY_EXTRAS,
  EMERGENCY_BUILTIN_KEYS,
  ADDRESS_BUILTIN_KEYS,
  IDENTITY_STATUTORY_BUILTIN_KEYS,
  emptyEmergencyContact,
  type HireActionData,
  STEPS,
  NAME_RE, EMAIL_RE, PAN_RE, IFSC_RE, MS_PER_YEAR, MIN_HIRE_AGE_YEARS, MAX_PLAUSIBLE_AGE_YEARS,
  MIN_NATIONAL_PHONE_DIGITS, MAX_NATIONAL_PHONE_DIGITS,
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
  const [coreSkills, setCoreSkills] = useState("");
  const [certifications, setCertifications] = useState("");
  const [documents, setDocuments] = useState<HireDocument[]>([]);
  const [docUploading, setDocUploading] = useState<string | null>(null);
  const [docError, setDocError] = useState("");
  const [verification, setVerification] = useState<VerificationDraft>(EMPTY_VERIFICATION);

  async function uploadDocument(documentType: string, file: File, entryRef?: string) {
    setDocUploading(entryRef ? `${documentType}:${entryRef}` : documentType);
    setDocError("");
    try {
      const formData = new FormData();
      formData.append("document_type", documentType);
      if (entryRef) formData.append("entry_ref", entryRef);
      formData.append("file", file, file.name);
      const res = await clientApi.post<{ data: HireDocument }>(
        API.hireActions.documents(hireActionId), formData,
      );
      const saved = res.data.data;
      setDocuments(prev => [
        ...prev.filter(d => !(d.document_type === documentType && (d.entry_ref || "") === (entryRef || ""))),
        saved,
      ]);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setDocError(msg ?? "Failed to upload document.");
    } finally {
      setDocUploading(null);
    }
  }

  async function deleteDocument(doc: HireDocument) {
    if (!window.confirm("Remove this document? You'll need to re-upload it before hiring.")) return;
    setDocError("");
    try {
      await clientApi.delete(API.hireActions.documentDetail(hireActionId, doc.id));
      setDocuments(prev => prev.filter(d => d.id !== doc.id));
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setDocError(msg ?? "Failed to remove document.");
    }
  }

  const [fieldConfig, setFieldConfig] = useState<OnboardingFieldConfigByStep>({});
  const [eduExpFieldConfig, setEduExpFieldConfig] = useState<EducationExperienceFieldConfigResponse>({ education: [], experience: [] });

  const [hiring, setHiring] = useState(false);
  const [hireError, setHireError] = useState<string | null>(null);

  // QA report #37 — the error banner rendered at the top of the step, so
  // if the user had scrolled down while filling a long step (Personal
  // identity is the worst offender), pressing Next showed the error
  // off-screen with no indication anything happened at all.
  const errorRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (stepErr) errorRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [stepErr]);

  // QA report #53 — the previous step's scroll position was still applied
  // to the next one (e.g. landing on step 2 already scrolled to the
  // bottom, wherever step 1 happened to be left).
  const wizBodyRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    wizBodyRef.current?.scrollTo({ top: 0 });
  }, [tab]);

  // "auto" next to Display name promised it would fill itself in — it
  // never did until the user manually clicked "+ Suggest" (QA report #40).
  // Only auto-fills while the user hasn't typed their own override.
  const displayNameTouchedRef = useRef(false);
  useEffect(() => {
    if (displayNameTouchedRef.current) return;
    setDisplayName([salutation, firstName, middleName, lastName].filter(Boolean).join(" "));
  }, [salutation, firstName, middleName, lastName]);

  let tempId = 0;
  const nextTempId = () => `temp-${++tempId}`;

  useEffect(() => {
    Promise.all([
      clientApi.get<{ data: HireActionData }>(API.hireActions.detail(hireActionId)),
      clientApi.get<{ data: OnboardingFieldConfigByStep }>(API.onboarding.fieldConfig),
      clientApi.get<{ data: EducationExperienceFieldConfigResponse }>(API.onboarding.educationExperienceFieldConfig),
      clientApi.get<{ data: HireDocument[] }>(API.hireActions.documents(hireActionId)),
    ]).then(([a, fc, efc, docs]) => {
      const data = a.data.data;
      setAction(data);
      setPhotoUrl(data.photo_url);
      setFieldConfig(fc.data?.data ?? {});
      setEduExpFieldConfig(efc.data?.data ?? { education: [], experience: [] });
      setDocuments(docs.data?.data ?? []);

      const d = data.draft_data || {};
      setSalutation(String(d.salutation ?? ""));
      setFirstName(String(d.first_name ?? ""));
      setMiddleName(String(d.middle_name ?? ""));
      setLastName(String(d.last_name ?? ""));
      const savedDisplayName = String(d.display_name ?? "");
      setDisplayName(savedDisplayName);
      if (savedDisplayName) displayNameTouchedRef.current = true;
      setNationality(String(d.nationality ?? "Indian"));
      setPlaceOfBirth(String(d.place_of_birth ?? ""));
      setEmail(String(d.email ?? ""));
      setPhone(String(d.phone ?? ""));
      setIdentityExtras(x => ({ ...x, ...(d as Partial<IdentityExtras>) }));
      const savedContacts = d.emergency_contacts as EmergencyContactEntry[] | undefined;
      if (savedContacts && savedContacts.length > 0) setEmergencyContacts(savedContacts);
      setAddressExtras(x => ({ ...x, ...(d as Partial<AddressExtras>) }));
      setForm(f => ({ ...f, ...(d as Partial<ProfileForm>) }));
      setEmployment(e => ({
        ...e,
        ...(d as Partial<EmploymentDraft>),
        // Suggest the position's default role only if nothing was saved
        // yet — never overwrite an HR override on a resumed draft.
        role: (d.role as string | undefined) || data.default_role_id || "",
        employment_type: data.employment_type,
      }));
      setBasicPay(b => ({ ...b, ...(d as Partial<BasicPayDraft>) }));
      setStatutory(s => ({ ...s, ...(d as Partial<StatutoryDraft>) }));
      setFamilyEntries((d.family_entries as FamilyEntry[]) ?? []);
      setNomineeEntries((d.nominee_entries as NomineeEntry[]) ?? []);
      setEducationEntries((d.education_entries as EducationEntry[]) ?? []);
      setExperienceEntries((d.experience_entries as ExperienceEntry[]) ?? []);
      setAssetEntries((d.asset_entries as AssetEntry[]) ?? []);
      setCoreSkills(String(d.core_skills ?? ""));
      setCertifications(String(d.certifications ?? ""));
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
    if (action?.employment_type === type) return;
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
      case 0: {
        // Matches the 7 fields step 1's own sidebar badge (STEPS[0].required)
        // already advertises as required: First name, Last name, Date of
        // birth, Gender, Nationality, Personal email, Mobile number.
        if (!firstName.trim()) return "First name is required.";
        if (!NAME_RE.test(firstName.trim())) return "First name can only contain letters, spaces, hyphens and apostrophes.";
        if (!lastName.trim()) return "Last name is required.";
        if (!NAME_RE.test(lastName.trim())) return "Last name can only contain letters, spaces, hyphens and apostrophes.";
        if (middleName.trim() && !NAME_RE.test(middleName.trim())) return "Middle name can only contain letters, spaces, hyphens and apostrophes.";

        if (!form.date_of_birth) return "Date of birth is required.";
        const dob = new Date(form.date_of_birth);
        if (Number.isNaN(dob.getTime())) return "Date of birth is not a valid date.";
        if (dob > new Date()) return "Date of birth cannot be in the future.";
        const ageYears = (Date.now() - dob.getTime()) / MS_PER_YEAR;
        if (ageYears < MIN_HIRE_AGE_YEARS) return `Employee must be at least ${MIN_HIRE_AGE_YEARS} years old.`;
        if (ageYears > MAX_PLAUSIBLE_AGE_YEARS) return "That date of birth doesn't look right — please check it.";

        if (!form.gender) return "Gender is required.";
        if (!nationality.trim()) return "Nationality is required.";

        if (!email.trim()) return "Personal email is required.";
        if (!EMAIL_RE.test(email.trim())) return "Enter a valid email address.";

        if (!phone.trim()) return "Mobile number is required.";
        {
          const digits = nationalDigitCount(phone);
          if (digits < MIN_NATIONAL_PHONE_DIGITS || digits > MAX_NATIONAL_PHONE_DIGITS) return "Enter a valid mobile number.";
          if (!isPlausibleNationalNumber(phone)) return "Enter a valid Indian mobile number — it must start with 6-9.";
        }
        if (identityExtras.alternate_mobile.trim()) {
          const altDigits = nationalDigitCount(identityExtras.alternate_mobile);
          if (altDigits < MIN_NATIONAL_PHONE_DIGITS || altDigits > MAX_NATIONAL_PHONE_DIGITS) {
            return "Enter a valid alternate mobile number, or leave it blank.";
          }
          if (!isPlausibleNationalNumber(identityExtras.alternate_mobile)) {
            return "Enter a valid alternate Indian mobile number — it must start with 6-9.";
          }
        }
        return null;
      }
      case 1:
        if (!employment.employment_type) return "Select an employment type.";
        if (!employment.role) return "Select a role.";
        if (!employment.branch) return "Select a company code.";
        if (employment.work_email.trim() && !EMAIL_RE.test(employment.work_email.trim())) {
          return "Enter a valid work email address.";
        }
        if (employment.annual_ctc.trim() && Number(employment.annual_ctc) <= 0) {
          return "Annual fixed CTC must be greater than zero, or left blank.";
        }
        return null;
      case 4: {
        // Family member DOB — QA report #35: a father with DOB 2030-01-01
        // (in the future) was accepted with no validation at all.
        const badDob = familyEntries.find(f => {
          if (!f.date_of_birth) return false;
          const d = new Date(f.date_of_birth);
          return Number.isNaN(d.getTime()) || d > new Date();
        });
        if (badDob) return `${badDob.name || "A family member"}'s date of birth cannot be in the future.`;

        const totals: Record<string, number> = {};
        for (const n of nomineeEntries) {
          const scheme = n.scheme || "epf_eps";
          totals[scheme] = (totals[scheme] ?? 0) + (Number(n.share_percentage) || 0);
        }
        const over = Object.entries(totals).find(([, total]) => total > 100);
        if (over) return `Nominee shares for ${over[0]} add up to ${over[1]}% — they can't exceed 100%.`;
        return null;
      }
      case 3: {
        // Matches the 5 fields this step's own sidebar badge already
        // advertises as required: PAN, Aadhaar, Account holder name,
        // Account number, IFSC code.
        if (!statutory.pan_number.trim()) return "PAN is required.";
        if (!PAN_RE.test(statutory.pan_number.trim())) return "Enter a valid PAN (format: ABCDE1234F).";
        if (!statutory.aadhaar_number.trim()) return "Aadhaar is required.";
        if (statutory.aadhaar_number.trim().length !== 12) return "Aadhaar must be exactly 12 digits.";
        if (!statutory.account_holder_name.trim()) return "Account holder name is required.";
        if (!NAME_RE.test(statutory.account_holder_name.trim())) return "Account holder name can only contain letters, spaces, hyphens and apostrophes.";
        if (!statutory.account_number.trim()) return "Account number is required.";
        if (statutory.account_number.trim().length < 6) return "Enter a valid account number.";
        if (!statutory.ifsc_code.trim()) return "IFSC code is required.";
        if (!IFSC_RE.test(statutory.ifsc_code.trim())) return "Enter a valid IFSC code (format: HDFC0001234).";
        if (statutory.passport_issue_date && statutory.passport_expiry && statutory.passport_expiry <= statutory.passport_issue_date) {
          return "Passport expiry must be after the issue date.";
        }
        return null;
      }
      case 6: {
        const uploadedTypes = new Set(documents.map(d => d.document_type));
        const missing = REQUIRED_DOC_KEYS.filter(k => !uploadedTypes.has(k));
        if (missing.length > 0) {
          return `Upload the required documents before continuing: ${missing.map(k => REQUIRED_DOC_LABELS[k] ?? k).join(", ")}.`;
        }
        return null;
      }
      default:
        return null;
    }
  }

  // Every field currently held in this wizard's local state — used
  // wherever a save must capture EVERYTHING typed so far, not just the
  // step currently on screen (patchAction() sends exactly the object it's
  // given, no implicit merge with whatever's already in local state). Built
  // as one function so "Next", jumping to another step via the sidebar, and
  // "Save draft" all persist the exact same snapshot instead of drifting
  // out of sync with each other.
  function buildFullDraftPayload() {
    return {
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
      asset_entries: assetEntries,
      core_skills: coreSkills, certifications,
      ...verification,
    };
  }

  // Jumping to another step via the sidebar (HireWizardSidebar's own
  // onStepClick) previously called setTab directly with no save at all —
  // whatever was typed on the step being left silently never reached
  // draft_data, and "Hire employee" at the end used whatever was last
  // actually PATCHed, not what was on screen. Saving here first (same full
  // snapshot "Next" already sends) closes that gap; errors are swallowed
  // rather than blocking navigation, since jumping between steps must never
  // get stuck the way advancing past a required-field gate should.
  async function goToStep(index: number) {
    // A validation error from the step being LEFT must never still be
    // showing on the step being landed on — QA report #38 found a PAN
    // error from Statutory (step 3) still visible after jumping to Family
    // (step 4) or Assets (step 7).
    setStepErr("");
    try {
      await patchAction(buildFullDraftPayload());
    } catch {
      // Best-effort — still navigate even if this particular snapshot
      // failed to validate; the field-level errors surface again next time
      // "Next" is pressed from wherever the user lands.
    }
    setTab(index);
  }

  async function handleNext() {
    const err = validateCurrentStep();
    if (err) { setStepErr(err); return; }
    setStepErr("");
    try {
      await patchAction(buildFullDraftPayload());
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
      // Belt-and-suspenders: whatever's currently in local state gets saved
      // one more time right before completing, in case the last edit
      // happened without going through handleNext/goToStep (e.g. the last
      // real save site missed in some future change to this file).
      await patchAction(buildFullDraftPayload()).catch(() => {});
      await clientApi.post(API.hireActions.complete(hireActionId));
      onHired();
    } catch (e) {
      setHireError((e as { message?: string })?.message || "Could not hire this employee.");
    } finally {
      setHiring(false);
    }
  }

  // Drives BOTH the sidebar's "N fields still required" box AND (as of this
  // fix) the green-checkmark/"done" state itself for every step listed here
  // — re-derived from CURRENT field values on every render, not a one-time
  // "did the user ever pass Next through this step" flag. That distinction
  // is the actual QA-reported bug (#33): highestSaved only ever increases,
  // so a step validated-and-passed once, then edited back to blank
  // afterward (e.g. clearing PAN/Aadhaar after initially filling them),
  // kept showing a green check and counting toward the progress % forever.
  // Steps not listed here (Basic Pay, Assets — genuinely no required
  // fields) fall back to the old highestSaved-based "done" in the sidebar.
  const missingByStep = useMemo(() => {
    const m: Record<number, string[]> = {};
    // All 7 fields the step's own sidebar badge (STEPS[0].required) has
    // always claimed as required — QA report #36 found the badge itself
    // never actually reflected these (it was a static "7" from _wizardData
    // that never changed no matter what was filled in).
    m[0] = [
      !firstName.trim() && "First name", !lastName.trim() && "Last name",
      !form.date_of_birth && "Date of birth", !form.gender && "Gender",
      !nationality.trim() && "Nationality", !email.trim() && "Personal email",
      !phone.trim() && "Mobile number",
    ].filter(Boolean) as string[];
    m[1] = [
      !employment.employment_type && "Employment type", !employment.role && "Role",
      !employment.branch && "Company code",
    ].filter(Boolean) as string[];
    m[3] = [
      !statutory.pan_number.trim() && "PAN",
      !statutory.aadhaar_number.trim() && "Aadhaar",
      !statutory.account_holder_name.trim() && "Account holder name",
      !statutory.account_number.trim() && "Account number",
      !statutory.ifsc_code.trim() && "IFSC code",
    ].filter(Boolean) as string[];
    m[5] = educationEntries.some(e => e.institution?.trim()) ? [] : ["At least one education entry"];
    m[6] = (() => {
      const uploadedTypes = new Set(documents.map(d => d.document_type));
      return REQUIRED_DOC_KEYS.filter(k => !uploadedTypes.has(k)).map(k => REQUIRED_DOC_LABELS[k] ?? k);
    })();
    return m;
  }, [
    firstName, lastName, form.date_of_birth, form.gender, nationality, email, phone,
    employment.employment_type, employment.role, employment.branch,
    statutory.pan_number, statutory.aadhaar_number, statutory.account_holder_name,
    statutory.account_number, statutory.ifsc_code, educationEntries, documents,
  ]);

  if (loading || !action) {
    return (
      <Modal title="Hire an employee" onClose={onClose}>
        <div style={{ padding: 40, textAlign: "center", color: loading ? "var(--on-variant)" : "var(--error)" }}>
          {loading ? "Loading…" : "Hire action not found."}
        </div>
      </Modal>
    );
  }

  // Same "re-derive from current field values where tracked, else fall back
  // to the historical highestSaved flag" rule HireWizardSidebar's own
  // checkmarks use — kept in sync so the top progress bar and the sidebar
  // never disagree about which steps actually count as done.
  const doneStepCount = STEPS.reduce((count, _step, i) => {
    const isDone = missingByStep[i] !== undefined ? missingByStep[i].length === 0 : i <= highestSaved;
    return count + (isDone ? 1 : 0);
  }, 0);
  const progressPct = Math.round((doneStepCount / STEPS.length) * 100);

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
      // The sidebar (step list) and the step content each scroll
      // independently within this bounded modal — see .wiz/.wiz-nav/.wiz-body
      // in aira-theme.css. Without this override, scrollBody's default
      // makes modal-body itself the one shared scroll container, dragging
      // the step list along with the content instead of leaving it in place.
      bodyStyle={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}
      footer={tab < 8 ? (
        <div className="flex items-center gap-4 w-full">
          <div className="flex-1">
            <div className="h-1.5 rounded-full" style={{ background: "var(--outline-v)" }}>
              <div className="h-1.5 rounded-full" style={{ width: `${progressPct}%`, background: "var(--primary)" }} />
            </div>
            <div className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>{progressPct}% complete</div>
          </div>
          <button onClick={onClose} className="btn btn-ghost">Discard</button>
          <button onClick={() => patchAction(buildFullDraftPayload()).catch(() => {})} className="btn btn-ghost">Save draft</button>
          <button onClick={() => setShowScanFill(true)} className="btn btn-ghost">Scan &amp; fill</button>
          {tab > 0 && <button onClick={() => goToStep(Math.max(0, tab - 1))} className="btn btn-ghost">Back</button>}
          <button onClick={handleNext} className="btn btn-filled">Next →</button>
        </div>
      ) : (
        <button onClick={onClose} className="btn btn-ghost">Close</button>
      )}
    >
      <div className="wiz">
        <HireWizardSidebar steps={STEPS} currentStep={tab} highestSaved={highestSaved}
          onStepClick={goToStep} missingByStep={missingByStep} />

        <div className="wiz-main">
          <div className="stephead" style={{ padding: "20px 24px 0" }}>
            <div>
              <h3>{STEPS[tab].label.split(" ").slice(0, -1).join(" ")} <em className="hl">{STEPS[tab].label.split(" ").slice(-1)}</em></h3>
              <p>{STEPS[tab].sub}</p>
            </div>
            <div className="stepcount">{String(tab + 1).padStart(2, "0")} / {String(STEPS.length).padStart(2, "0")}</div>
          </div>

        <div className="wiz-body" ref={wizBodyRef}>
          {stepErr && (
            <div ref={errorRef} className="flex items-start gap-2 px-3.5 py-2.5 rounded-lg border border-[var(--error-c)] mb-4"
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
                    <input value={displayName} onChange={e => { displayNameTouchedRef.current = true; setDisplayName(e.target.value); }} placeholder="Generated from name" className="field-input" />
                    <button type="button" onClick={() => { displayNameTouchedRef.current = false; setDisplayName([salutation, firstName, middleName, lastName].filter(Boolean).join(" ")); }}
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
                  <CountrySelect value={nationality} onChange={setNationality} mode="demonym" />
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
                  <LanguagesSelect value={identityExtras.languages_known}
                    onChange={v => setIdentityExtras(x => ({ ...x, languages_known: v }))} />
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
                  <PhoneInput value={phone} onChange={setPhone} placeholder="90000 00000" />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Alternate mobile <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>optional</span></label>
                  <PhoneInput value={identityExtras.alternate_mobile}
                    onChange={v => setIdentityExtras(x => ({ ...x, alternate_mobile: v }))}
                    placeholder="Optional" />
                </div>
              </div>

              <AddressFields
                form={form}
                extras={addressExtras}
                onFieldChange={(k, v) => setForm(f => ({ ...f, [k]: v }))}
                onExtrasChange={(k, v) => setAddressExtras(x => ({ ...x, [k]: v }))}
              />

              {/* Custom (is_custom) fields are excluded below — customValues/
                  onCustomChange are permanent no-op stubs here (this wizard
                  saves into HireAction.draft_data, which has no schema for
                  arbitrary custom fields yet), so a custom field rendered
                  here would silently discard whatever HR typed into it.
                  Showing an input that never saves is worse than not
                  showing it. */}
              <DynamicStepFields
                configs={[...(fieldConfig["0"] ?? []), ...(fieldConfig["3"] ?? [])]
                  .filter(c =>
                    c.visible && !c.is_custom
                    && !EMERGENCY_BUILTIN_KEYS.has(c.field_key)
                    && !ADDRESS_BUILTIN_KEYS.has(c.field_key)
                    && !IDENTITY_STATUTORY_BUILTIN_KEYS.has(c.field_key))}
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
              reservedEmployeeId={action.reserved_employee_id}
              positionTitle={action.position_title} orgUnitName={action.org_unit_name} grade={action.grade}
              costCenter=""
              defaultRoleId={action.default_role_id} defaultRoleName={action.default_role_name}
            />
          )}

          {tab === 2 && (
            <BasicPayStep annualCtc={employment.annual_ctc} salaryStructureId={employment.salary_structure}
              branchName={employment.branch} value={basicPay} onChange={setBasicPay} />
          )}

          {tab === 3 && (
            <StatutoryAccountsStep
              value={statutory} onChange={setStatutory}
              documents={documents} uploading={docUploading} docError={docError}
              onUploadDoc={uploadDocument} onDeleteDoc={deleteDocument}
            />
          )}

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
                onAdd={() => setEducationEntries(p => [...p, { id: nextTempId(), level: "", custom_level_label: "", institution: "", specialization: "", percentage: "", start_date: "", end_date: "", is_highest: false }])}
                onFieldChange={(id, field, value) => setEducationEntries(p => p.map(e => e.id === id ? { ...e, [field]: value } : e))}
                onRemove={id => setEducationEntries(p => p.filter(e => e.id !== id))}
                onSetHighest={id => setEducationEntries(p => p.map(e => ({ ...e, is_highest: e.id === id })))}
                documents={documents} uploading={docUploading} onUploadDoc={uploadDocument} onDeleteDoc={deleteDocument}
                error={null}
              />
              <ExperienceList
                totalExperienceYears={null} entries={experienceEntries} fieldConfig={eduExpFieldConfig.experience}
                onAdd={() => setExperienceEntries(p => [...p, { id: nextTempId(), employer_name: "", designation: "", employment_type: "full_time", start_date: "", end_date: "", is_current: false, responsibilities: "", reason_for_leaving: "" }])}
                onFieldChange={(id, field, value) => setExperienceEntries(p => p.map(e => e.id === id ? { ...e, [field]: value } : e))}
                onRemove={id => setExperienceEntries(p => p.filter(e => e.id !== id))}
                documents={documents} uploading={docUploading} onUploadDoc={uploadDocument} onDeleteDoc={deleteDocument}
                error={null}
              />

              <div className="divider" />
              <div className="sechead">SKILLS &amp; CERTIFICATIONS</div>
              <div className="g3">
                <div className="f">
                  <label>Core skills <span className="tag">OPTIONAL</span></label>
                  <input value={coreSkills} onChange={e => setCoreSkills(e.target.value)} placeholder="e.g. React, payroll operations, team leadership" className="finput" />
                  <div className="hint">Use comma-separated skills; keep this relevant to the role.</div>
                </div>
                <div className="f">
                  <label>Certifications <span className="tag">OPTIONAL</span></label>
                  <input value={certifications} onChange={e => setCertifications(e.target.value)} placeholder="Certification and year" className="finput" />
                </div>
              </div>
            </div>
          )}

          {tab === 6 && (
            <DocumentsChecklistStep
              documents={documents}
              uploading={docUploading}
              error={docError}
              onUpload={uploadDocument}
              onDelete={deleteDocument}
              verification={verification} onVerificationChange={setVerification}
              hasExperienceEntries={experienceEntries.length > 0}
            />
          )}

          {tab === 7 && (
            <div className="mstep on">
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
              statutory={statutory}
              // The wizard always starts with one blank placeholder row —
              // counting it as "1 emergency contact added" before the user
              // typed anything into it was QA report #50's "1 emergency
              // contact shown when none added".
              emergencyContactCount={emergencyContacts.filter(c => c.name.trim() && c.phone.trim()).length}
              panNumber={statutory.pan_number} aadhaarNumber={statutory.aadhaar_number}
              familyEntries={familyEntries} nomineeEntries={nomineeEntries}
              educationEntries={educationEntries} experienceEntries={experienceEntries} assetEntries={assetEntries}
              uploadedDocTypes={new Set(documents.map(d => d.document_type))} requiredDocTypes={REQUIRED_DOC_KEYS}
              onHire={handleHire} hiring={hiring} hireError={hireError}
            />
          )}

        </div>
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

"use client";

// ── "Edit full record" modal ──────────────────────────────────────────────
// Reuses the Hire Wizard's own visual shell AND, wherever a post-hire data
// path exists, its ACTUAL step components — not a reconstruction with
// different fields. Per explicit feedback: this must show the same UI and
// the same fields as Hire an employee, not an ad-hoc subset.
//
//   Step                     Component (same file Hire uses)      Bound to
//   ───────────────────────  ────────────────────────────────────  ─────────────────────────────
//   0 Personal identity      (inline — Hire has no separate file   existing employee fields
//                             for this step either; same field set,
//                             order and labels reconstructed here)
//                            + EmergencyContactsList (real import)  legacy single emergency_* fields,
//                                                                   shown as one list entry
//   1 Employment             EmploymentStep (real import)           User fields (branch/reporting
//                                                                   lines/work setup) — see note below
//                                                                   on fields with no write path yet
//   2 Basic pay              BasicPayStep (real import)              computed live via the real
//                                                                   estimate_salary_breakdown() preview
//                                                                   endpoint (API.payroll.salaryPreview),
//                                                                   same as Hire — see note below on saving
//   3 Statutory & accounts   StatutoryAccountsStep (real import)    EmployeeProfile (PAN/Aadhaar/PF/ESI/bank)
//   4 Family & nomination    FamilyNominationStep (real import)     /onboarding/employees/<uuid>/family,nominees
//   5 Education & experience EducationChecklist + ExperienceList    /onboarding/employees/<uuid>/education,experience
//                            (real imports, same as the self-service
//                             and HR-onboarding wizards use)
//   6 Documents               DocumentsChecklistStep (real import)  existing employee documents endpoint
//   7 Assets                 AssetsList (real import)               /onboarding/employees/<uuid>/assets
//
// Note on Basic pay: BasicPayStep itself only ever displays a live PREVIEW
// breakdown (it calls estimate_salary_breakdown(), not the real payroll
// engine) — it has no save endpoint of its own in either Hire or here.
// employment.annual_ctc/salary_structure are seeded from this employee's
// current active EmployeeSalaryConfig (the same history
// API.payroll.employeeSalaryHistory(uuid) the full Salary tab reads) and,
// on Save changes, a new EmployeeSalaryConfig revision is POSTed via
// API.payroll.employeeSalary — the SAME write path the full Salary tab
// uses — but ONLY when the CTC/structure actually changed from what was
// loaded, so opening this section without editing it never creates a
// spurious revision row (see the save handler below for the exact check).
//
// Note on Employment: EmploymentStep itself fetches its own dropdown data
// (positions/people/policies) — passed through here unchanged. Some
// of its fields map to real, now-writable User columns (branch,
// reporting_manager_id, dotted_line_manager_id, work_location, work_mode,
// probation_period_months, notice_period_days — see the backend
// employees_detail.py whitelist extension that went with this change).
// Others (weekly_off_policy, working_hours_policy/shift, salary_structure,
// annual_ctc, pay_group, attendance_scheme) have NO post-hire
// write path anywhere in this codebase yet — they render (same UI, same
// fields, matching the explicit request) but are NOT sent on save; this is
// stated in-code at the save call, not silently dropped without a trace.

import { matchEmploymentType } from "@/lib/employmentType";
import { parseApiError } from "@/lib/apiError";
import { MARITAL_STATUS_OPTIONS } from "@/lib/maritalStatus";
import { usePermission } from "@/hooks/usePermission";
import EditRecordContactFields from "./EditRecordContactFields";
import { buildContactChanges } from "./editRecordContact";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import PhoneInput from "@/components/PhoneInput";
import CountrySelect from "@/components/CountrySelect";
import LanguagesSelect from "@/components/LanguagesSelect";
import type { HireDocument } from "@/components/DocUploadButton";
import type { DetailValues, Employee } from "../_data";
import Avatar from "./Avatar";
import { apiToEmployee, type ApiEmployee } from "../[id]/_apiMapping";
import BasicPayStep, { EMPTY_BASIC_PAY, type BasicPayDraft } from "../../hire/[hireActionId]/_components/BasicPayStep";
import { STEPS as HIRE_STEPS } from "../../hire/[hireActionId]/_components/_wizardData";
import StatutoryAccountsStep, { EMPTY_STATUTORY, type StatutoryDraft } from "../../hire/[hireActionId]/_components/StatutoryAccountsStep";
import { EMPTY_EMPLOYMENT, type EmploymentDraft } from "../../hire/[hireActionId]/_components/EmploymentStep";
import EditRecordEmploymentStep from "./EditRecordEmploymentStep";
import DocumentsChecklistStep, { EMPTY_VERIFICATION, type VerificationDraft } from "../../hire/[hireActionId]/_components/DocumentsChecklistStep";
import EmergencyContactsList, { type EmergencyContactEntry } from "../../hire/[hireActionId]/_components/EmergencyContactsList";
import AddressFields, { EMPTY_ADDRESS_EXTRAS, type AddressExtras, type AddressFormFields } from "../../hire/[hireActionId]/_components/AddressFields";
import { type FamilyEntry, type NomineeEntry } from "@/app/onboarding/_components/FamilyNominationStep";
import AssetsList, { type AssetEntry } from "@/app/onboarding/_components/AssetsList";
import EducationChecklist, { type EducationEntry } from "@/app/onboarding/_components/EducationChecklist";
import ExperienceList, { type ExperienceEntry } from "@/app/onboarding/_components/ExperienceList";
import { todayDateString } from "@/lib/candidateValidation";
import type { EducationExperienceFieldConfigResponse } from "@/types/onboardingFieldConfig";
import type { EmployeeSalaryConfig } from "@/types/payroll";

const STEPS = HIRE_STEPS.slice(0, -1); // drop "Review" — not applicable to editing an existing record

// AddressFields speaks snake_case (ProfileForm's own key names); `values`
// (DetailValues) is keyed camelCase. Inverse of _data.ts's own internal
// CAMEL_TO_SNAKE map, scoped to just the address fields AddressFields uses.
const ADDRESS_FIELD_TO_CAMEL: Record<keyof AddressFormFields, string> = {
  current_address: "currentAddress", current_address_line2: "currentAddressLine2",
  current_village: "currentVillage", current_district: "currentDistrict",
  current_state: "currentState", current_pin_code: "currentPinCode",
  permanent_address: "permanentAddress", permanent_address_line2: "permanentAddressLine2",
  permanent_village: "permanentVillage", permanent_district: "permanentDistrict",
  permanent_state: "permanentState", permanent_pin_code: "permanentPinCode",
  permanent_same_as_current: "permanentSameAsCurrent",
};

// Same backend-accepted values as the real FamilyNominationStep
// (app/onboarding/_components/FamilyNominationStep.tsx) — only this
// section's layout/card styling/Guardian block differ from that
// component, per explicit reference-image feedback; the underlying data
// contract (codes sent to /onboarding/employees/<uuid>/family,nominees)
// is unchanged.
const FAMILY_RELATIONSHIPS = ["father", "mother", "spouse", "child", "sibling"];
const FAMILY_RELATIONSHIP_LABELS: Record<string, string> = {
  father: "Father", mother: "Mother", spouse: "Spouse", child: "Child", sibling: "Sibling",
};
const NOMINATION_SCHEMES = [
  { value: "epf_eps", label: "EPF + EPS" }, { value: "gratuity", label: "Gratuity" }, { value: "both", label: "Both" },
];

let tempId = 0;
const nextTempId = () => `temp-${++tempId}`;

function ageFromDateOfBirth(value: string): number | null {
  if (!value) return null;
  const dateOfBirth = new Date(`${value}T00:00:00`);
  if (Number.isNaN(dateOfBirth.getTime())) return null;
  const today = new Date();
  let age = today.getFullYear() - dateOfBirth.getFullYear();
  if (
    today.getMonth() < dateOfBirth.getMonth() ||
    (today.getMonth() === dateOfBirth.getMonth() && today.getDate() < dateOfBirth.getDate())
  ) age -= 1;
  return age >= 0 ? age : null;
}

// Flat section nav for this modal — deliberately NOT HireWizardSidebar.
// That component is built for linear wizard progress (numbered circles,
// a per-step "N fields still required" count badge from each step's
// static STEPS[i].required) — correct for a one-way hire flow, wrong for
// an edit view where every section is already complete and any section
// can be opened in any order. Same label/sub/group/tag data, no numbers,
// no required-count badges.
function EditRecordSidebar({ currentStep, onStepClick, hasMissing }: { currentStep: number; onStepClick: (i: number) => void; hasMissing: boolean }) {
  return (
    <div className="wiz-nav" style={{ overflowY: "visible" }}>
      {STEPS.map((s, i) => (
        <div key={s.label}>
          {s.group && <div className="navgrp">{s.group}</div>}
          <button type="button" onClick={() => onStepClick(i)} className={`step${i === currentStep ? " on" : ""}`} style={{ paddingLeft: 12 }}>
            <div className="tx">
              <div className="t1">
                {s.label}
                {s.tag && <span className={`tag ${s.tag.tone}`}>{s.tag.label}</span>}
              </div>
              <div className="t2">{s.sub}</div>
            </div>
          </button>
        </div>
      ))}

      <div
        className="mt-4 rounded-lg p-3 text-[11.5px]"
        style={hasMissing ? { background: "var(--warn-c)", color: "var(--warn)" } : { background: "var(--ok-bg)", color: "var(--ok)" }}
      >
        <div style={{ fontWeight: 700, marginBottom: 2 }}>{hasMissing ? "A few required fields are empty" : "Nothing outstanding"}</div>
        <div>{hasMissing ? "Fill in the required fields marked with *." : "All required fields are complete. Optional sections can be finished after joining."}</div>
      </div>
    </div>
  );
}

// ── Personal-identity local state — same fields/order/labels as
// HireWizardClient's own step-0 JSX (it has no separate component file to
// import; this reconstructs it field-for-field). Fields with no backend
// column at all (middle name, specially abled, international worker,
// category, address landmark/country) are LOCAL ONLY in this pass —
// rendered for visual/field parity with Hire, but not sent on save (except
// current/permanent address itself, which IS a real field and does save —
// only the landmark/country extras are local-only). Flagged plainly, not
// hidden. (Statutory declarations/Voluntary self-declaration/Address were
// previously tracked in state here but never actually rendered — a real
// gap found and fixed; see the JSX below for all three.)
interface PersonalIdentityDraft {
  salutation: string; firstName: string; middleName: string; lastName: string; displayName: string;
  dateOfBirth: string; gender: string; bloodGroup: string; maritalStatus: string; nationality: string; placeOfBirth: string;
  fatherName: string; motherName: string; languagesKnown: string; speciallyAbled: string; internationalWorker: string; category: string;
  personalEmail: string; mobileNumber: string; alternateMobile: string;
}
const EMPTY_PERSONAL: PersonalIdentityDraft = {
  salutation: "", firstName: "", middleName: "", lastName: "", displayName: "",
  dateOfBirth: "", gender: "", bloodGroup: "", maritalStatus: "single", nationality: "", placeOfBirth: "",
  fatherName: "", motherName: "", languagesKnown: "", speciallyAbled: "no", internationalWorker: "no", category: "prefer_not_to_say",
  personalEmail: "", mobileNumber: "", alternateMobile: "",
};

// ── Local drafts ────────────────────────────────────────────────────────
// Lets HR save in-progress edits without submitting, and come back to them
// later — local-only (localStorage), per employee, no backend model. Note:
// loading a draft that had removed a family/nominee/education/experience/
// asset entry won't re-send the delete for that entry on save (the
// deletedXIds refs that drive those deletes aren't part of the snapshot) —
// acceptable for a "resume my edits" draft, not a full undo history.
interface EditRecordDraftState {
  values: DetailValues;
  addressExtras: AddressExtras;
  personal: PersonalIdentityDraft;
  emergencyContacts: EmergencyContactEntry[];
  guardian: { name: string; relationship: string; address: string };
  accessCard: { cardNumber: string; validFrom: string; validTill: string };
  employment: EmploymentDraft;
  basicPay: BasicPayDraft;
  statutory: StatutoryDraft;
  familyEntries: FamilyEntry[];
  nomineeEntries: NomineeEntry[];
  educationEntries: EducationEntry[];
  experienceEntries: ExperienceEntry[];
  coreSkills: string;
  certifications: string;
  assetEntries: AssetEntry[];
}
interface EditRecordDraft {
  id: string;
  savedAt: string; // ISO
  state: EditRecordDraftState;
}
const MAX_DRAFTS = 10;
const draftsStorageKey = (employeeId: string) => `editRecordDrafts:${employeeId}`;

function loadDrafts(employeeId: string): EditRecordDraft[] {
  try {
    const raw = localStorage.getItem(draftsStorageKey(employeeId));
    return raw ? (JSON.parse(raw) as EditRecordDraft[]) : [];
  } catch {
    return [];
  }
}
function persistDrafts(employeeId: string, drafts: EditRecordDraft[]) {
  try {
    localStorage.setItem(draftsStorageKey(employeeId), JSON.stringify(drafts));
  } catch {
    // Storage unavailable/full — the draft just won't persist, not fatal.
  }
}

export default function EditRecordModal({ employee, onClose }: { employee: Employee; onClose: () => void }) {
  // The shared Modal component doesn't lock body scroll on its own — with
  // tall content (this modal has a lot), the page behind it could also
  // scroll, showing a second scrollbar at the viewport edge alongside the
  // modal's own internal one. Lock it while this modal is mounted.
  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = previousOverflow; };
  }, []);

  useEffect(() => () => { if (draftSavedTimer.current) clearTimeout(draftSavedTimer.current); }, []);

  const [uuid, setUuid] = useState("");
  const [loading, setLoading] = useState(true);
  const [values, setValues] = useState<DetailValues>({});
  // Landmark/country — same as Hire's own addressExtras: no backend column
  // exists for either today (current_address_line2 absorbs landmark; country
  // isn't stored at all), so local-only, same documented gap as Personal
  // identity's speciallyAbled/internationalWorker/category below.
  const [addressExtras, setAddressExtras] = useState<AddressExtras>(EMPTY_ADDRESS_EXTRAS);

  const [personal, setPersonal] = useState<PersonalIdentityDraft>(EMPTY_PERSONAL);
  // HR (employees.edit) may correct the mobile and personal/login email; others see them read-only. savedContact is
  // what the server holds, so only a real change is sent, and a login-email change needs the explicit tick.
  const canEditContact = usePermission("employees.edit");
  const [savedContact, setSavedContact] = useState({ email: "", mobile: "" });
  const [savedUanMasked, setSavedUanMasked] = useState("");
  const [isLoginChangeConfirmed, setIsLoginChangeConfirmed] = useState(false);
  const [contactErrors, setContactErrors] = useState<{ email?: string; phone?: string }>({});
  const [emergencyContacts, setEmergencyContacts] = useState<EmergencyContactEntry[]>([]);
  // Guardian (Family & nomination step) — local-only, same as Personal
  // identity's extra fields: no backend column exists for this today, so
  // it's rendered for field parity but not sent on save.
  const [guardian, setGuardian] = useState({ name: "", relationship: "", address: "" });
  // Access card (Assets step) — same local-only situation as Guardian:
  // no CompanyAsset/access-card model or endpoint exists in this codebase
  // today (confirmed by Explore — AssetsList's own real entries are the
  // only persisted part of this step).
  const [accessCard, setAccessCard] = useState({ cardNumber: "", validFrom: "", validTill: "" });

  const [employment, setEmployment] = useState<EmploymentDraft>(EMPTY_EMPLOYMENT);
  const [basicPay, setBasicPay] = useState<BasicPayDraft>(EMPTY_BASIC_PAY);
  // Baseline CTC/structure as loaded — a new EmployeeSalaryConfig revision
  // is only created on save if these actually changed, so opening and
  // closing Basic pay without editing anything never creates a spurious
  // revision row.
  const baselineCtc = useRef({ annualCtc: "", salaryStructure: "" });
  const [positionTitle, setPositionTitle] = useState("");
  // Date of joining is only sent when changed, so saving never trips the backend's post-onboarding lock needlessly.
  const baselineJoiningDate = useRef("");
  const [orgUnitName, setOrgUnitName] = useState("");

  const [statutory, setStatutory] = useState<StatutoryDraft>(EMPTY_STATUTORY);

  const [familyEntries, setFamilyEntries] = useState<FamilyEntry[]>([]);
  const [nomineeEntries, setNomineeEntries] = useState<NomineeEntry[]>([]);
  const [educationEntries, setEducationEntries] = useState<EducationEntry[]>([]);
  const [experienceEntries, setExperienceEntries] = useState<ExperienceEntry[]>([]);
  const [eduExpFieldConfig, setEduExpFieldConfig] = useState<EducationExperienceFieldConfigResponse>({ education: [], experience: [] });
  const [coreSkills, setCoreSkills] = useState("");
  const [certifications, setCertifications] = useState("");
  const [assetEntries, setAssetEntries] = useState<AssetEntry[]>([]);
  const [verification, setVerification] = useState<VerificationDraft>(EMPTY_VERIFICATION);

  const [hireDocs, setHireDocs] = useState<HireDocument[]>([]);
  const [uploadingDocType, setUploadingDocType] = useState<string | null>(null);
  const [docUploadError, setDocUploadError] = useState("");

  const [photoUrl, setPhotoUrl] = useState<string | null | undefined>(employee.photoUrl);
  const [uploadingPhoto, setUploadingPhoto] = useState(false);
  const [photoError, setPhotoError] = useState("");

  async function onUploadPhoto(file: File) {
    setPhotoError("");
    setUploadingPhoto(true);
    try {
      const formData = new FormData();
      formData.append("photo", file);
      const { data } = await clientApi.post<{ data: { profile_photo_url: string | null } }>(
        API.employees.photo(employee.id), formData, { headers: { "Content-Type": "multipart/form-data" } },
      );
      setPhotoUrl(data.data.profile_photo_url ?? undefined);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setPhotoError(msg || "Failed to upload photo. Please try again.");
    } finally {
      setUploadingPhoto(false);
    }
  }

  const [familyErr, setFamilyErr] = useState<string | null>(null);
  const [assetErr, setAssetErr] = useState<string | null>(null);
  const deletedFamilyIds = useRef<Set<string>>(new Set());
  const deletedNomineeIds = useRef<Set<string>>(new Set());
  const deletedAssetIds = useRef<Set<string>>(new Set());
  const deletedEducationIds = useRef<Set<string>>(new Set());
  const deletedExperienceIds = useRef<Set<string>>(new Set());

  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState(false);

  // Dirty-tracking for the close (X) confirmation — baselineRef is captured
  // once all the record's data has finished loading, and again after every
  // successful save, so "unsaved changes?" only fires on edits actually made
  // since the record was last known to match the server.
  const [coreLoaded, setCoreLoaded] = useState(false);
  const [listsLoaded, setListsLoaded] = useState(false);
  const [baselineTick, setBaselineTick] = useState(0);
  const baselineRef = useRef<string | null>(null);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);

  const [showDrafts, setShowDrafts] = useState(false);
  const [drafts, setDrafts] = useState<EditRecordDraft[]>([]);
  const [draftSavedMsg, setDraftSavedMsg] = useState(false);
  const draftSavedTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  function openDrafts() {
    setDrafts(loadDrafts(employee.id));
    setDraftSavedMsg(false);
    setShowDrafts(true);
  }

  function buildSnapshot(): EditRecordDraftState {
    return {
      values, addressExtras, personal, emergencyContacts, guardian, accessCard,
      employment, basicPay, statutory, familyEntries, nomineeEntries,
      educationEntries, experienceEntries, coreSkills, certifications, assetEntries,
    };
  }

  function saveCurrentAsDraft() {
    const draft: EditRecordDraft = { id: nextTempId(), savedAt: new Date().toISOString(), state: buildSnapshot() };
    const next = [draft, ...loadDrafts(employee.id)].slice(0, MAX_DRAFTS);
    persistDrafts(employee.id, next);
    setDrafts(next);
    setDraftSavedMsg(true);
    if (draftSavedTimer.current) clearTimeout(draftSavedTimer.current);
    draftSavedTimer.current = setTimeout(() => setDraftSavedMsg(false), 2500);
  }

  // Always holds this render's buildSnapshot — read from the effect below
  // instead of listing it as a dependency, so the baseline capture only
  // re-runs on coreLoaded/listsLoaded/baselineTick (load complete, or a
  // save just succeeded), never on every keystroke the user makes.
  const buildSnapshotRef = useRef(buildSnapshot);
  useEffect(() => { buildSnapshotRef.current = buildSnapshot; });

  // Captures the "known saved" snapshot once on initial load, and again
  // after baselineTick is bumped by a successful save — see onSaveChanges.
  useEffect(() => {
    if (!coreLoaded || !listsLoaded) return;
    baselineRef.current = JSON.stringify(buildSnapshotRef.current());
  }, [coreLoaded, listsLoaded, baselineTick]);

  function isDirty(): boolean {
    if (!baselineRef.current) return false; // nothing loaded yet to compare against
    return JSON.stringify(buildSnapshot()) !== baselineRef.current;
  }

  function requestClose() {
    if (isDirty()) setShowCloseConfirm(true);
    else onClose();
  }

  function loadDraft(draft: EditRecordDraft) {
    const s = draft.state;
    setValues(s.values);
    setAddressExtras(s.addressExtras);
    setPersonal(s.personal);
    setEmergencyContacts(s.emergencyContacts);
    setGuardian(s.guardian);
    setAccessCard(s.accessCard);
    setEmployment(s.employment);
    setBasicPay(s.basicPay);
    setStatutory(s.statutory);
    setFamilyEntries(s.familyEntries);
    setNomineeEntries(s.nomineeEntries);
    setEducationEntries(s.educationEntries);
    setExperienceEntries(s.experienceEntries);
    setCoreSkills(s.coreSkills);
    setCertifications(s.certifications);
    setAssetEntries(s.assetEntries);
    setShowDrafts(false);
  }

  function deleteDraft(id: string) {
    const next = loadDrafts(employee.id).filter(d => d.id !== id);
    persistDrafts(employee.id, next);
    setDrafts(next);
  }

  const refreshDocs = useCallback((raw: ApiEmployee) => {
    setHireDocs((raw.documents ?? []).map(d => ({
      id: String(d.id), document_type: d.document_type, document_type_display: d.document_type_display,
      entry_ref: "", file_name: d.file_name, file_size: d.file_size, uploaded_at: d.uploaded_at,
      file_url: d.file || undefined,  // the signed link the profile page's Preview uses too
    })));
  }, []);

  useEffect(() => {
    clientApi.get<{ data: ApiEmployee }>(API.employees.detail(employee.id)).then(({ data }) => {
      const raw = data.data;
      const emp = apiToEmployee(raw, []);
      setUuid(raw.uuid);
      setValues(emp.details);
      refreshDocs(raw);

      // Several read-side fields (pf_covered/esi_covered/work_mode/
      // probation_period_months/notice_period_days/dotted_line_manager/
      // core_skills/certifications) aren't declared on the shared
      // ApiEmployee type (that type mirrors what the OLDER edit page's own
      // payload builder sent, which never included them) — the backend's
      // _employee_dict does return them (extended alongside this fix).
      // Read defensively rather than widening the shared type for fields
      // only this modal uses.
      const rawRecord = raw as unknown as Record<string, unknown>;
      const dottedLineManager = rawRecord.dotted_line_manager as { uuid: string | null; name: string | null } | null;

      setPersonal(p => ({
        ...p,
        firstName: emp.firstName ?? "", lastName: emp.lastName ?? "",
        salutation: raw.profile?.salutation ?? "",
        displayName: raw.profile?.display_name || `${emp.firstName ?? ""} ${emp.lastName ?? ""}`.trim(),
        nationality: raw.profile?.nationality ?? "",
        placeOfBirth: raw.profile?.place_of_birth ?? "",
        dateOfBirth: emp.details.dateOfBirth ?? "", gender: emp.details.gender ?? "",
        bloodGroup: emp.details.bloodGroup ?? "", maritalStatus: (emp.details.maritalStatus ?? "single").toLowerCase(),
        fatherName: raw.profile?.father_name ?? "",
        motherName: raw.profile?.mother_name ?? "",
        languagesKnown: raw.profile?.languages_known ?? "",
        personalEmail: emp.email ?? "", mobileNumber: emp.phone ?? "",
      }));
      setSavedContact({ email: emp.email ?? "", mobile: emp.phone ?? "" });
      setSavedUanMasked(raw.profile?.uan_masked ?? "");

      const legacyEmergency: EmergencyContactEntry = {
        id: nextTempId(), name: emp.details.emergencyName ?? "", relationship: emp.details.emergencyRelationship ?? "",
        phone: emp.details.emergencyPhone ?? "", alternate_phone: "", email: emp.details.emergencyEmail ?? "", address: "",
        is_primary: true,
      };
      setEmergencyContacts(legacyEmergency.name ? [legacyEmergency] : []);

      setEmployment(e => ({
        ...e,
        employment_type: typeof rawRecord.employee_type === "string" ? matchEmploymentType(rawRecord.employee_type) : "",
        date_of_joining: emp.details.dateOfJoining ?? "",
        work_email: emp.email ?? "",
        branch: emp.details.branch ?? "",
        reporting_manager_id: emp.details.reportingManagerId ?? "",
        dotted_line_manager_id: dottedLineManager?.uuid ?? "",
        work_location: typeof rawRecord.work_location === "string" ? rawRecord.work_location : "",
        work_mode: typeof rawRecord.work_mode === "string" ? rawRecord.work_mode : "",
        probation_period_months: rawRecord.probation_period_months != null ? String(rawRecord.probation_period_months) : "",
        notice_period_days: rawRecord.notice_period_days != null ? String(rawRecord.notice_period_days) : "",
      }));
      baselineJoiningDate.current = emp.details.dateOfJoining ?? "";
      setPositionTitle(emp.designation ?? "");
      setOrgUnitName(emp.department ?? "");

      setStatutory(s => ({
        ...s,
        // account_number/ifsc_code are masked-only from this GET response
        // (see EmployeeRevealSensitiveView) — left blank here, same as
        // pan_number/aadhaar_number below, so saving without touching them
        // doesn't overwrite the real stored value with an empty string.
        account_holder_name: emp.details.accountHolderName ?? "",
        bank_name: emp.details.bankName ?? "",
        bank_branch_address: emp.details.bankBranch ?? "",
        // UAN / ESI number are never returned in full (UAN only masked): blank here means "keep what is on file".
        uan_number: "", esi_number: "",
        pf_covered: typeof rawRecord.pf_covered === "boolean" ? String(rawRecord.pf_covered) : s.pf_covered,
        esi_covered: typeof rawRecord.esi_covered === "boolean" ? String(rawRecord.esi_covered) : s.esi_covered,
      }));

      setCoreSkills(typeof rawRecord.core_skills === "string" ? rawRecord.core_skills : "");
      setCertifications(typeof rawRecord.certifications === "string" ? rawRecord.certifications : "");
      setAccessCard(c => ({ ...c, validFrom: c.validFrom || emp.details.dateOfJoining || "" }));

      setLoading(false);
      setCoreLoaded(true);
    }).catch(() => { setLoading(false); setCoreLoaded(true); });
  }, [employee.id, refreshDocs]);

  useEffect(() => {
    if (!uuid) return;
    Promise.allSettled([
      clientApi.get<{ data: FamilyEntry[] }>(API.onboarding.employees.family(uuid)).then(r => setFamilyEntries(r.data?.data ?? [])),
      clientApi.get<{ data: NomineeEntry[] }>(API.onboarding.employees.nominees(uuid)).then(r => setNomineeEntries(r.data?.data ?? [])),
      clientApi.get<{ data: AssetEntry[] }>(API.onboarding.employees.assets(uuid)).then(r => setAssetEntries(r.data?.data ?? [])),
      clientApi.get<{ data: EducationEntry[] }>(API.onboarding.employees.education(uuid)).then(r => setEducationEntries(r.data?.data ?? [])),
      clientApi.get<{ data: ExperienceEntry[] }>(API.onboarding.employees.experience(uuid)).then(r => setExperienceEntries(r.data?.data ?? [])),
      clientApi.get<{ data: EducationExperienceFieldConfigResponse }>(API.onboarding.educationExperienceFieldConfig)
        .then(r => setEduExpFieldConfig(r.data?.data ?? { education: [], experience: [] })),
      clientApi.get<{ data: EmployeeSalaryConfig[] }>(API.payroll.employeeSalaryHistory(uuid)).then(r => {
        const current = (r.data?.data ?? []).find(h => h.is_active) ?? null;
        const annualCtc = current ? String(Math.round(Number(current.annual_ctc))) : "";
        const salaryStructure = current?.salary_structure ?? "";
        baselineCtc.current = { annualCtc, salaryStructure };
        setEmployment(e => ({ ...e, annual_ctc: annualCtc, salary_structure: salaryStructure }));
      }),
    ]).then(() => setListsLoaded(true));
  }, [uuid]);

  const saveFamilyAndNominees = useCallback(async () => {
    if (!familyEntries.every(e => e.name.trim())) { setFamilyErr("Name is required for every family member entry."); return false; }
    if (!nomineeEntries.every(e => e.family_member)) { setFamilyErr("Select a family member for every nominee entry."); return false; }
    setFamilyErr(null);
    try {
      for (const id of deletedFamilyIds.current) await clientApi.delete(API.onboarding.employees.familyDetail(uuid, id));
      deletedFamilyIds.current.clear();

      const idMap = new Map<string, string>();
      const savedFamily: FamilyEntry[] = [];
      for (const entry of familyEntries) {
        const payload = { name: entry.name.trim(), relationship: entry.relationship, date_of_birth: entry.date_of_birth || null, gender: entry.gender, blood_group: entry.blood_group, is_dependent: entry.is_dependent };
        const isNew = entry.id.startsWith("temp-");
        const res = isNew
          ? await clientApi.post<{ data: FamilyEntry }>(API.onboarding.employees.family(uuid), payload)
          : await clientApi.patch<{ data: FamilyEntry }>(API.onboarding.employees.familyDetail(uuid, entry.id), payload);
        const saved = res.data?.data ?? entry;
        if (isNew) idMap.set(entry.id, saved.id);
        savedFamily.push(saved);
      }
      setFamilyEntries(savedFamily);

      for (const id of deletedNomineeIds.current) await clientApi.delete(API.onboarding.employees.nomineeDetail(uuid, id));
      deletedNomineeIds.current.clear();

      const savedNominees: NomineeEntry[] = [];
      for (const entry of nomineeEntries) {
        const realFamilyId = idMap.get(entry.family_member) ?? entry.family_member;
        const payload = { family_member: realFamilyId, scheme: entry.scheme, share_percentage: entry.share_percentage || "0" };
        const isNew = entry.id.startsWith("temp-");
        const res = isNew
          ? await clientApi.post<{ data: NomineeEntry }>(API.onboarding.employees.nominees(uuid), payload)
          : await clientApi.patch<{ data: NomineeEntry }>(API.onboarding.employees.nomineeDetail(uuid, entry.id), payload);
        savedNominees.push(res.data?.data ?? { ...entry, family_member: realFamilyId });
      }
      setNomineeEntries(savedNominees);
      return true;
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setFamilyErr(msg ?? "Failed to save family & nomination details.");
      return false;
    }
  }, [familyEntries, nomineeEntries, uuid]);

  const saveAssets = useCallback(async () => {
    if (!assetEntries.every(e => e.asset_type)) { setAssetErr("Select an asset type for every entry."); return false; }
    setAssetErr(null);
    try {
      for (const id of deletedAssetIds.current) await clientApi.delete(API.onboarding.employees.assetDetail(uuid, id));
      deletedAssetIds.current.clear();
      const saved: AssetEntry[] = [];
      for (const entry of assetEntries) {
        const isNew = entry.id.startsWith("temp-");
        // No "issue later" toggle here (see AssetsList.tsx) — adding an
        // entry means it's issued now, so the new row must be stamped
        // issued_at immediately. Without this issued_at stayed blank
        // forever and the ESS asset card showed a tag/date-less row under
        // an ASSIGNED badge.
        const payload = isNew
          ? { asset_type: entry.asset_type, tag_number: entry.tag_number, condition: entry.condition, issued_at: todayDateString() }
          : { asset_type: entry.asset_type, tag_number: entry.tag_number, condition: entry.condition };
        const res = isNew
          ? await clientApi.post<{ data: AssetEntry }>(API.onboarding.employees.assets(uuid), payload)
          : await clientApi.patch<{ data: AssetEntry }>(API.onboarding.employees.assetDetail(uuid, entry.id), payload);
        saved.push(res.data?.data ?? entry);
      }
      setAssetEntries(saved);
      return true;
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setAssetErr(msg ?? "Failed to save assets.");
      return false;
    }
  }, [assetEntries, uuid]);

  const saveEducationAndExperience = useCallback(async () => {
    for (const id of deletedEducationIds.current) await clientApi.delete(API.onboarding.employees.educationDetail(uuid, id));
    deletedEducationIds.current.clear();
    const savedEducation: EducationEntry[] = [];
    for (const entry of educationEntries) {
      const { id, ...payload } = entry;
      const isNew = id.startsWith("temp-");
      const res = isNew
        ? await clientApi.post<{ data: EducationEntry }>(API.onboarding.employees.education(uuid), payload)
        : await clientApi.patch<{ data: EducationEntry }>(API.onboarding.employees.educationDetail(uuid, id), payload);
      savedEducation.push(res.data?.data ?? entry);
    }
    setEducationEntries(savedEducation);

    for (const id of deletedExperienceIds.current) await clientApi.delete(API.onboarding.employees.experienceDetail(uuid, id));
    deletedExperienceIds.current.clear();
    const savedExperience: ExperienceEntry[] = [];
    for (const entry of experienceEntries) {
      const { id, ...payload } = entry;
      const isNew = id.startsWith("temp-");
      const res = isNew
        ? await clientApi.post<{ data: ExperienceEntry }>(API.onboarding.employees.experience(uuid), payload)
        : await clientApi.patch<{ data: ExperienceEntry }>(API.onboarding.employees.experienceDetail(uuid, id), payload);
      savedExperience.push(res.data?.data ?? entry);
    }
    setExperienceEntries(savedExperience);
    return true;
  }, [educationEntries, experienceEntries, uuid]);

  async function onUploadDocument(documentType: string, file: File) {
    setDocUploadError("");
    setUploadingDocType(documentType);
    try {
      const formData = new FormData();
      formData.append("document_type", documentType);
      formData.append("file", file);
      await clientApi.post(API.employees.documents(employee.id), formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const { data } = await clientApi.get<{ data: ApiEmployee }>(API.employees.detail(employee.id));
      refreshDocs(data.data);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setDocUploadError(msg || "Failed to upload document. Please try again.");
    } finally {
      setUploadingDocType(null);
    }
  }

  async function onSaveChanges(closeAfter = false) {
    setSaving(true);
    setSaveError(null);
    setSavedMsg(false);
    setContactErrors({});
    if (statutory.uan_number && statutory.uan_number.length !== 12) {
      setSaveError("UAN must be 12 digits");
      setSaving(false);
      return;
    }
    const contactChanges = buildContactChanges(personal, savedContact, canEditContact, isLoginChangeConfirmed);
    try {
      const primaryEmergency = emergencyContacts.find(c => c.is_primary) ?? emergencyContacts[0];
      const payload = {
        // Employment — only the fields with a real write path (see the
        // module docstring above for which EmploymentDraft fields have
        // none yet and are therefore NOT sent here).
        employee_type: employment.employment_type || '',
        branch: employment.branch || null,
        // Only sent when the user picked a different position / joining date (see EditRecordEmploymentStep).
        ...(employment.position ? { position: employment.position } : {}),
        ...(employment.date_of_joining && employment.date_of_joining !== baselineJoiningDate.current
          ? { date_of_joining: employment.date_of_joining } : {}),
        reporting_manager_id: employment.reporting_manager_id || null,
        dotted_line_manager_id: employment.dotted_line_manager_id || '',
        work_mode: employment.work_mode || '',
        probation_period_months: employment.probation_period_months || null,
        notice_period_days: employment.notice_period_days || null,
        ...contactChanges,
        // Personal identity
        salutation: personal.salutation || "",
        display_name: personal.displayName || "",
        nationality: personal.nationality || "",
        place_of_birth: personal.placeOfBirth || "",
        date_of_birth: personal.dateOfBirth || null,
        gender: personal.gender || "",
        marital_status: personal.maritalStatus || "",
        blood_group: personal.bloodGroup || "",
        father_name: familyEntries.find(entry => entry.relationship === "father")?.name || personal.fatherName || "",
        mother_name: familyEntries.find(entry => entry.relationship === "mother")?.name || personal.motherName || "",
        languages_known: personal.languagesKnown || "",
        current_address: values.currentAddress || "",
        current_address_line2: values.currentAddressLine2 || "",
        current_village: values.currentVillage || "",
        current_district: values.currentDistrict || "",
        current_state: values.currentState || "",
        current_pin_code: values.currentPinCode || "",
        permanent_address: values.permanentAddress || "",
        permanent_address_line2: values.permanentAddressLine2 || "",
        permanent_village: values.permanentVillage || "",
        permanent_district: values.permanentDistrict || "",
        permanent_state: values.permanentState || "",
        permanent_pin_code: values.permanentPinCode || "",
        permanent_same_as_current: values.permanentSameAsCurrent === "true",
        // Emergency contact — only the Primary entry has a real post-hire
        // slot (EmployeeProfile has one emergency-contact set of columns,
        // not a list) — same documented behavior as the Hire Wizard's own
        // EmergencyContactsList.
        emergency_name: primaryEmergency?.name ?? "",
        emergency_relationship: primaryEmergency?.relationship ?? "",
        emergency_phone: primaryEmergency?.phone ?? "",
        emergency_email: primaryEmergency?.email ?? "",
        // Statutory & accounts
        account_holder_name: statutory.account_holder_name || "",
        bank_name: statutory.bank_name || "",
        bank_branch_name: statutory.bank_branch_address || "",
        pf_covered: statutory.pf_covered === "true",
        esi_covered: statutory.esi_covered === "true",
        // Write-only re-entry — blank means "no change" (see
        // StatutoryAccountsStep's own "handled as sensitive data" banner;
        // the employee GET only ever returns masked previews, never
        // plaintext, so there is nothing to prefill and clear would mean
        // losing data silently).
        ...(statutory.uan_number ? { uan_number: statutory.uan_number } : {}),
        ...(statutory.esi_number ? { esi_number: statutory.esi_number } : {}),
        ...(statutory.pan_number ? { pan_number: statutory.pan_number } : {}),
        ...(statutory.aadhaar_number ? { aadhaar_number: statutory.aadhaar_number } : {}),
        ...(statutory.account_number ? { account_number: statutory.account_number } : {}),
        ...(statutory.ifsc_code ? { ifsc_code: statutory.ifsc_code } : {}),
        ...(statutory.passport_number ? { passport_number: statutory.passport_number, passport_expiry: statutory.passport_expiry || null } : {}),
        // Education & experience — core skills/certifications
        core_skills: coreSkills || "",
        certifications: certifications || "",
      };
      await clientApi.put(API.employees.detail(employee.id), payload);
      setSavedContact({ email: personal.personalEmail, mobile: personal.mobileNumber });
      setIsLoginChangeConfirmed(false);

      // Basic pay — only create a new EmployeeSalaryConfig revision if the
      // CTC/structure actually changed from what was loaded, so opening
      // and closing this section without editing it never creates a
      // spurious revision row. A real CTC change needs a reason on this
      // model (it's a revision, not a plain field edit) — "other" with a
      // fixed note is used here since this modal has no dedicated
      // reason/effective-date picker the way the full Salary tab does.
      let ctcOk = true;
      if (employment.annual_ctc && (
        employment.annual_ctc !== baselineCtc.current.annualCtc || employment.salary_structure !== baselineCtc.current.salaryStructure
      )) {
        try {
          await clientApi.post(API.payroll.employeeSalary, {
            employee: uuid, annual_ctc: employment.annual_ctc,
            effective_from: new Date().toISOString().split("T")[0],
            salary_structure: employment.salary_structure || null,
            reason: "other", reason_note: "Updated via Edit record",
          });
          baselineCtc.current = { annualCtc: employment.annual_ctc, salaryStructure: employment.salary_structure };
        } catch (err: unknown) {
          const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
          setSaveError(msg ?? "Failed to save the CTC change.");
          ctcOk = false;
        }
      }

      const familyOk = await saveFamilyAndNominees();
      const assetsOk = await saveAssets();
      const eduExpOk = await saveEducationAndExperience();

      const allOk = familyOk && assetsOk && eduExpOk && ctcOk;
      setSavedMsg(allOk);
      if (!allOk) {
        setSaveError(prev => prev ?? "Some sections could not be saved — see the errors above.");
      } else {
        setBaselineTick(t => t + 1);
        if (closeAfter) onClose();
      }
    } catch (err: unknown) {
      const parsed = parseApiError(err, "Failed to save changes. Please try again.");
      setContactErrors({ email: parsed.fieldErrors.email, phone: parsed.fieldErrors.phone });
      setSaveError(parsed.message);
    } finally {
      setSaving(false);
    }
  }

  const totalExperienceYears = useMemo(() => null, []); // no server-computed total for an existing employee in this pass
  const personalAge = ageFromDateOfBirth(personal.dateOfBirth);

  return (
    <>
    <Modal
      title={
        <div>
          <div className="text-[18px] font-bold">Edit <span style={{ color: "var(--primary)", fontStyle: "italic" }}>record</span></div>
          <div className="text-[12px] mt-0.5" style={{ color: "var(--on-variant)", fontWeight: 400 }}>
            Jump to any section, change what you need, and save. Nothing else has to be re-entered.
          </div>
        </div>
      }
      onClose={requestClose}
      size="lg"
      maxWidth={1100}
      scrollBody
      bodyStyle={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}
      footer={
        <div className="flex items-center gap-3 w-full justify-end" style={{ position: "relative" }}>
          {savedMsg && <span style={{ fontSize: 12, color: "var(--ok)", marginRight: "auto" }}>All changes saved</span>}
          {saveError && <span style={{ fontSize: 12, color: "var(--crit)", marginRight: "auto" }}>{saveError}</span>}
          <button onClick={openDrafts} disabled={saving} className="btn btn-ghost">Drafts{drafts.length > 0 ? ` (${drafts.length})` : ""}</button>
          <button onClick={() => onSaveChanges(false)} disabled={saving} className="btn btn-ghost">
            {saving ? "Saving…" : "Save"}
          </button>
          <button onClick={() => onSaveChanges(true)} disabled={saving} className="btn btn-filled">
            {saving ? "Saving…" : "Save & close"}
          </button>

          {showDrafts && (
            <div style={{
              position: "absolute", bottom: "calc(100% + 8px)", right: 0, zIndex: 50,
              width: 320, maxHeight: 360, overflowY: "auto",
              background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: 8,
              boxShadow: "var(--shadow-md)", padding: 10,
            }}>
              <div className="flex items-center justify-between" style={{ marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: "var(--on-variant)" }}>Drafts</span>
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowDrafts(false)}>
                  <i className="ti ti-x" />
                </button>
              </div>
              <button type="button" className="btn btn-ghost btn-sm" style={{ width: "100%", marginBottom: 8 }} onClick={saveCurrentAsDraft}>
                <i className="ti ti-device-floppy" /> Save current as draft
              </button>
              {draftSavedMsg && (
                <div style={{ fontSize: 12, color: "var(--ok)", marginBottom: 8 }}>
                  <i className="ti ti-circle-check" /> Draft saved
                </div>
              )}
              {drafts.length === 0 ? (
                <div style={{ fontSize: 12, color: "var(--on-variant)", padding: "8px 0" }}>No saved drafts yet.</div>
              ) : (
                drafts.map(d => (
                  <div key={d.id} className="flex items-center gap-2" style={{ padding: "6px 0", borderTop: "1px solid var(--outline-v)" }}>
                    <span style={{ fontSize: 12, flex: 1 }}>{new Date(d.savedAt).toLocaleString()}</span>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => loadDraft(d)}>Load</button>
                    <button type="button" className="btn btn-ghost btn-sm" style={{ color: "var(--error)" }} onClick={() => deleteDraft(d.id)}>
                      <i className="ti ti-trash" />
                    </button>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      }
    >
      {loading ? (
        <div className="flex items-center justify-center py-20 gap-2 text-[13px]" style={{ color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 animate-spin text-[22px]" style={{ color: "var(--primary)" }} />
          Loading…
        </div>
      ) : (
        <div className="wiz">
          <EditRecordSidebar currentStep={step} onStepClick={setStep} hasMissing={!personal.firstName.trim() || !personal.lastName.trim() || !statutory.account_holder_name.trim()} />

          <div className="wiz-main">
            <div className="stephead" style={{ padding: "20px 24px 0" }}>
              <div>
                {step === 1
                  ? <h3><em className="hl">Employment</em> details</h3>
                  : <h3>{STEPS[step].label}</h3>}
                <p>{step === 1 ? "Position, reporting line, work setup and pay." : STEPS[step].sub}</p>
              </div>
            </div>

            <div className="wiz-body">
              {step === 0 && (
                <div className="mstep on">
                  <div className="flex items-center gap-4 mb-5">
                    <Avatar text={`${personal.firstName} ${personal.lastName}`.trim() || employee.code} size={64} photoUrl={photoUrl} />
                    <div>
                      <div className="text-[12.5px] font-semibold mb-1">Employee photo</div>
                      <div className="text-[11px] mb-1.5" style={{ color: "var(--on-variant)" }}>
                        Square JPG or PNG, at least 400×400px. Cropped to a circle on ID cards and reports.
                      </div>
                      {/* Same "btn btn-ghost btn-sm" small outline button DocUploadButton
                          uses for every other inline attach control in the Hire flow
                          (PAN/Aadhaar/Passport cards, Documents step, certificates) —
                          reusing that exact class combination, not a new style. */}
                      <label className="btn btn-ghost btn-sm" style={{ cursor: uploadingPhoto ? "wait" : "pointer", display: "inline-flex" }}>
                        {uploadingPhoto ? <><i className="ti ti-loader-2 animate-spin" /> Uploading…</> : <><i className="ti ti-upload" /> Upload file</>}
                        <input
                          type="file" accept="image/jpeg,image/png" className="sr-only" disabled={uploadingPhoto}
                          onChange={e => { const file = e.target.files?.[0]; if (file) onUploadPhoto(file); e.target.value = ""; }}
                        />
                      </label>
                      {photoError && <div className="text-[11px] mt-1" style={{ color: "var(--error)" }}>{photoError}</div>}
                    </div>
                  </div>

                  <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Identity</div>
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Salutation <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>OPTIONAL</span></label>
                      <select value={personal.salutation} onChange={e => setPersonal(p => ({ ...p, salutation: e.target.value }))} className="field-input field-select">
                        <option value="">Select</option>
                        {["Mr.", "Ms.", "Mrs.", "Dr."].map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">First name <span style={{ color: "var(--error)" }}>*</span></label>
                      <input value={personal.firstName} readOnly className="field-input" style={{ background: "var(--bg-low)", color: "var(--on-variant)" }} />
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Middle name <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>OPTIONAL</span></label>
                      <input value={personal.middleName} onChange={e => setPersonal(p => ({ ...p, middleName: e.target.value }))} placeholder="e.g. Kumar" className="field-input" />
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3 mb-5">
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Last name <span style={{ color: "var(--error)" }}>*</span></label>
                      <input value={personal.lastName} readOnly className="field-input" style={{ background: "var(--bg-low)", color: "var(--on-variant)" }} />
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Display name <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>auto</span></label>
                      <div className="flex gap-2">
                        <input value={personal.displayName} onChange={e => setPersonal(p => ({ ...p, displayName: e.target.value }))} className="field-input" />
                        <button
                          type="button"
                          onClick={() => setPersonal(p => ({ ...p, displayName: [p.salutation, p.firstName, p.middleName, p.lastName].filter(Boolean).join(" ") }))}
                          className="btn btn-sm"
                          style={{ whiteSpace: "nowrap", background: "#7c3aed", color: "#ffffff", border: "none" }}
                        >+ Suggest</button>
                      </div>
                      <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Shown across the app and in approvals.</p>
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Employee number <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>auto</span></label>
                      <div className="field-input" style={{ background: "var(--bg-low)", color: "var(--on-bg)" }}>{employee.code}</div>
                    </div>
                  </div>

                  <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Basic details</div>
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Date of birth <span style={{ color: "var(--error)" }}>*</span></label>
                      <input type="date" value={personal.dateOfBirth} onChange={e => setPersonal(p => ({ ...p, dateOfBirth: e.target.value }))} className="field-input" />
                      {personalAge !== null && (
                        <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>
                          Age {personalAge}
                        </p>
                      )}
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Gender <span style={{ color: "var(--error)" }}>*</span></label>
                      <select value={personal.gender} onChange={e => setPersonal(p => ({ ...p, gender: e.target.value }))} className="field-input field-select">
                        <option value="">Select</option>
                        <option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Blood group <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>OPTIONAL</span></label>
                      <select value={personal.bloodGroup} onChange={e => setPersonal(p => ({ ...p, bloodGroup: e.target.value }))} className="field-input field-select">
                        <option value="">Select</option>
                        {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map(b => <option key={b} value={b}>{b}</option>)}
                      </select>
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3 mb-5">
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Marital status</label>
                      <select value={personal.maritalStatus} onChange={e => setPersonal(p => ({ ...p, maritalStatus: e.target.value }))} className="field-input field-select">
                        {MARITAL_STATUS_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Nationality <span style={{ color: "var(--error)" }}>*</span></label>
                      <CountrySelect value={personal.nationality} onChange={v => setPersonal(p => ({ ...p, nationality: v }))} mode="demonym" />
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Place of birth <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>OPTIONAL</span></label>
                      <div className="flex gap-2">
                        <input value={personal.placeOfBirth} onChange={e => setPersonal(p => ({ ...p, placeOfBirth: e.target.value }))} placeholder="City / town" className="field-input" />
                        <button
                          type="button"
                          onClick={() => setPersonal(p => ({ ...p, placeOfBirth: values.currentVillage || values.currentDistrict }))}
                          className="btn btn-sm"
                          style={{ whiteSpace: "nowrap", background: "#7c3aed", color: "#ffffff", border: "none" }}
                        >+ Suggest</button>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3 mb-5">
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Father&apos;s name <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>FROM FAMILY</span></label>
                      <div className="field-input" style={{ background: "var(--bg-low)", color: "var(--on-variant)" }}>
                        {familyEntries.find(entry => entry.relationship === "father")?.name || personal.fatherName || "Set in Family & nomination"}
                      </div>
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Mother&apos;s name <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>FROM FAMILY</span></label>
                      <div className="field-input" style={{ background: "var(--bg-low)", color: "var(--on-variant)" }}>
                        {familyEntries.find(entry => entry.relationship === "mother")?.name || personal.motherName || "Set in Family & nomination"}
                      </div>
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Languages known <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>OPTIONAL</span></label>
                      <LanguagesSelect
                        value={personal.languagesKnown}
                        onChange={languagesKnown => setPersonal(p => ({ ...p, languagesKnown }))}
                      />
                    </div>
                  </div>

                  <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Statutory declarations</div>
                  <div className="grid grid-cols-2 gap-3 mb-5">
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        Specially abled
                        <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: "0.03em", textTransform: "uppercase", color: "var(--warn)", background: "var(--warn-c)", borderRadius: 99, padding: "1px 6px" }}>RPwD</span>
                      </label>
                      <select value={personal.speciallyAbled} onChange={e => setPersonal(p => ({ ...p, speciallyAbled: e.target.value }))} className="field-input field-select">
                        <option value="no">No</option><option value="yes">Yes</option>
                      </select>
                      <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Record-keeping obligation under the RPwD Act 2016.</p>
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5" style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        International worker
                        <span style={{ fontSize: 8.5, fontWeight: 700, letterSpacing: "0.03em", textTransform: "uppercase", color: "var(--warn)", background: "var(--warn-c)", borderRadius: 99, padding: "1px 6px" }}>GOI</span>
                      </label>
                      <select value={personal.internationalWorker} onChange={e => setPersonal(p => ({ ...p, internationalWorker: e.target.value }))} className="field-input field-select">
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
                      <label className="block text-[12.5px] font-semibold mb-1.5">Category / community <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>OPTIONAL</span></label>
                      <select value={personal.category} onChange={e => setPersonal(p => ({ ...p, category: e.target.value }))} className="field-input field-select">
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
                    <EditRecordContactFields
                      canEdit={canEditContact}
                      email={personal.personalEmail}
                      mobile={personal.mobileNumber}
                      savedEmail={savedContact.email}
                      isLoginChangeConfirmed={isLoginChangeConfirmed}
                      emailError={contactErrors.email}
                      mobileError={contactErrors.phone}
                      onEmailChange={value => { setContactErrors(previous => ({ ...previous, email: undefined })); setPersonal(p => ({ ...p, personalEmail: value })); }}
                      onMobileChange={value => { setContactErrors(previous => ({ ...previous, phone: undefined })); setPersonal(p => ({ ...p, mobileNumber: value })); }}
                      onLoginChangeConfirmed={setIsLoginChangeConfirmed}
                    />
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Alternate mobile <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>OPTIONAL, not yet stored post-hire</span></label>
                      <PhoneInput value={personal.alternateMobile} onChange={v => setPersonal(p => ({ ...p, alternateMobile: v }))} placeholder="Optional" />
                    </div>
                  </div>

                  <AddressFields
                    form={{
                      current_address: values.currentAddress || "",
                      current_address_line2: values.currentAddressLine2 || "",
                      current_village: values.currentVillage || "",
                      current_district: values.currentDistrict || "",
                      current_state: values.currentState || "",
                      current_pin_code: values.currentPinCode || "",
                      permanent_address: values.permanentAddress || "",
                      permanent_address_line2: values.permanentAddressLine2 || "",
                      permanent_village: values.permanentVillage || "",
                      permanent_district: values.permanentDistrict || "",
                      permanent_state: values.permanentState || "",
                      permanent_pin_code: values.permanentPinCode || "",
                      permanent_same_as_current: values.permanentSameAsCurrent || "false",
                    }}
                    extras={addressExtras}
                    onFieldChange={(key, value) => {
                      const camelKey = ADDRESS_FIELD_TO_CAMEL[key] ?? key;
                      setValues(v => ({ ...v, [camelKey]: value }));
                    }}
                    onExtrasChange={(key, value) => setAddressExtras(x => ({ ...x, [key]: value }))}
                  />

                  <EmergencyContactsList
                    entries={emergencyContacts}
                    onAdd={() => setEmergencyContacts(p => [...p, { id: nextTempId(), name: "", relationship: "", phone: "", alternate_phone: "", email: "", address: "", is_primary: p.length === 0 }])}
                    onFieldChange={(id, field, value) => setEmergencyContacts(p => p.map(e => (e.id === id ? { ...e, [field]: value } : e)))}
                    onRemove={id => setEmergencyContacts(p => p.filter(e => e.id !== id))}
                    onSetPrimary={id => setEmergencyContacts(p => p.map(e => ({ ...e, is_primary: e.id === id })))}
                  />
                </div>
              )}

              {step === 1 && (
                <EditRecordEmploymentStep
                  value={employment} onChange={setEmployment}
                  positionTitle={positionTitle} orgUnitName={orgUnitName}
                />
              )}

              {step === 2 && (
                <BasicPayStep
                  annualCtc={employment.annual_ctc} salaryStructureId={employment.salary_structure}
                  branchName={employment.branch} value={basicPay} onChange={setBasicPay}
                />
              )}

              {step === 3 && (
                <StatutoryAccountsStep
                  savedUanMasked={savedUanMasked}
                  value={statutory}
                  onChange={setStatutory}
                  documents={hireDocs}
                  uploading={uploadingDocType}
                  docError={docUploadError}
                  onUploadDoc={onUploadDocument}
                  onDeleteDoc={() => setDocUploadError("To replace a document, upload a new file of the same type.")}
                />
              )}

              {step === 4 && (
                <div className="mstep on">
                  {familyErr && <div className="alert alert-error" style={{ marginBottom: 16 }}>{familyErr}</div>}

                  <div className="sechead">FAMILY MEMBERS</div>
                  <div className="hint" style={{ marginBottom: 14 }}>
                    Nominees are chosen from this list, and the parents&apos; names on step 1 are filled from it. Add family before setting nominations.
                  </div>
                  {familyEntries.map(entry => (
                    <div key={entry.id} style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: "14px 16px", marginBottom: 14 }}>
                      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                        <span className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--on-variant)" }}>Family member</span>
                        <button className="btn btn-ghost btn-sm" type="button" style={{ color: "var(--error)" }}
                          onClick={() => { if (!entry.id.startsWith("temp-")) deletedFamilyIds.current.add(entry.id); setFamilyEntries(p => p.filter(e => e.id !== entry.id)); setNomineeEntries(p => p.filter(n => n.family_member !== entry.id)); }}>
                          Remove
                        </button>
                      </div>
                      <div className="g3">
                        <div className="f"><label>Name</label><input className="finput" placeholder="Full name" value={entry.name} onChange={e => setFamilyEntries(p => p.map(x => x.id === entry.id ? { ...x, name: e.target.value } : x))} /></div>
                        <div className="f">
                          <label>Relationship</label>
                          <select className="finput field-select" value={entry.relationship} onChange={e => setFamilyEntries(p => p.map(x => x.id === entry.id ? { ...x, relationship: e.target.value } : x))}>
                            <option value="">Select</option>
                            {FAMILY_RELATIONSHIPS.map(r => <option key={r} value={r}>{FAMILY_RELATIONSHIP_LABELS[r]}</option>)}
                          </select>
                        </div>
                        <div className="f"><label>Date of birth</label><input className="finput" type="date" value={entry.date_of_birth} onChange={e => setFamilyEntries(p => p.map(x => x.id === entry.id ? { ...x, date_of_birth: e.target.value } : x))} /></div>
                        <div className="f">
                          <label>Gender</label>
                          <select className="finput field-select" value={entry.gender} onChange={e => setFamilyEntries(p => p.map(x => x.id === entry.id ? { ...x, gender: e.target.value } : x))}>
                            <option value="">Select</option>
                            <option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
                          </select>
                        </div>
                        <div className="f"><label>Blood group</label><input className="finput" placeholder="e.g. O+" value={entry.blood_group} onChange={e => setFamilyEntries(p => p.map(x => x.id === entry.id ? { ...x, blood_group: e.target.value } : x))} /></div>
                        <div className="f">
                          <label>Dependent</label>
                          <select className="finput field-select" value={entry.is_dependent ? "yes" : "no"} onChange={e => setFamilyEntries(p => p.map(x => x.id === entry.id ? { ...x, is_dependent: e.target.value === "yes" } : x))}>
                            <option value="yes">Yes</option><option value="no">No</option>
                          </select>
                        </div>
                      </div>
                    </div>
                  ))}
                  <button className="add" type="button" onClick={() => setFamilyEntries(p => [...p, { id: nextTempId(), name: "", relationship: "", date_of_birth: "", gender: "", blood_group: "", is_dependent: false }])}>
                    + Add family member
                  </button>

                  <div className="divider" />
                  <div className="sechead">NOMINATION</div>
                  <div className="hint" style={{ marginBottom: 14 }}>
                    Required for EPF Form 2. Nominees are picked from the family list, so a name is only typed once. Each scheme should total 100%.
                  </div>
                  {familyEntries.length === 0 && (
                    <div className="hint" style={{ color: "var(--warn)", marginBottom: 14 }}>Add a family member above before adding a nominee.</div>
                  )}
                  {nomineeEntries.map(entry => {
                    const familyMember = familyEntries.find(f => f.id === entry.family_member);
                    return (
                      <div key={entry.id} style={{ border: "1px solid var(--outline-v)", borderRadius: 10, padding: "14px 16px", marginBottom: 14 }}>
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
                          <span className="text-[11px] font-bold uppercase tracking-wide" style={{ color: "var(--on-variant)" }}>Nominee</span>
                          <button className="btn btn-ghost btn-sm" type="button" style={{ color: "var(--error)" }}
                            onClick={() => { if (!entry.id.startsWith("temp-")) deletedNomineeIds.current.add(entry.id); setNomineeEntries(p => p.filter(e => e.id !== entry.id)); }}>
                            Remove
                          </button>
                        </div>
                        <div className="g3">
                          <div className="f">
                            <label>Nominee</label>
                            <select className="finput field-select" value={entry.family_member} onChange={e => setNomineeEntries(p => p.map(x => x.id === entry.id ? { ...x, family_member: e.target.value } : x))}>
                              <option value="">{familyEntries.length === 0 ? "Add family members first" : "Select from family"}</option>
                              {familyEntries.map(f => <option key={f.id} value={f.id}>{f.name}{f.relationship ? ` (${FAMILY_RELATIONSHIP_LABELS[f.relationship] ?? f.relationship})` : ""}</option>)}
                            </select>
                          </div>
                          <div className="f">
                            <label>Relationship <span className="tag">AUTO</span></label>
                            <input className="finput" readOnly style={{ background: "var(--bg-low)", color: "var(--on-variant)" }} value={familyMember ? (FAMILY_RELATIONSHIP_LABELS[familyMember.relationship] ?? familyMember.relationship) : "From family record"} />
                          </div>
                          <div className="f">
                            <label>Scheme</label>
                            <select className="finput field-select" value={entry.scheme} onChange={e => setNomineeEntries(p => p.map(x => x.id === entry.id ? { ...x, scheme: e.target.value } : x))}>
                              {NOMINATION_SCHEMES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                            </select>
                          </div>
                          <div className="f"><label>Share %</label><input className="finput" type="number" min={0} max={100} value={entry.share_percentage} onChange={e => setNomineeEntries(p => p.map(x => x.id === entry.id ? { ...x, share_percentage: e.target.value.replace(/[^0-9]/g, "") } : x))} /></div>
                        </div>
                      </div>
                    );
                  })}
                  <button className="add" type="button" disabled={familyEntries.length === 0} onClick={() => setNomineeEntries(p => [...p, { id: nextTempId(), family_member: "", scheme: "epf_eps", share_percentage: "" }])}>
                    + Add nominee
                  </button>
                  {nomineeEntries.length > 0 && (
                    <div className="flex justify-end mt-2">
                      <span className={`text-[12px] font-semibold ${NOMINATION_SCHEMES.filter(s => s.value !== "both").every(s => {
                        const total = nomineeEntries.filter(n => n.scheme === s.value || n.scheme === "both").reduce((sum, n) => sum + (Number(n.share_percentage) || 0), 0);
                        return total === 100 || total === 0;
                      }) ? "text-emerald-600" : "text-red-500"}`}>
                        {NOMINATION_SCHEMES.filter(s => s.value !== "both").map(s => {
                          const total = nomineeEntries.filter(n => n.scheme === s.value || n.scheme === "both").reduce((sum, n) => sum + (Number(n.share_percentage) || 0), 0);
                          return `${s.label} ${total}%`;
                        }).join(" · ")}
                      </span>
                    </div>
                  )}

                  <div className="divider" />
                  <div className="sechead">GUARDIAN</div>
                  <div className="hint" style={{ marginBottom: 14 }}>Only required if a nominee above is under 18.</div>
                  <div className="g3">
                    <div className="f">
                      <label>Guardian name <span className="tag">OPTIONAL</span></label>
                      <div style={{ display: "flex", gap: 8 }}>
                        <input className="finput" value={guardian.name} onChange={e => setGuardian(g => ({ ...g, name: e.target.value }))} />
                        <button type="button" className="btn btn-sm" style={{ whiteSpace: "nowrap", background: "#7c3aed", color: "#ffffff", border: "none" }}
                          onClick={() => { const primary = emergencyContacts.find(c => c.is_primary) ?? emergencyContacts[0]; if (primary) setGuardian(g => ({ ...g, name: primary.name, relationship: primary.relationship })); }}>
                          + Suggest
                        </button>
                      </div>
                    </div>
                    <div className="f">
                      <label>Relationship <span className="tag">OPTIONAL</span></label>
                      <input className="finput" value={guardian.relationship} onChange={e => setGuardian(g => ({ ...g, relationship: e.target.value }))} />
                    </div>
                    <div className="f">
                      <label>Guardian address <span className="tag">OPTIONAL</span></label>
                      <input className="finput" placeholder="Optional" value={guardian.address} onChange={e => setGuardian(g => ({ ...g, address: e.target.value }))} />
                    </div>
                  </div>
                </div>
              )}

              {step === 5 && (
                <div className="mstep on edit-record-eduexp">
                  {/* EducationChecklist/ExperienceList's own "+ Add..." button
                      is a small, left-aligned "btn btn-ghost" (correct for
                      their other real callers — self-service and HR
                      onboarding wizards) — scoped override here only, to
                      match this modal's full-width centered "+ Add..." bar
                      style used everywhere else (Family & nomination,
                      Assets). :not(.btn-sm) excludes each entry's small
                      "Remove" button, which shares the btn-ghost class. */}
                  <style jsx>{`
                    .edit-record-eduexp :global(button.btn.btn-ghost:not(.btn-sm)) {
                      display: block;
                      width: 100%;
                      text-align: center;
                      padding: 10px 16px;
                      margin-bottom: 20px;
                      border: 1.5px dashed var(--line, var(--outline-v));
                      background: var(--sunken, var(--brand-tint));
                      color: var(--brand-ink, var(--primary));
                      border-radius: 12px;
                      font-weight: 700;
                    }
                  `}</style>
                  <div className="flex flex-wrap gap-x-6 gap-y-2 rounded-lg px-3.5 py-2.5 mb-3" style={{ background: "var(--brand-tint)" }}>
                    {[
                      ["Qualifications", String(educationEntries.length)],
                      ["Highest", educationEntries.find(e => e.is_highest)?.level || "—"],
                      ["Institution", educationEntries.find(e => e.is_highest)?.institution || "—"],
                      ["Specialization", educationEntries.find(e => e.is_highest)?.specialization || "—"],
                      ["Grade", educationEntries.find(e => e.is_highest)?.percentage || "—"],
                      ["Completed", educationEntries.find(e => e.is_highest)?.end_date || "—"],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <div className="text-[9px] font-bold tracking-wider uppercase" style={{ color: "var(--primary)" }}>{label}</div>
                        <div className="text-[12.5px] font-semibold" style={{ color: "var(--on-bg)" }}>{value}</div>
                      </div>
                    ))}
                  </div>
                  <EducationChecklist
                    entries={educationEntries} fieldConfig={eduExpFieldConfig.education}
                    onAdd={() => setEducationEntries(p => [...p, { id: nextTempId(), level: "", custom_level_label: "", institution: "", specialization: "", percentage: "", start_date: "", end_date: "", is_highest: false }])}
                    onFieldChange={(id, field, value) => setEducationEntries(p => p.map(e => (e.id === id ? { ...e, [field]: value } : e)))}
                    onRemove={id => { if (!id.startsWith("temp-")) deletedEducationIds.current.add(id); setEducationEntries(p => p.filter(e => e.id !== id)); }}
                    onSetHighest={id => setEducationEntries(p => p.map(e => ({ ...e, is_highest: e.id === id })))}
                    documents={hireDocs} uploading={uploadingDocType} onUploadDoc={onUploadDocument}
                    error={null}
                  />
                  <div className="flex flex-wrap gap-x-6 gap-y-2 rounded-lg px-3.5 py-2.5 mb-3 mt-5" style={{ background: "var(--brand-tint)" }}>
                    {[
                      ["Employers", String(experienceEntries.length)],
                      ["Most recent", experienceEntries[0] ? `${experienceEntries[0].designation} · ${experienceEntries[0].employer_name}` : "—"],
                      ["Last working day", experienceEntries[0]?.end_date || "—"],
                    ].map(([label, value]) => (
                      <div key={label}>
                        <div className="text-[9px] font-bold tracking-wider uppercase" style={{ color: "var(--primary)" }}>{label}</div>
                        <div className="text-[12.5px] font-semibold" style={{ color: "var(--on-bg)" }}>{value}</div>
                      </div>
                    ))}
                  </div>
                  <ExperienceList
                    totalExperienceYears={totalExperienceYears} entries={experienceEntries} fieldConfig={eduExpFieldConfig.experience}
                    onAdd={() => setExperienceEntries(p => [...p, { id: nextTempId(), employer_name: "", designation: "", employment_type: "full_time", start_date: "", end_date: "", is_current: false, responsibilities: "", reason_for_leaving: "" }])}
                    onFieldChange={(id, field, value) => setExperienceEntries(p => p.map(e => (e.id === id ? { ...e, [field]: value } : e)))}
                    onRemove={id => { if (!id.startsWith("temp-")) deletedExperienceIds.current.add(id); setExperienceEntries(p => p.filter(e => e.id !== id)); }}
                    documents={hireDocs} uploading={uploadingDocType} onUploadDoc={onUploadDocument}
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

              {step === 6 && (
                <DocumentsChecklistStep
                  documents={hireDocs}
                  uploading={uploadingDocType}
                  error={docUploadError}
                  onUpload={onUploadDocument}
                  onDelete={() => setDocUploadError("To replace a document, upload a new file of the same type.")}
                  verification={verification} onVerificationChange={setVerification}
                  hasExperienceEntries={experienceEntries.length > 0}
                />
              )}

              {step === 7 && (
                <div className="mstep on edit-record-assets">
                  {/* Same scoped override as Education & experience above —
                      AssetsList's own "+ Issue an Asset" button is a small,
                      left-aligned "btn btn-ghost" (correct for its other
                      real caller, the self-service onboarding wizard). */}
                  <style jsx>{`
                    .edit-record-assets :global(button.btn.btn-ghost:not(.btn-sm)) {
                      display: block;
                      width: 100%;
                      text-align: center;
                      padding: 10px 16px;
                      margin-bottom: 20px;
                      border: 1.5px dashed var(--line, var(--outline-v));
                      background: var(--sunken, var(--brand-tint));
                      color: var(--brand-ink, var(--primary));
                      border-radius: 12px;
                      font-weight: 700;
                    }
                  `}</style>
                  <AssetsList
                    entries={assetEntries}
                    onAdd={() => setAssetEntries(p => [...p, { id: nextTempId(), asset_type: "", tag_number: "", condition: "new" }])}
                    onFieldChange={(id, field, value) => setAssetEntries(p => p.map(e => (e.id === id ? { ...e, [field]: value } : e)))}
                    onRemove={id => { if (!id.startsWith("temp-")) deletedAssetIds.current.add(id); setAssetEntries(p => p.filter(e => e.id !== id)); }}
                    error={assetErr}
                  />
                  <div className="divider" />
                  <div className="sechead">ACCESS CARD</div>
                  <div className="g3">
                    <div className="f">
                      <label>Card number <span className="tag">OPTIONAL</span></label>
                      <div style={{ display: "flex", gap: 8 }}>
                        <input className="finput" placeholder="Auto-generated if left blank" value={accessCard.cardNumber} onChange={e => setAccessCard(c => ({ ...c, cardNumber: e.target.value }))} />
                        <button type="button" className="btn btn-sm" style={{ whiteSpace: "nowrap", background: "#7c3aed", color: "#ffffff", border: "none" }}
                          onClick={() => setAccessCard(c => ({ ...c, cardNumber: `AC-${Math.floor(Math.random() * 90000 + 10000)}` }))}>
                          + Suggest
                        </button>
                      </div>
                    </div>
                    <div className="f"><label>Valid from</label><input className="finput" type="date" value={accessCard.validFrom} onChange={e => setAccessCard(c => ({ ...c, validFrom: e.target.value }))} /></div>
                    <div className="f"><label>Valid till</label><input className="finput" type="date" value={accessCard.validTill} onChange={e => setAccessCard(c => ({ ...c, validTill: e.target.value }))} /></div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </Modal>

    {showCloseConfirm && (
      <Modal
        title="Unsaved changes"
        onClose={() => setShowCloseConfirm(false)}
        footer={
          <div className="flex items-center gap-3 w-full justify-end">
            <button className="btn btn-ghost" onClick={() => setShowCloseConfirm(false)}>Keep editing</button>
            <button
              className="btn btn-filled"
              style={{ background: "var(--error)" }}
              onClick={() => { setShowCloseConfirm(false); onClose(); }}
            >
              Discard changes
            </button>
          </div>
        }
      >
        <p style={{ fontSize: 13, color: "var(--on-variant)" }}>
          You have unsaved changes to this record. Closing now will discard them — save, or save as a draft to come back to later, first.
        </p>
      </Modal>
    )}
    </>
  );
}

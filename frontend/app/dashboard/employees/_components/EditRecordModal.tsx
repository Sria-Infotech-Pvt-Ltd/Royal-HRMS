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
//   1 Employment             EmploymentStep (real import)           User fields (role/branch/reporting
//                                                                   lines/work setup) — see note below
//                                                                   on fields with no write path yet
//   2 Basic pay              SalaryTab (NOT BasicPayStep)           real EmployeeSalaryConfig system —
//                                                                   see note below
//   3 Statutory & accounts   StatutoryAccountsStep (real import)    EmployeeProfile (PAN/Aadhaar/PF/ESI/bank)
//   4 Family & nomination    FamilyNominationStep (real import)     /onboarding/employees/<uuid>/family,nominees
//   5 Education & experience EducationChecklist + ExperienceList    /onboarding/employees/<uuid>/education,experience
//                            (real imports, same as the self-service
//                             and HR-onboarding wizards use)
//   6 Documents               DocumentsChecklistStep (real import)  existing employee documents endpoint
//   7 Assets                 AssetsList (real import)               /onboarding/employees/<uuid>/assets
//
// Note on Basic pay: BasicPayStep is NOT reused here. It computes purely
// from local draft state (employment.annual_ctc/salary_structure) with no
// save endpoint of its own — at hire completion those numbers are only
// ever persisted as part of the whole-hire payload. For an ALREADY-HIRED
// employee the real, live equivalent is the existing EmployeeSalaryConfig
// system (SalaryTab), which already has its own working fetch/save this
// modal reuses instead of re-deriving numbers from a field that doesn't
// exist post-hire.
//
// Note on Employment: EmploymentStep itself fetches its own dropdown data
// (roles/branches/people/policies) — passed through here unchanged. Some
// of its fields map to real, now-writable User columns (role, branch,
// reporting_manager_id, dotted_line_manager_id, work_location, work_mode,
// probation_period_months, notice_period_days — see the backend
// employees_detail.py whitelist extension that went with this change).
// Others (weekly_off_policy, working_hours_policy/shift, salary_structure,
// annual_ctc, pay_group, attendance_scheme, leave_plan) have NO post-hire
// write path anywhere in this codebase yet — they render (same UI, same
// fields, matching the explicit request) but are NOT sent on save; this is
// stated in-code at the save call, not silently dropped without a trace.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import PhoneInput from "@/components/PhoneInput";
import CountrySelect from "@/components/CountrySelect";
import type { HireDocument } from "@/components/DocUploadButton";
import type { DetailValues, Employee } from "../_data";
import Avatar from "./Avatar";
import { apiToEmployee, type ApiEmployee } from "../[id]/_apiMapping";
import SalaryTab from "../[id]/_components/SalaryTab";
import { STEPS as HIRE_STEPS } from "../../hire/[hireActionId]/_components/_wizardData";
import StatutoryAccountsStep, { EMPTY_STATUTORY, type StatutoryDraft } from "../../hire/[hireActionId]/_components/StatutoryAccountsStep";
import EmploymentStep, { EMPTY_EMPLOYMENT, type EmploymentDraft } from "../../hire/[hireActionId]/_components/EmploymentStep";
import DocumentsChecklistStep, { EMPTY_VERIFICATION, type VerificationDraft } from "../../hire/[hireActionId]/_components/DocumentsChecklistStep";
import EmergencyContactsList, { type EmergencyContactEntry } from "../../hire/[hireActionId]/_components/EmergencyContactsList";
import FamilyNominationStep, { type FamilyEntry, type NomineeEntry } from "@/app/onboarding/_components/FamilyNominationStep";
import AssetsList, { type AssetEntry } from "@/app/onboarding/_components/AssetsList";
import EducationChecklist, { type EducationEntry } from "@/app/onboarding/_components/EducationChecklist";
import ExperienceList, { type ExperienceEntry } from "@/app/onboarding/_components/ExperienceList";
import type { EducationExperienceFieldConfigResponse } from "@/types/onboardingFieldConfig";

const STEPS = HIRE_STEPS.slice(0, -1); // drop "Review" — not applicable to editing an existing record

let tempId = 0;
const nextTempId = () => `temp-${++tempId}`;

// Flat section nav for this modal — deliberately NOT HireWizardSidebar.
// That component is built for linear wizard progress (numbered circles,
// a per-step "N fields still required" count badge from each step's
// static STEPS[i].required) — correct for a one-way hire flow, wrong for
// an edit view where every section is already complete and any section
// can be opened in any order. Same label/sub/group/tag data, no numbers,
// no required-count badges.
function EditRecordSidebar({ currentStep, onStepClick, hasMissing }: { currentStep: number; onStepClick: (i: number) => void; hasMissing: boolean }) {
  return (
    <div className="wiz-nav">
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
// column at all (salutation, middle name, display name, nationality, place
// of birth, mother's name, languages known, specially abled, international
// worker, category) are LOCAL ONLY in this pass — rendered for visual/field
// parity with Hire, but not sent on save. Flagged plainly, not hidden.
interface PersonalIdentityDraft {
  salutation: string; firstName: string; middleName: string; lastName: string; displayName: string;
  dateOfBirth: string; gender: string; bloodGroup: string; maritalStatus: string; nationality: string; placeOfBirth: string;
  motherName: string; languagesKnown: string[]; speciallyAbled: string; internationalWorker: string; category: string;
  personalEmail: string; mobileNumber: string; alternateMobile: string;
}
const EMPTY_PERSONAL: PersonalIdentityDraft = {
  salutation: "", firstName: "", middleName: "", lastName: "", displayName: "",
  dateOfBirth: "", gender: "", bloodGroup: "", maritalStatus: "single", nationality: "", placeOfBirth: "",
  motherName: "", languagesKnown: [], speciallyAbled: "no", internationalWorker: "no", category: "prefer_not_to_say",
  personalEmail: "", mobileNumber: "", alternateMobile: "",
};

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

  const [uuid, setUuid] = useState("");
  const [loading, setLoading] = useState(true);
  const [values, setValues] = useState<DetailValues>({});

  const [personal, setPersonal] = useState<PersonalIdentityDraft>(EMPTY_PERSONAL);
  const [emergencyContacts, setEmergencyContacts] = useState<EmergencyContactEntry[]>([]);

  const [employment, setEmployment] = useState<EmploymentDraft>(EMPTY_EMPLOYMENT);
  const [positionTitle, setPositionTitle] = useState("");
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

  const refreshDocs = useCallback((raw: ApiEmployee) => {
    setHireDocs((raw.documents ?? []).map(d => ({
      id: String(d.id), document_type: d.document_type, document_type_display: d.document_type_display,
      entry_ref: "", file_name: d.file_name, file_size: d.file_size, uploaded_at: d.uploaded_at,
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
        displayName: `${emp.firstName ?? ""} ${emp.lastName ?? ""}`.trim(),
        dateOfBirth: emp.details.dateOfBirth ?? "", gender: emp.details.gender ?? "",
        bloodGroup: emp.details.bloodGroup ?? "", maritalStatus: (emp.details.maritalStatus ?? "single").toLowerCase(),
        motherName: typeof rawRecord.mother_name === "string" ? rawRecord.mother_name : "",
        personalEmail: emp.email ?? "", mobileNumber: emp.phone ?? "",
      }));

      const legacyEmergency: EmergencyContactEntry = {
        id: nextTempId(), name: emp.details.emergencyName ?? "", relationship: emp.details.emergencyRelationship ?? "",
        phone: emp.details.emergencyPhone ?? "", alternate_phone: "", email: emp.details.emergencyEmail ?? "", address: "",
        is_primary: true,
      };
      setEmergencyContacts(legacyEmergency.name ? [legacyEmergency] : []);

      setEmployment(e => ({
        ...e,
        role: emp.details.ssRole ?? "", branch: emp.details.branch ?? "",
        reporting_manager_id: emp.details.reportingManagerId ?? "",
        dotted_line_manager_id: dottedLineManager?.uuid ?? "",
        work_location: typeof rawRecord.work_location === "string" ? rawRecord.work_location : "",
        work_mode: typeof rawRecord.work_mode === "string" ? rawRecord.work_mode : "",
        probation_period_months: rawRecord.probation_period_months != null ? String(rawRecord.probation_period_months) : "",
        notice_period_days: rawRecord.notice_period_days != null ? String(rawRecord.notice_period_days) : "",
      }));
      setPositionTitle(emp.designation ?? "");
      setOrgUnitName(emp.department ?? "");

      setStatutory(s => ({
        ...s,
        account_holder_name: emp.details.accountHolderName ?? "", account_number: emp.details.accountNumber ?? "",
        ifsc_code: emp.details.ifscCode ?? "", bank_name: emp.details.bankName ?? "",
        bank_branch_address: emp.details.bankBranch ?? "",
        uan_number: emp.details.uanNumber ?? "", esi_number: emp.details.esiNumber ?? "",
        pf_covered: typeof rawRecord.pf_covered === "boolean" ? String(rawRecord.pf_covered) : s.pf_covered,
        esi_covered: typeof rawRecord.esi_covered === "boolean" ? String(rawRecord.esi_covered) : s.esi_covered,
      }));

      setCoreSkills(typeof rawRecord.core_skills === "string" ? rawRecord.core_skills : "");
      setCertifications(typeof rawRecord.certifications === "string" ? rawRecord.certifications : "");

      setLoading(false);
    }).catch(() => setLoading(false));
  }, [employee.id, refreshDocs]);

  useEffect(() => {
    if (!uuid) return;
    clientApi.get<{ data: FamilyEntry[] }>(API.onboarding.employees.family(uuid)).then(r => setFamilyEntries(r.data?.data ?? [])).catch(() => {});
    clientApi.get<{ data: NomineeEntry[] }>(API.onboarding.employees.nominees(uuid)).then(r => setNomineeEntries(r.data?.data ?? [])).catch(() => {});
    clientApi.get<{ data: AssetEntry[] }>(API.onboarding.employees.assets(uuid)).then(r => setAssetEntries(r.data?.data ?? [])).catch(() => {});
    clientApi.get<{ data: EducationEntry[] }>(API.onboarding.employees.education(uuid)).then(r => setEducationEntries(r.data?.data ?? [])).catch(() => {});
    clientApi.get<{ data: ExperienceEntry[] }>(API.onboarding.employees.experience(uuid)).then(r => setExperienceEntries(r.data?.data ?? [])).catch(() => {});
    clientApi.get<{ data: EducationExperienceFieldConfigResponse }>(API.onboarding.educationExperienceFieldConfig)
      .then(r => setEduExpFieldConfig(r.data?.data ?? { education: [], experience: [] })).catch(() => {});
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
        const payload = { asset_type: entry.asset_type, tag_number: entry.tag_number, condition: entry.condition };
        const isNew = entry.id.startsWith("temp-");
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

  async function onSaveChanges() {
    setSaving(true);
    setSaveError(null);
    setSavedMsg(false);
    try {
      const primaryEmergency = emergencyContacts.find(c => c.is_primary) ?? emergencyContacts[0];
      const payload = {
        // Employment — only the fields with a real write path (see the
        // module docstring above for which EmploymentDraft fields have
        // none yet and are therefore NOT sent here).
        branch: employment.branch || null,
        role: employment.role || null,
        reporting_manager_id: employment.reporting_manager_id || null,
        dotted_line_manager_id: employment.dotted_line_manager_id || '',
        work_location: employment.work_location || '',
        work_mode: employment.work_mode || '',
        probation_period_months: employment.probation_period_months || null,
        notice_period_days: employment.notice_period_days || null,
        // Personal identity
        date_of_birth: personal.dateOfBirth || null,
        gender: personal.gender || "",
        marital_status: personal.maritalStatus || "",
        blood_group: personal.bloodGroup || "",
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
        account_number: statutory.account_number || "",
        ifsc_code: statutory.ifsc_code || "",
        bank_name: statutory.bank_name || "",
        bank_branch_name: statutory.bank_branch_address || "",
        uan_number: statutory.uan_number || "",
        esi_number: statutory.esi_number || "",
        pf_covered: statutory.pf_covered === "true",
        esi_covered: statutory.esi_covered === "true",
        // Write-only re-entry — blank means "no change" (see
        // StatutoryAccountsStep's own "handled as sensitive data" banner;
        // the employee GET only ever returns masked previews, never
        // plaintext, so there is nothing to prefill and clear would mean
        // losing data silently).
        ...(statutory.pan_number ? { pan_number: statutory.pan_number } : {}),
        ...(statutory.aadhaar_number ? { aadhaar_number: statutory.aadhaar_number } : {}),
        ...(statutory.passport_number ? { passport_number: statutory.passport_number, passport_expiry: statutory.passport_expiry || null } : {}),
        // Education & experience — core skills/certifications
        core_skills: coreSkills || "",
        certifications: certifications || "",
      };
      await clientApi.put(API.employees.detail(employee.id), payload);

      const familyOk = await saveFamilyAndNominees();
      const assetsOk = await saveAssets();
      const eduExpOk = await saveEducationAndExperience();

      setSavedMsg(familyOk && assetsOk && eduExpOk);
      if (!familyOk || !assetsOk || !eduExpOk) setSaveError("Some sections could not be saved — see the errors above.");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveError(msg ?? "Failed to save changes. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function onDiscard() {
    setSaveError(null);
    setSavedMsg(false);
  }

  const totalExperienceYears = useMemo(() => null, []); // no server-computed total for an existing employee in this pass

  return (
    <Modal
      title={
        <div>
          <div className="text-[18px] font-bold">Edit <span style={{ color: "var(--primary)", fontStyle: "italic" }}>record</span></div>
          <div className="text-[12px] mt-0.5" style={{ color: "var(--on-variant)", fontWeight: 400 }}>
            Jump to any section, change what you need, and save. Nothing else has to be re-entered.
          </div>
        </div>
      }
      onClose={onClose}
      size="lg"
      maxWidth={1100}
      scrollBody
      bodyStyle={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}
      footer={
        <div className="flex items-center gap-3 w-full justify-end">
          {savedMsg && <span style={{ fontSize: 12, color: "var(--ok)", marginRight: "auto" }}>All changes saved</span>}
          {saveError && <span style={{ fontSize: 12, color: "var(--crit)", marginRight: "auto" }}>{saveError}</span>}
          <button onClick={onDiscard} disabled={saving} className="btn btn-ghost">Discard</button>
          <button onClick={onClose} className="btn btn-ghost">Cancel</button>
          <button onClick={onSaveChanges} disabled={saving} className="btn btn-filled">
            {saving ? "Saving…" : "Save changes"}
          </button>
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
                <h3>{STEPS[step].label}</h3>
                <p>{STEPS[step].sub}</p>
              </div>
            </div>

            <div style={{ padding: 24 }}>
              {step === 0 && (
                <div className="mstep on">
                  <div className="flex items-center gap-4 mb-5">
                    <Avatar text={`${personal.firstName} ${personal.lastName}`.trim() || employee.code} size={64} photoUrl={employee.photoUrl} />
                    <div>
                      <div className="text-[12.5px] font-semibold mb-1">Employee photo</div>
                      <div className="text-[11px] mb-1.5" style={{ color: "var(--on-variant)" }}>
                        Square JPG or PNG, at least 400×400px. Cropped to a circle on ID cards and reports.
                      </div>
                      <div className="text-[11px]" style={{ color: "var(--on-variant)" }}>
                        Employees upload their own photo from their profile — HR can&apos;t change it on their behalf here.
                      </div>
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
                      <input value={personal.displayName} onChange={e => setPersonal(p => ({ ...p, displayName: e.target.value }))} className="field-input" />
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
                        <option value="single">Single</option><option value="married">Married</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Nationality <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>not yet stored post-hire</span></label>
                      <CountrySelect value={personal.nationality} onChange={v => setPersonal(p => ({ ...p, nationality: v }))} mode="demonym" />
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Place of birth <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>OPTIONAL, not yet stored post-hire</span></label>
                      <input value={personal.placeOfBirth} onChange={e => setPersonal(p => ({ ...p, placeOfBirth: e.target.value }))} placeholder="City / town" className="field-input" />
                    </div>
                  </div>

                  <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Contact</div>
                  <div className="grid grid-cols-3 gap-3 mb-5">
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Personal email <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>read-only here</span></label>
                      <input value={personal.personalEmail} readOnly className="field-input" style={{ background: "var(--bg-low)", color: "var(--on-variant)" }} />
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Mobile number <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>read-only here</span></label>
                      <PhoneInput value={personal.mobileNumber} onChange={() => {}} placeholder="90000 00000" />
                    </div>
                    <div>
                      <label className="block text-[12.5px] font-semibold mb-1.5">Alternate mobile <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>OPTIONAL, not yet stored post-hire</span></label>
                      <PhoneInput value={personal.alternateMobile} onChange={v => setPersonal(p => ({ ...p, alternateMobile: v }))} placeholder="Optional" />
                    </div>
                  </div>

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
                <EmploymentStep
                  value={employment} onChange={setEmployment} onSetEmploymentType={() => {}}
                  reservedEmployeeId={employee.code} positionTitle={positionTitle} orgUnitName={orgUnitName}
                  grade="" costCenter="" defaultRoleId={null} defaultRoleName={null}
                />
              )}

              {step === 2 && <SalaryTab employeeId={uuid} employeeCode={employee.code} />}

              {step === 3 && (
                <StatutoryAccountsStep
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
                <FamilyNominationStep
                  familyEntries={familyEntries}
                  nomineeEntries={nomineeEntries}
                  onAddFamily={() => setFamilyEntries(p => [...p, { id: nextTempId(), name: "", relationship: "child", date_of_birth: "", gender: "", blood_group: "", is_dependent: false }])}
                  onFamilyFieldChange={(id, field, value) => setFamilyEntries(p => p.map(e => (e.id === id ? { ...e, [field]: value } : e)))}
                  onRemoveFamily={id => { if (!id.startsWith("temp-")) deletedFamilyIds.current.add(id); setFamilyEntries(p => p.filter(e => e.id !== id)); setNomineeEntries(p => p.filter(n => n.family_member !== id)); }}
                  onAddNominee={() => setNomineeEntries(p => [...p, { id: nextTempId(), family_member: "", scheme: "epf_eps", share_percentage: "" }])}
                  onNomineeFieldChange={(id, field, value) => setNomineeEntries(p => p.map(e => (e.id === id ? { ...e, [field]: value } : e)))}
                  onRemoveNominee={id => { if (!id.startsWith("temp-")) deletedNomineeIds.current.add(id); setNomineeEntries(p => p.filter(e => e.id !== id)); }}
                  error={familyErr}
                />
              )}

              {step === 5 && (
                <div className="mstep on">
                  <EducationChecklist
                    entries={educationEntries} fieldConfig={eduExpFieldConfig.education}
                    onAdd={() => setEducationEntries(p => [...p, { id: nextTempId(), level: "", custom_level_label: "", institution: "", specialization: "", percentage: "", start_date: "", end_date: "", is_highest: false }])}
                    onFieldChange={(id, field, value) => setEducationEntries(p => p.map(e => (e.id === id ? { ...e, [field]: value } : e)))}
                    onRemove={id => { if (!id.startsWith("temp-")) deletedEducationIds.current.add(id); setEducationEntries(p => p.filter(e => e.id !== id)); }}
                    onSetHighest={id => setEducationEntries(p => p.map(e => ({ ...e, is_highest: e.id === id })))}
                    documents={hireDocs} uploading={uploadingDocType} onUploadDoc={onUploadDocument}
                    error={null}
                  />
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
                <AssetsList
                  entries={assetEntries}
                  onAdd={() => setAssetEntries(p => [...p, { id: nextTempId(), asset_type: "", tag_number: "", condition: "new" }])}
                  onFieldChange={(id, field, value) => setAssetEntries(p => p.map(e => (e.id === id ? { ...e, [field]: value } : e)))}
                  onRemove={id => { if (!id.startsWith("temp-")) deletedAssetIds.current.add(id); setAssetEntries(p => p.filter(e => e.id !== id)); }}
                  error={assetErr}
                />
              )}
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}

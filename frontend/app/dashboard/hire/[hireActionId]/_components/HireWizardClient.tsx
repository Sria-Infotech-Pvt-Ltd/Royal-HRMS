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
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import { validateHireStep, type HireSnapshot } from "@/lib/hireValidation";
import { useApiErrors } from "@/hooks/useApiErrors";
import { useHireDraftActions } from "@/hooks/useHireDraftActions";
import { parseApiError } from "@/lib/apiError";
import FieldError from "@/components/shared/FieldError";
import ConfirmModal from "@/components/ConfirmModal";
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
import { fieldsTheServerDidNotKeep } from "./savedDraftCheck";
import { shrinkImageForUpload } from "@/lib/shrinkImage";
import { changedDraftFields } from "./draftChanges";
import EmployeePhotoUpload from "./EmployeePhotoUpload";
import HireWizardSidebar from "./HireWizardSidebar";
import StepIssuesPanel from "./StepIssuesPanel";
import EmploymentStep, { EMPTY_EMPLOYMENT, type EmploymentDraft } from "./EmploymentStep";
import ApprovalAssignmentFields from "@/components/approvals/ApprovalAssignmentFields";
import BasicPayStep, { EMPTY_BASIC_PAY, type BasicPayDraft } from "./BasicPayStep";
import StatutoryAccountsStep, { EMPTY_STATUTORY, type StatutoryDraft } from "./StatutoryAccountsStep";
import DocumentsChecklistStep, { certificateTypeForLevel, REQUIRED_DOC_KEYS, REQUIRED_DOC_LABELS, EMPTY_VERIFICATION, type VerificationDraft, type HireDocument } from "./DocumentsChecklistStep";
import ReviewStep from "./ReviewStep";
import DateInput from "@/components/shared/DateInput";
import HireCompletionPanel from "./HireCompletionPanel";
import type { FaceIdHireSummary } from "@/types/faceId";
import { MARITAL_STATUS_OPTIONS } from "@/lib/maritalStatus";
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
} from "./_wizardData";

const APPROVER_FIELDS = ["reporting_manager_id", "l1_approver_id", "hr_id"] as const;

/** Just the messages that belong beside the reporting manager / L1 / L2 boxes. */
function approverErrorsOf(fieldErrors: Record<string, string>): Record<string, string> {
  const own: Record<string, string> = {};
  for (const key of APPROVER_FIELDS) if (fieldErrors[key]) own[key] = fieldErrors[key];
  return own;
}

export default function HireWizardClient({ hireActionId, onClose, onHired }: { hireActionId: string; onClose: () => void; onHired: () => void }) {
  const [action, setAction] = useState<HireActionData | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState(0);
  const [highestSaved, setHighestSaved] = useState(-1);
  const [stepErr, setStepErr] = useState("");
  // Turned on the first time Next is pressed with problems on the step. From then on the list of problems follows what is typed, so a
  // problem disappears the moment it is fixed.
  const [showIssues, setShowIssues] = useState(false);
  // Why a Suggest button did nothing (it had nothing to suggest from yet), shown under that field instead of failing silently.
  const [suggestHint, setSuggestHint] = useState<{ field: "display_name" | "place_of_birth"; text: string } | null>(null);
  const [autosaveStatus, setAutosaveStatus] = useState<"idle" | "saving" | "saved" | "warning" | "error">("idle");
  // Why the last autosave did not fully succeed (which field, or that the server could not be reached).
  const [autosaveMessage, setAutosaveMessage] = useState("");

  const [salutation, setSalutation] = useState("");
  const [firstName, setFirstName] = useState("");
  const [middleName, setMiddleName] = useState("");
  const [lastName, setLastName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [nationality, setNationality] = useState("Indian");
  const [placeOfBirth, setPlaceOfBirth] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  // Server messages for the two fields it checks for duplicates (email / mobile already belong to someone), shown inline.
  const [contactErrors, setContactErrors] = useState<{ email?: string; phone?: string }>({});
  // The server's message for a reporting manager / L1 / L2 choice it would not accept, shown beside that box.
  const [approverErrors, setApproverErrors] = useState<Record<string, string>>({});
  // True while a step is being saved on its way to the next one: the button shows it and ignores clicks.
  const [isNavigating, setIsNavigating] = useState(false);
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
  const { handleError: handleApiError } = useApiErrors();
  const draftActions = useHireDraftActions({ hireActionId, save: () => patchAction(buildFullDraftPayload()), onClose });
  const [documentToRemove, setDocumentToRemove] = useState<HireDocument | null>(null);
  const [verification, setVerification] = useState<VerificationDraft>(EMPTY_VERIFICATION);

  async function uploadDocument(documentType: string, file: File, entryRef?: string) {
    setDocUploading(entryRef ? `${documentType}:${entryRef}` : documentType);
    setDocError("");
    try {
      const formData = new FormData();
      formData.append("document_type", documentType);
      if (entryRef) formData.append("entry_ref", entryRef);
      // A big phone photo is shrunk first: on a slow upload line a 2 MB file took over the server's 60 seconds.
      const toSend = await shrinkImageForUpload(file);
      formData.append("file", toSend, toSend.name);
      const res = await clientApi.post<{ data: HireDocument }>(
        API.hireActions.documents(hireActionId), formData,
      );
      const saved = res.data.data;
      setDocuments(prev => [
        ...prev.filter(d => !(d.document_type === documentType && (d.entry_ref || "") === (entryRef || ""))),
        saved,
      ]);
    } catch (err: unknown) {
      // Shows the server's reason (wrong type, over 5 MB, too small ...) on whichever step the upload came from.
      setDocError(handleApiError(err, "Failed to upload document.").message);
    } finally {
      setDocUploading(null);
    }
  }

  // Asks first (the app's own modal, not a native confirm); removeDocument does the delete once confirmed.
  function deleteDocument(doc: HireDocument) {
    setDocumentToRemove(doc);
  }

  async function removeDocument(doc: HireDocument) {
    setDocumentToRemove(null);
    setDocError("");
    try {
      await clientApi.delete(API.hireActions.documentDetail(hireActionId, doc.id));
      setDocuments(prev => prev.filter(d => d.id !== doc.id));
    } catch (err: unknown) {
      const message = handleApiError(err, "Failed to remove document.").message;
      // The list on screen can be stale (the file was already removed, e.g. in another tab). Then
      // every View/Delete on that row got "not found" and the row could never go away. Re-read the
      // list from the server: if the document is already gone, the goal is met and there is no error.
      const fresh = await reloadDocuments();
      if (fresh && !fresh.some(d => d.id === doc.id)) return;
      setDocError(message);
    }
  }

  async function reloadDocuments(): Promise<HireDocument[] | null> {
    try {
      const res = await clientApi.get<{ data: HireDocument[] }>(API.hireActions.documents(hireActionId));
      const list = res.data?.data ?? [];
      setDocuments(list);
      return list;
    } catch {
      return null;
    }
  }

  // Step 5 (certificates / experience letters) has no alert of its own, so a failed upload there is shown above it.
  const educationErrorRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (docError) educationErrorRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [docError]);

  const [fieldConfig, setFieldConfig] = useState<OnboardingFieldConfigByStep>({});
  const [eduExpFieldConfig, setEduExpFieldConfig] = useState<EducationExperienceFieldConfigResponse>({ education: [], experience: [] });

  const [hiring, setHiring] = useState(false);
  const [completedHire, setCompletedHire] = useState<{ faceId: FaceIdHireSummary; code: string; reportingManager: { name: string | null; source: string } | null } | null>(null);
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
  // useLayoutEffect (synchronous, before the browser paints), not
  // useEffect — the same reset one frame later left a visible flash of
  // the previous step's scroll position (reported: "the Employment page
  // opens at the middle of the page").
  useLayoutEffect(() => {
    if (wizBodyRef.current) wizBodyRef.current.scrollTop = 0;
  }, [tab]);

  // "auto" next to Display name promised it would fill itself in — it
  // never did until the user manually clicked "+ Suggest" (QA report #40).
  // Only auto-fills while the user hasn't typed their own override.
  const displayNameTouchedRef = useRef(false);
  useEffect(() => {
    if (displayNameTouchedRef.current) return;
    setDisplayName([salutation, firstName, middleName, lastName].filter(Boolean).join(" "));
  }, [salutation, firstName, middleName, lastName]);

  // This used to be a sequential counter ("temp-1", "temp-2", ...). Even
  // moved into a useRef (persists across renders, unlike a plain local
  // variable that reset to 0 on every render — the very first version of
  // this bug), a small integer counter is still fragile: an effect that
  // runs more than once for the same component instance (React 18 Strict
  // Mode double-invokes effects with no cleanup in dev, exactly what the
  // load effect below is), or a draft resumed from a previous session,
  // can each independently produce "temp-1"/"temp-2"/etc., and two
  // separate counters landing on the same small number is exactly a
  // collision. A random UUID has no such shared-counter dependency at
  // all — regenerated logic in any order, in any number of effect runs,
  // never collides. Every id-matching operation in this file (Remove's
  // .filter(e => e.id !== id), field edits' .map(e => e.id === id ? ... :
  // e)) matches EVERY entry sharing an id, not just the one clicked —
  // which is what made a collision here show up as "editing entry #2
  // overwrote entry #1" / "removing one removed all of them".
  const nextTempId = () => `temp-${crypto.randomUUID()}`;

  // A resumed draft's entries carry ids that were already saved into
  // draft_data in a PREVIOUS session — this repairs any list that still
  // contains a duplicate id from before ids were made collision-proof
  // (or from Strict Mode's double effect run), by reassigning a fresh id
  // to any entry after the first one to use a given id.
  function repairTempIds<T extends { id: string }>(list: T[]): T[] {
    const seen = new Set<string>();
    return list.map(entry => {
      if (seen.has(entry.id)) return { ...entry, id: nextTempId() };
      seen.add(entry.id);
      return entry;
    });
  }

  useEffect(() => {
    Promise.all([
      clientApi.get<{ data: HireActionData }>(API.hireActions.detail(hireActionId)),
      clientApi.get<{ data: OnboardingFieldConfigByStep }>(API.onboarding.fieldConfig),
      clientApi.get<{ data: EducationExperienceFieldConfigResponse }>(API.onboarding.educationExperienceFieldConfig),
      clientApi.get<{ data: HireDocument[] }>(API.hireActions.documents(hireActionId)),
    ]).then(([a, fc, efc, docs]) => {
      const data = a.data.data;
      setAction(data);
      knownDraftRef.current = (data.draft_data as Record<string, unknown> | undefined) ?? {};
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
      if (savedContacts && savedContacts.length > 0) setEmergencyContacts(repairTempIds(savedContacts));
      setAddressExtras(x => ({ ...x, ...(d as Partial<AddressExtras>) }));
      setForm(f => ({ ...f, ...(d as Partial<ProfileForm>) }));
      setEmployment(e => ({
        ...e,
        ...(d as Partial<EmploymentDraft>),
        employment_type: data.employment_type,
      }));
      setBasicPay(b => ({ ...b, ...(d as Partial<BasicPayDraft>) }));
      setStatutory(s => ({ ...s, ...(d as Partial<StatutoryDraft>) }));
      // Family is repaired BEFORE nominees so that if a duplicate family id
      // gets reassigned, nominees referencing the OLD id (rare — only
      // possible for a draft already corrupted before this fix existed)
      // simply fail to match anything further rather than pointing at the
      // wrong person; there's no way to recover which nominee meant which
      // duplicate short of asking HR to re-pick it on this step.
      const repairedFamily = repairTempIds((d.family_entries as FamilyEntry[]) ?? []);
      // Same "one blank card already there" convention Emergency Contacts
      // already uses — an empty list showing only an explanatory line and
      // an Add button read as broken/incomplete; a blank starter card
      // makes the step look ready to fill in immediately, with the Add
      // button only needed for a SECOND (or later) entry.
      setFamilyEntries(repairedFamily.length > 0 ? repairedFamily : [
        { id: nextTempId(), name: "", relationship: "child", date_of_birth: "", gender: "", blood_group: "", is_dependent: false },
      ]);
      setNomineeEntries(repairTempIds((d.nominee_entries as NomineeEntry[]) ?? []));
      const repairedEducation = repairTempIds((d.education_entries as EducationEntry[]) ?? []);
      setEducationEntries(repairedEducation.length > 0 ? repairedEducation : [
        { id: nextTempId(), level: "", custom_level_label: "", institution: "", specialization: "", percentage: "", start_date: "", end_date: "", is_highest: false },
      ]);
      const repairedExperience = repairTempIds((d.experience_entries as ExperienceEntry[]) ?? []);
      setExperienceEntries(repairedExperience.length > 0 ? repairedExperience : [
        { id: nextTempId(), employer_name: "", designation: "", employment_type: "full_time", start_date: "", end_date: "", is_current: false, responsibilities: "", reason_for_leaving: "" },
      ]);
      setAssetEntries(repairTempIds((d.asset_entries as AssetEntry[]) ?? []));
      setCoreSkills(String(d.core_skills ?? ""));
      setCertifications(String(d.certifications ?? ""));
      // ONLY the three verification fields. This used to spread the whole saved draft into `verification`, and every save ends with
      // `...verification`, so a reopened draft's load-time values (family, company code, PAN, education ...) were written back over
      // whatever had been typed since: edits to a resumed draft silently never saved.
      setVerification(v => ({
        verification_status: String(d.verification_status ?? v.verification_status),
        verification_completed_on: String(d.verification_completed_on ?? v.verification_completed_on),
        verification_provider: String(d.verification_provider ?? v.verification_provider),
      }));
    }).finally(() => setLoading(false));
  }, [hireActionId]); // eslint-disable-line react-hooks/exhaustive-deps -- repairTempIds is redefined every render; only load once per hireActionId, same as the rest of this effect

  // Father's / mother's name are typed here on step 1, and they are the Father / Mother entries of the Family step too (the same
  // source EPF Form 2 reads), so typing one place fills the other. A change made on the Family step flows back here through the
  // effect below.
  function setParentName(kind: "father" | "mother", name: string) {
    if (kind === "father") setForm(f => ({ ...f, father_name: name }));
    else setIdentityExtras(x => ({ ...x, mother_name: name }));
    setFamilyEntries(list => {
      const existing = list.find(entry => entry.relationship === kind);
      if (existing) {
        // Clearing the name drops an entry that holds nothing else, so the Family step is not left with a nameless row.
        const holdsOtherDetails = !!(existing.date_of_birth || existing.blood_group || existing.is_dependent);
        if (!name.trim() && !holdsOtherDetails) return list.filter(entry => entry.id !== existing.id);
        return list.map(entry => (entry.id === existing.id ? { ...entry, name } : entry));
      }
      if (!name.trim()) return list;
      return [...list, { id: nextTempId(), name, relationship: kind, date_of_birth: "", gender: kind === "father" ? "male" : "female", blood_group: "", is_dependent: false }];
    });
  }

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

  // The draft as the server last told us it holds it. A save sends only what DIFFERS from this, never the whole form: a whole-form
  // save from a second open copy of the same draft (another tab, a stale window) used to overwrite newer typing with its own
  // empty boxes, which is how values "disappeared" and Hire then refused with "first name, last name ... are required".
  const knownDraftRef = useRef<Record<string, unknown>>({});
  async function patchAction(payload: Record<string, unknown>) {
    const known = knownDraftRef.current;
    const changed = changedDraftFields(payload, known);
    const { data } = await clientApi.patch<{ data: HireActionData }>(API.hireActions.detail(hireActionId), changed);
    knownDraftRef.current = (data.data.draft_data as Record<string, unknown> | undefined) ?? known;
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

  function validationSnapshot(): HireSnapshot {
    return {
      firstName, middleName, lastName, dateOfBirth: form.date_of_birth, gender: form.gender, nationality, email, phone,
      alternateMobile: identityExtras.alternate_mobile, employment, statutory, familyEntries, nomineeEntries, educationEntries,
      documentTypes: documents.map(d => d.document_type),
      requiredDocuments: REQUIRED_DOC_KEYS.map(key => ({ key, label: REQUIRED_DOC_LABELS[key] ?? key })),
      phoneDigits: nationalDigitCount, isPlausiblePhone: isPlausibleNationalNumber, now: new Date(),
    };
  }

  // Everything wrong on this step, once the person has tried to leave it. Recomputed every render, so it never goes stale.
  const issues = showIssues ? validateHireStep(tab, validationSnapshot()) : [];
  const issueMessages: Record<string, string> = Object.fromEntries(issues.map(issue => [issue.field, issue.message]));
  /** Marks a field's wrapper so the message can find it, and so it shows red while it is wrong. */
  const fieldProps = (field: string) => ({ className: "hw-field", "data-hw-field": field, "data-hw-invalid": issueMessages[field] ? ("true" as const) : undefined });

  /** Scrolls a field into view and puts the cursor in it. */
  function focusField(field: string) {
    const key = field === "nominees" ? "family" : field;
    const holder = wizBodyRef.current?.querySelector<HTMLElement>(`[data-hw-field="${key}"]`);
    if (!holder) { errorRef.current?.scrollIntoView({ behavior: "smooth", block: "center" }); return; }
    holder.scrollIntoView({ behavior: "smooth", block: "center" });
    const control = holder.querySelector<HTMLElement>("input:not([type=hidden]), select, textarea, button");
    window.setTimeout(() => control?.focus({ preventScroll: true }), 250);
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
      ...form,
      // Explicitly after the ...form spread: ProfileForm now also declares
      // salutation/display_name/nationality/place_of_birth/mother_name/
      // languages_known (added for the self-service wizard's own Identity
      // header, which tracks them through `form` instead) — this wizard
      // tracks its own separate state/extras for all of these instead,
      // which must win here, same reasoning for identityExtras/addressExtras
      // below as for the explicit scalars.
      ...identityExtras,
      ...addressExtras,
      salutation, first_name: firstName, middle_name: middleName, last_name: lastName,
      display_name: displayName, nationality, place_of_birth: placeOfBirth, email, phone,
      branch: employment.branch, work_email: employment.work_email,
      reporting_manager_id: employment.reporting_manager_id, dotted_line_manager_id: employment.dotted_line_manager_id,
      l1_approver_id: employment.l1_approver_id ?? "", hr_id: employment.hr_id ?? "",
      work_location: employment.work_location, work_mode: employment.work_mode,
      probation_period_months: employment.probation_period_months, notice_period_days: employment.notice_period_days,
      weekly_off_policy: employment.weekly_off_policy, working_hours_policy: employment.working_hours_policy,
      salary_structure: employment.salary_structure, annual_ctc: employment.annual_ctc,
      pay_group: employment.pay_group, attendance_scheme: employment.attendance_scheme,
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

  // Continuous autosave — debounced, fires ~1.2s after the last edit to ANY
  // field on the current step, independent of "Next"/step-jump saves (which
  // only fire on navigation and would otherwise lose whatever was typed if
  // the tab/browser closes mid-step). No dependency array: this effect must
  // see every render, since buildFullDraftPayload() reads dozens of pieces
  // of state and listing them all would be as fragile as missing one.
  // lastAttemptedRef starts at null so the very first run (right after the
  // initial GET finishes loading) primes the baseline instead of firing a
  // spurious save of data that was just loaded from the server, untouched.
  // Short on purpose: the wait after the last keystroke, and the longest a person typing without a pause waits. Leaving a field
  // saves at once (see the focusout listener below), so these only matter while typing.
  const AUTOSAVE_DELAY_MS = 400;
  const AUTOSAVE_MAX_WAIT_MS = 1500;
  // Saves go one after another, never side by side: two requests in flight can land out of order and a stale full-form snapshot
  // would overwrite a newer one on the server.
  const saveChainRef = useRef<Promise<unknown>>(Promise.resolve());
  const autosaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // The last snapshot an autosave was SENT for, whether or not it succeeded. A snapshot is never re-sent on its own: this
  // effect re-runs on every render, so without this a refused save re-rendered, re-sent and looped (it filled the log with
  // identical 400s). The next edit, or the Retry button, sends again.
  const lastAttemptedRef = useRef<string | null>(null);
  // The newest snapshot of the form, kept so a save can be forced at any moment (closing the wizard, hiding the tab).
  const latestPayloadRef = useRef<Record<string, unknown> | null>(null);
  // When the form first became unsaved; a person typing without a pause must still be saved every few seconds.
  const dirtySinceRef = useRef<number | null>(null);
  const flushAutosaveRef = useRef<() => void>(() => {});

  function sendAutosave(payload: Record<string, unknown>, serialized: string) {
    if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = null;
    dirtySinceRef.current = null;
    lastAttemptedRef.current = serialized;
    setAutosaveStatus("saving");
    setAutosaveMessage("");
    const attempt = saveChainRef.current.catch(() => undefined).then(() => patchAction(payload));
    saveChainRef.current = attempt;
    attempt
      .then(result => {
        // Duplicate email/mobile: the draft IS saved, but the person must hear about it (and cannot move on until fixed).
        const blocking = result.warnings?.find(w => w.severity === "error");
        setApproverErrors({});
        setAutosaveStatus(blocking ? "warning" : "saved");
        setAutosaveMessage(blocking ? `${blocking.message} Your changes are saved.` : "");
      })
      .catch((e: unknown) => {
        const parsed = parseApiError(e, "Could not reach the server.");
        // A 400 means the server refused only the fields named in the message and still saved the rest of the form.
        const partlySaved = parsed.status === 400 && Object.keys(parsed.fieldErrors).length > 0;
        setApproverErrors(approverErrorsOf(parsed.fieldErrors));
        setAutosaveStatus("error");
        setAutosaveMessage(partlySaved
          ? `Not saved: ${parsed.message} Everything else was saved.`
          : `${parsed.message} Your entries are still on this screen but are not saved yet.`);
      });
  }

  // Send anything not yet sent, right now (no waiting for the pause in typing).
  flushAutosaveRef.current = () => {
    const payload = latestPayloadRef.current;
    if (!payload || lastAttemptedRef.current === null) return;
    const serialized = JSON.stringify(payload);
    if (serialized !== lastAttemptedRef.current) sendAutosave(payload, serialized);
  };

  useEffect(() => {
    if (loading) return;
    const payload = buildFullDraftPayload();
    latestPayloadRef.current = payload;
    const serialized = JSON.stringify(payload);
    if (lastAttemptedRef.current === null) {
      lastAttemptedRef.current = serialized;
      return;
    }
    if (serialized === lastAttemptedRef.current) {
      dirtySinceRef.current = null;
      return;
    }

    // No cleanup on purpose: a timer cancelled by every re-render could be cancelled forever while someone types or while
    // the screen keeps updating. The wait is capped (AUTOSAVE_MAX_WAIT_MS) and the pending save is flushed on leaving.
    const now = Date.now();
    if (dirtySinceRef.current === null) dirtySinceRef.current = now;
    const delay = Math.max(0, Math.min(AUTOSAVE_DELAY_MS, AUTOSAVE_MAX_WAIT_MS - (now - dirtySinceRef.current)));
    if (autosaveTimerRef.current) clearTimeout(autosaveTimerRef.current);
    autosaveTimerRef.current = setTimeout(() => sendAutosave(payload, serialized), delay);
  });

  // Leaving (closing the wizard, hiding or closing the tab) must never lose what was typed in the last moment.
  useEffect(() => {
    const flushNow = () => flushAutosaveRef.current();
    const flushWhenHidden = () => { if (document.visibilityState === "hidden") flushNow(); };
    const warnIfUnsaved = (event: BeforeUnloadEvent) => {
      const payload = latestPayloadRef.current;
      if (payload && lastAttemptedRef.current !== null && JSON.stringify(payload) !== lastAttemptedRef.current) {
        flushNow();
        event.preventDefault();
      }
    };
    document.addEventListener("visibilitychange", flushWhenHidden);
    document.addEventListener("focusout", flushNow);   // leaving a field (Tab or click elsewhere) saves right away
    window.addEventListener("pagehide", flushNow);
    window.addEventListener("beforeunload", warnIfUnsaved);
    return () => {
      document.removeEventListener("visibilitychange", flushWhenHidden);
      document.removeEventListener("focusout", flushNow);
      window.removeEventListener("pagehide", flushNow);
      window.removeEventListener("beforeunload", warnIfUnsaved);
      flushNow();
    };
  }, []);

  function retryAutosave() {
    lastAttemptedRef.current = null;  // forget the failed snapshot so the effect above sends the current form again
    setAutosaveStatus("idle");
    setAutosaveMessage("");
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
    setShowIssues(false);
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
    if (isNavigating) return;  // a second click while the step is saving must not save (or advance) twice
    const found = validateHireStep(tab, validationSnapshot());
    if (found.length > 0) {
      setShowIssues(true);
      setStepErr("");
      // After the panel has drawn, take the person to the first field that needs attention.
      window.setTimeout(() => focusField(found[0].field), 50);
      return;
    }
    setShowIssues(false);
    setStepErr("");
    setIsNavigating(true);
    try {
      const saved = await patchAction(buildFullDraftPayload());
      setApproverErrors({});
      // Saving never fails because of a duplicate any more, but the person still cannot move on with someone else's email.
      const duplicate = saved.warnings?.find(w => w.severity === "error");
      if (duplicate) {
        setContactErrors({ email: duplicate.field === "email" ? duplicate.message : undefined, phone: duplicate.field === "phone" ? duplicate.message : undefined });
        setStepErr(`${duplicate.message} Your changes are saved; change it to continue.`);
        return;
      }
      setHighestSaved(h => Math.max(h, tab));
      setTab(t => Math.min(t + 1, STEPS.length - 1));
    } catch (e) {
      const parsed = parseApiError(e, "Could not save this step.");
      setContactErrors({ email: parsed.fieldErrors.email, phone: parsed.fieldErrors.phone });
      setApproverErrors(approverErrorsOf(parsed.fieldErrors));
      setStepErr(parsed.message);
    } finally {
      setIsNavigating(false);
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
      // A failed save is NEVER ignored here: hiring from a draft the server does not hold would be refused anyway,
      // with a message that blames the wrong thing.
      try {
        await saveChainRef.current.catch(() => undefined);   // let any autosave already on its way finish first, so it cannot land after this one
        const payload = buildFullDraftPayload();
        const held = await patchAction(payload);
        // The server answered "saved", but is its copy really what is on screen? If not, say which fields, and do not hire.
        const notKept = fieldsTheServerDidNotKeep(payload, held.draft_data);
        if (notKept.length > 0) {
          setHireError(`The server did not keep: ${notKept.join(", ")}. Nothing was hired. Open that step, re-enter it, wait for "Saved", and press Hire again.`);
          return;
        }
      } catch (saveError) {
        const parsed = parseApiError(saveError, "Could not reach the server.");
        setHireError(`Your entries could not be saved, so nothing was hired. ${parsed.message}`);
        return;
      }
      const response = await clientApi.post<{ data?: { face_id?: FaceIdHireSummary; reserved_employee_id?: string; reporting_manager?: { name: string | null; source: string } } }>(API.hireActions.complete(hireActionId));
      const faceId = response.data?.data?.face_id;
      // Show the completion screen (with the Face ID next step); closing the wizard happens from there.
      if (faceId) setCompletedHire({ faceId, code: response.data?.data?.reserved_employee_id ?? "", reportingManager: response.data?.data?.reporting_manager ?? null });
      else onHired();
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
      !employment.employment_type && "Employment type",
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
    employment.employment_type, employment.branch,
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

  if (completedHire) {
    return (
      <HireCompletionPanel
        employeeName={[firstName, lastName].filter(Boolean).join(" ") || "The new hire"}
        employeeCode={completedHire.code}
        faceId={completedHire.faceId}
        reportingManager={completedHire.reportingManager}
        onDone={onHired}
      />
    );
  }

  return (
    <>
    <Modal
      title={
        <div className="hw-head">
          <div className="hw-title">Hire an <em>employee</em></div>
          <div className="hw-meta">
            <span className="hw-chip is-brand"><i className="ti ti-user-plus" /> Hire</span>
            {action.reason_display && <span className="hw-chip">{action.reason_display}</span>}
            <span className="hw-chip"><i className="ti ti-calendar" /> Effective {formatDate(action.effective_from)}</span>
            {action.position_title && <span className="hw-chip"><i className="ti ti-briefcase" /> {action.position_title}</span>}
          </div>
        </div>
      }
      onClose={onClose}
      size="lg"
      maxWidth={1360}
      scrollBody
      // The sidebar (step list) and the step content each scroll
      // independently within this bounded modal — see .wiz/.wiz-nav/.wiz-body
      // in aira-theme.css. Without this override, scrollBody's default
      // makes modal-body itself the one shared scroll container, dragging
      // the step list along with the content instead of leaving it in place.
      bodyStyle={{ padding: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}
      footer={tab < 8 ? (
        <div className="hw-foot">
          <div className="hw-progress">
            <div className="hw-progress-top"><strong>{progressPct}% complete</strong><span>Step {tab + 1} of {STEPS.length}</span></div>
            <div className="hw-progress-bar" role="progressbar" aria-valuenow={progressPct} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${progressPct}%` }} /></div>
          </div>
          <div className="hw-actions">
            <button type="button" onClick={draftActions.openDiscard} className="hw-link is-danger"><i className="ti ti-trash" /> Discard</button>
            <button type="button" onClick={draftActions.saveAndExit} disabled={draftActions.isSaving} className="hw-link"><i className="ti ti-door-exit" /> Save &amp; exit</button>
            <button type="button" onClick={draftActions.saveDraft} disabled={draftActions.isSaving} className="hw-link"><i className="ti ti-device-floppy" /> Save draft</button>
            <button type="button" onClick={() => setShowScanFill(true)} className="hw-link"><i className="ti ti-scan" /> Scan &amp; fill</button>
            <span className="hw-sep" aria-hidden="true" />
            {tab > 0 && <button type="button" onClick={() => goToStep(Math.max(0, tab - 1))} className="btn btn-ghost hw-btn"><i className="ti ti-arrow-left" /> Back</button>}
            <button type="button" onClick={handleNext} disabled={isNavigating} className="btn btn-filled hw-btn">
              {isNavigating ? <><i className="ti ti-loader-2 spin" /> Saving…</> : <>Next <i className="ti ti-arrow-right" /></>}
            </button>
          </div>
        </div>
      ) : (
        <button onClick={onClose} className="btn btn-ghost">Close</button>
      )}
    >
      <div className="wiz hire-wiz">
        <HireWizardSidebar steps={STEPS} currentStep={tab} highestSaved={highestSaved} progressPct={progressPct}
          onStepClick={goToStep} missingByStep={missingByStep} />

        <div className="wiz-main">
          <div className="stephead">
            <div>
              <h3>{STEPS[tab].label.split(" ").slice(0, -1).join(" ")} <em className="hl">{STEPS[tab].label.split(" ").slice(-1)}</em></h3>
              <p>{STEPS[tab].sub}</p>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              {autosaveStatus !== "idle" && (
                <span className="text-[11.5px]" style={{ color: autosaveStatus === "error" ? "var(--error)" : "var(--on-variant)", display: "flex", alignItems: "center", gap: 4 }}>
                  {autosaveStatus === "saving" && <><i className="ti ti-loader-2 animate-spin" /> Saving…</>}
                  {autosaveStatus === "saved" && <><i className="ti ti-circle-check" /> All changes saved</>}
                  {autosaveStatus === "warning" && <><i className="ti ti-alert-circle" /> Saved, with a problem</>}
                  {autosaveStatus === "error" && <><i className="ti ti-alert-circle" /> Autosave problem</>}
                  {(autosaveStatus === "error" || autosaveStatus === "warning") && autosaveMessage && (
                    <span role="alert" title={autosaveMessage} style={{ maxWidth: 360, whiteSpace: "normal" }}>{autosaveMessage}</span>
                  )}
                  {autosaveStatus === "error" && (
                    <button type="button" className="btn btn-ghost" style={{ padding: "2px 8px", fontSize: 11.5 }} onClick={retryAutosave}>Retry</button>
                  )}
                </span>
              )}
              <div className="stepcount">{String(tab + 1).padStart(2, "0")} / {String(STEPS.length).padStart(2, "0")}</div>
            </div>
          </div>

        <div className="wiz-body" ref={wizBodyRef}>
          <StepIssuesPanel
            ref={errorRef}
            issues={issues}
            serverMessage={stepErr}
            autosaveProblem={autosaveStatus === "error" || autosaveStatus === "warning" ? (autosaveMessage || "Autosave did not complete.") : ""}
            onRetryAutosave={retryAutosave}
            onGoToField={focusField}
          />

          {tab === 0 && (
            <div className="mstep on">
              <EmployeePhotoUpload hireActionId={hireActionId} photoUrl={photoUrl} onPhotoChange={setPhotoUrl} />

              <div className="hw-section">Identity</div>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Salutation</label>
                  <select value={salutation} onChange={e => setSalutation(e.target.value)} className="field-input field-select">
                    <option value="">Select</option>
                    {["Mr.", "Ms.", "Mrs.", "Dr."].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div {...fieldProps("first_name")}>
                  <label className="block text-[12.5px] font-semibold mb-1.5">First name <span style={{ color: "var(--error)" }}>*</span></label>
                  <input value={firstName} onChange={e => setFirstName(e.target.value)} placeholder="e.g. Rahul" className="field-input" />
                  <FieldError message={issueMessages.first_name} />
                </div>
                <div {...fieldProps("middle_name")}>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Middle name</label>
                  <input value={middleName} onChange={e => setMiddleName(e.target.value)} placeholder="e.g. Kumar" className="field-input" />
                  <FieldError message={issueMessages.middle_name} />
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 mb-5">
                <div {...fieldProps("last_name")}>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Last name <span style={{ color: "var(--error)" }}>*</span></label>
                  <input value={lastName} onChange={e => setLastName(e.target.value)} placeholder="e.g. Sharma" className="field-input" />
                  <FieldError message={issueMessages.last_name} />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Display name <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>auto</span></label>
                  <div className="flex gap-2">
                    <input value={displayName} onChange={e => { displayNameTouchedRef.current = true; setDisplayName(e.target.value); }} placeholder="Generated from name" className="field-input" />
                    <button type="button" className="hw-suggest" onClick={() => {
                      const suggestion = [salutation, firstName, middleName, lastName].filter(Boolean).join(" ");
                      if (!firstName.trim() && !lastName.trim()) { setSuggestHint({ field: "display_name", text: "Type the first and last name first. Suggest builds the display name from them." }); return; }
                      displayNameTouchedRef.current = false;
                      setSuggestHint(null);
                      setDisplayName(suggestion);
                    }}><i className="ti ti-wand" /> Suggest</button>
                  </div>
                  {suggestHint?.field === "display_name"
                    ? <p className="hint bad" role="status" style={{ marginTop: 4 }}>{suggestHint.text}</p>
                    : <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Shown across the app and in approvals.</p>}
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Employee number <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>auto</span></label>
                  <div className="field-input" style={{ background: "var(--bg-low)", color: action.reserved_employee_id ? "var(--on-bg)" : "var(--on-variant)" }}>
                    {action.reserved_employee_id || "Assigned on employment type"}
                  </div>
                  <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Each employment type has its own series — set the type in step 2 and the number is reserved here.</p>
                </div>
              </div>

              <div className="hw-section">Basic details</div>
              <div className="grid grid-cols-3 gap-3 mb-3">
                <div {...fieldProps("date_of_birth")}>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Date of birth <span style={{ color: "var(--error)" }}>*</span></label>
                  <DateInput value={form.date_of_birth} onChange={iso => setForm(f => ({ ...f, date_of_birth: iso }))} className="field-input" separator="-" />
                  <FieldError message={issueMessages.date_of_birth} />
                </div>
                <div {...fieldProps("gender")}>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Gender <span style={{ color: "var(--error)" }}>*</span></label>
                  <select value={form.gender} onChange={e => setForm(f => ({ ...f, gender: e.target.value }))} className="field-input field-select">
                    <option value="">Select</option>
                    <option value="male">Male</option><option value="female">Female</option><option value="other">Other</option>
                  </select>
                  <FieldError message={issueMessages.gender} />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Blood group</label>
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
                    {MARITAL_STATUS_OPTIONS.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </div>
                <div {...fieldProps("nationality")}>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Nationality <span style={{ color: "var(--error)" }}>*</span></label>
                  <CountrySelect value={nationality} onChange={setNationality} mode="demonym" />
                  <FieldError message={issueMessages.nationality} />
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Place of birth</label>
                  <div className="flex gap-2">
                    <input value={placeOfBirth} onChange={e => setPlaceOfBirth(e.target.value)} placeholder="City / town" className="field-input" />
                    <button type="button" className="hw-suggest" onClick={() => {
                      const place = form.current_village || form.current_district;
                      if (!place) { setSuggestHint({ field: "place_of_birth", text: "Fill in the city or district of the current address (further down) first. Suggest uses it." }); return; }
                      setSuggestHint(null);
                      setPlaceOfBirth(place);
                    }}><i className="ti ti-wand" /> Suggest</button>
                  </div>
                  {suggestHint?.field === "place_of_birth" && <p className="hint bad" role="status" style={{ marginTop: 4 }}>{suggestHint.text}</p>}
                </div>
              </div>
              <div className="grid grid-cols-3 gap-3 mb-5">
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Father&apos;s name</label>
                  <input value={form.father_name} onChange={e => setParentName("father", e.target.value)} placeholder="e.g. Suresh Sharma" className="field-input" />
                  <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Also added to Family &amp; nomination.</p>
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Mother&apos;s name</label>
                  <input value={identityExtras.mother_name} onChange={e => setParentName("mother", e.target.value)} placeholder="e.g. Sunita Sharma" className="field-input" />
                  <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Required on EPF Form 2. Also added to Family &amp; nomination.</p>
                </div>
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Languages known</label>
                  <LanguagesSelect value={identityExtras.languages_known}
                    onChange={v => setIdentityExtras(x => ({ ...x, languages_known: v }))} />
                </div>
              </div>

              <div className="hw-section">Statutory declarations</div>
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

              <div className="hw-section">Voluntary self-declaration</div>
              <p className="text-[11.5px] mb-2" style={{ color: "var(--on-variant)" }}>
                Not required of a private employer. Collect only where a government, PSU or aided establishment must report it, or a state incentive scheme requires it. Self-declared, and hidden from reporting managers.
              </p>
              <div className="grid grid-cols-3 gap-3 mb-5">
                <div>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Category / community</label>
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

              <div className="hw-section">Contact</div>
              <div className="grid grid-cols-3 gap-3 mb-5">
                <div {...fieldProps("email")}>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Personal email <span style={{ color: "var(--error)" }}>*</span></label>
                  <input type="email" value={email} onChange={e => { setEmail(e.target.value); setContactErrors(c => ({ ...c, email: undefined })); }} placeholder="name@example.com" className="field-input" />
                  <FieldError message={contactErrors.email ?? issueMessages.email} />
                </div>
                <div {...fieldProps("phone")}>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Mobile number <span style={{ color: "var(--error)" }}>*</span></label>
                  <PhoneInput value={phone} onChange={value => { setPhone(value); setContactErrors(c => ({ ...c, phone: undefined })); }} placeholder="90000 00000" />
                  <FieldError message={contactErrors.phone ?? issueMessages.phone} />
                </div>
                <div {...fieldProps("alternate_mobile")}>
                  <label className="block text-[12.5px] font-semibold mb-1.5">Alternate mobile</label>
                  <PhoneInput value={identityExtras.alternate_mobile}
                    onChange={v => setIdentityExtras(x => ({ ...x, alternate_mobile: v }))}
                    placeholder="Optional" />
                  <FieldError message={issueMessages.alternate_mobile} />
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
              value={employment} onChange={setEmployment} onSetEmploymentType={setEmploymentType} errors={issueMessages}
              reservedEmployeeId={action.reserved_employee_id}
              positionTitle={action.position_title} orgUnitName={action.org_unit_name} grade={action.grade}
              costCenter=""
              approverSection={
                <ApprovalAssignmentFields
                  value={{ reporting_manager_id: employment.reporting_manager_id, l1_approver_id: employment.l1_approver_id ?? "", hr_id: employment.hr_id ?? "" }}
                  onChange={next => setEmployment(e => ({ ...e, ...next }))}
                  errors={approverErrors}
                />
              }
            />
          )}

          {tab === 2 && (
            <BasicPayStep annualCtc={employment.annual_ctc} salaryStructureId={employment.salary_structure}
              branchName={employment.branch} value={basicPay} onChange={setBasicPay} />
          )}

          {tab === 3 && (
            <StatutoryAccountsStep
              value={statutory} onChange={setStatutory} errors={issueMessages}
              documents={documents}
            />
          )}

          {tab === 4 && (
            <div {...fieldProps("family")}>
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
            </div>
          )}

          {tab === 5 && (
            <div className="mstep on">
              {docError && (
                <div ref={educationErrorRef} className="alert alert-error mb-16"><i className="ti ti-alert-circle" /><div>{docError}</div></div>
              )}
              <div {...fieldProps("education")}>
              <FieldError message={issueMessages.education} />
              <EducationChecklist
                entries={educationEntries} fieldConfig={eduExpFieldConfig.education}
                onAdd={() => setEducationEntries(p => [...p, { id: nextTempId(), level: "", custom_level_label: "", institution: "", specialization: "", percentage: "", start_date: "", end_date: "", is_highest: false }])}
                onFieldChange={(id, field, value) => setEducationEntries(p => p.map(e => e.id === id ? { ...e, [field]: value } : e))}
                onRemove={id => setEducationEntries(p => p.filter(e => e.id !== id))}
                onSetHighest={id => setEducationEntries(p => p.map(e => ({ ...e, is_highest: e.id === id })))}
                documents={documents} uploading={docUploading} onUploadDoc={uploadDocument} onDeleteDoc={deleteDocument} certificateTypeFor={certificateTypeForLevel}
                error={null}
              />
              </div>
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
                  <label>Core skills</label>
                  <input value={coreSkills} onChange={e => setCoreSkills(e.target.value)} placeholder="e.g. React, payroll operations, team leadership" className="finput" />
                  <div className="hint">Use comma-separated skills; keep this relevant to the role.</div>
                </div>
                <div className="f">
                  <label>Certifications</label>
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
              missing={issueMessages}
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

    {draftActions.isDiscardOpen && (
      <ConfirmModal
        title="Discard this draft?"
        body="The draft and everything entered so far will be deleted, and its reserved employee number is released. This cannot be undone. To keep it, use Save & exit instead."
        confirmLabel="Discard draft"
        danger
        saving={draftActions.isDiscarding}
        onConfirm={draftActions.confirmDiscard}
        onCancel={draftActions.closeDiscard}
      />
    )}
    {documentToRemove && (
      <ConfirmModal
        title="Remove this document?"
        body="You will need to upload it again before hiring."
        confirmLabel="Remove"
        danger
        onConfirm={() => removeDocument(documentToRemove)}
        onCancel={() => setDocumentToRemove(null)}
      />
    )}

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

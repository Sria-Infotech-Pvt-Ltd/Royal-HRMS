"use client";

import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import type { OnboardingFieldConfigByStep, CustomFieldFileValue, OnboardingSection, EducationExperienceFieldConfigResponse } from "@/types/onboardingFieldConfig";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import type { ProfileForm } from "@/app/onboarding/_types";
import DynamicStepFields from "@/app/onboarding/_components/DynamicStepFields";
import TabDocuments, { type UploadedDoc } from "@/app/onboarding/_components/TabDocuments";
import StepIndicator from "@/app/onboarding/_components/StepIndicator";
import BasicDetailsCard, { type BasicDetails } from "@/app/onboarding/_components/BasicDetailsCard";
import EducationChecklist, { type EducationEntry } from "@/app/onboarding/_components/EducationChecklist";
import ExperienceList, { type ExperienceEntry } from "@/app/onboarding/_components/ExperienceList";
import FamilyNominationStep, { type FamilyEntry, type NomineeEntry } from "@/app/onboarding/_components/FamilyNominationStep";
import AssetsList, { type AssetEntry } from "@/app/onboarding/_components/AssetsList";
import { EMPTY, PAN_RE, BUILTIN_STEPS, DOCUMENTS_STEP, type WizardStep } from "./_wizardSteps";

// HR/Admin-side onboarding wizard — fills in an employee's onboarding profile
// on their behalf (walk-in hires, or anyone who can't complete it themselves).
// Reuses the exact same step-field components as the self-service wizard
// (app/onboarding/page.tsx); the container logic here is deliberately
// simpler — no step-locking (HR can jump freely), no login/logout chrome,
// and Face ID is handled by pointing at the existing Face ID Registrations
// admin page rather than an inline capture flow (that's an in-person capture
// UX, not something to half-build here).

export default function HREmployeeOnboardingPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const canEdit    = usePermission("onboarding.edit");
  const canApprove = usePermission("onboarding.approve");
  // Basic Details reuses PUT /employees/<id>/ (Edit Employee's own endpoint)
  // directly, so it's gated on the same permission that endpoint itself
  // checks (employees.edit), not onboarding.edit.
  const canEditBasicDetails = usePermission("employees.edit");

  const [employeeUuid, setEmployeeUuid] = useState<string>("");
  const [employeeName, setEmployeeName] = useState<string>("");
  const [basicDetails, setBasicDetails] = useState<BasicDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  const [tab, setTab] = useState(0);
  const [highestSaved, setHighestSaved] = useState(-1);
  // Raw step numbers the backend already considers complete (GET
  // /onboarding/employees/<id>/'s own `completed_steps`) — restores
  // unlocked progress when reopening this wizard partway through an
  // employee's onboarding, instead of resetting to only Step 1 unlocked
  // every time regardless of what HR already saved in an earlier session.
  const [completedStepNumbers, setCompletedStepNumbers] = useState<number[]>([]);
  const [form, setForm] = useState<ProfileForm>(EMPTY);
  const [customValues, setCustomValues] = useState<Record<string, string>>({});
  const [docs, setDocs] = useState<UploadedDoc[]>([]);
  const [customFileValues, setCustomFileValues] = useState<CustomFieldFileValue[]>([]);
  const [fieldConfig, setFieldConfig] = useState<OnboardingFieldConfigByStep>({});
  const [eduExpFieldConfig, setEduExpFieldConfig] = useState<EducationExperienceFieldConfigResponse>({ education: [], experience: [] });
  // HR-created custom sections beyond the 4 built-ins — see OnboardingSection.
  const [customSections, setCustomSections] = useState<OnboardingSection[]>([]);
  const steps = useMemo<WizardStep[]>(() => {
    // OnboardingSection also carries label/icon-override rows for the 4
    // built-ins (steps 0-3, renameable from Settings) — this wizard keeps
    // its own hardcoded built-in labels regardless, so only step 5+ rows
    // (real custom sections) render as extra tabs here.
    const customSteps: WizardStep[] = customSections
      .filter(s => s.is_active && s.step > 4)
      .slice()
      .sort((a, b) => a.order - b.order || a.label.localeCompare(b.label))
      .map(s => ({ step: s.step, label: s.label, shortLabel: s.label, icon: s.icon, kind: "fields" }));
    return [...BUILTIN_STEPS, ...customSteps, DOCUMENTS_STEP];
  }, [customSections]);

  // Contiguous PREFIX of "done" steps starting from Step 1 (matches the
  // same one-at-a-time gate StepIndicator itself enforces) — Experience
  // always counts as passed, same as saveSection()'s own "experience"
  // branch always returning true (it has no required fields). Only ever
  // raises highestSaved, never lowers it.
  useEffect(() => {
    let highest = -1;
    for (let i = 0; i < steps.length; i++) {
      const passes = steps[i].kind === "experience" || steps[i].kind === "family-nomination" || steps[i].kind === "assets" || completedStepNumbers.includes(steps[i].step);
      if (!passes) break;
      highest = i;
    }
    if (highest >= 0) setHighestSaved(prev => Math.max(prev, highest));
  }, [steps, completedStepNumbers]);
  const [docTypeConfig, setDocTypeConfig] = useState<DocumentTypeConfig[]>([]);
  const docTypes = docTypeConfig.filter(t => t.visible).sort((a, b) => a.order - b.order);
  const uploadedTypes = new Set(docs.map(d => d.document_type));

  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);
  const [uploadingFileKey, setUploadingFileKey] = useState<string | null>(null);
  const [fileUploadError, setFileUploadError] = useState<string | null>(null);
  const [panErr, setPanErr] = useState<string | null>(null);
  const [panSaving, setPanSaving] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [approving, setApproving] = useState(false);
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // ── Load employee + onboarding data ─────────────────────────────────────
  useEffect(() => {
    clientApi.get(API.employees.detail(id)).then(r => {
      const raw = r.data?.data;
      if (!raw) { setNotFound(true); return; }
      setEmployeeUuid(raw.uuid);
      setEmployeeName(raw.full_name || raw.email || id);
      setBasicDetails({
        full_name:       raw.full_name ?? "",
        email:           raw.email ?? "",
        phone:           raw.phone ?? "",
        employee_type:   raw.employee_type ?? "",
        date_of_joining: raw.date_of_joining ?? "",
        role:            raw.role ?? "",
        role_display:    raw.role_display ?? "",
        branch:          raw.branch ?? "",
        department:      raw.department ?? "",
        designation:     raw.designation ?? "",
        org_unit_name:   raw.org_unit_name ?? null,
      });
    }).catch(() => setNotFound(true)).finally(() => setLoading(false));
  }, [id]);

  // Education and Experience are both genuine add/remove lists — see
  // BUILTIN_STEPS' comment above. Add/edit/remove is purely local state;
  // nothing reaches the server until the step's own Save & Continue
  // reconciles the whole list at once (see saveSection()'s "education"/
  // "experience" branches below) — deletedEducationIdsRef/
  // deletedExperienceIdsRef track which real (non-temp) ids were removed
  // locally so reconciliation knows what to DELETE server-side.
  const [educationEntries, setEducationEntries] = useState<EducationEntry[]>([]);
  const [educationErr, setEducationErr] = useState<string | null>(null);
  const tempEducationIdRef = useRef(0);
  const deletedEducationIdsRef = useRef<Set<string>>(new Set());
  const [experienceEntries, setExperienceEntries] = useState<ExperienceEntry[]>([]);
  const [totalExperienceYears, setTotalExperienceYears] = useState<string | null>(null);
  const [experienceErr, setExperienceErr] = useState<string | null>(null);
  const tempExperienceIdRef = useRef(0);
  const deletedExperienceIdsRef = useRef<Set<string>>(new Set());

  // Family/Nominee/Asset — same bulk-reconciliation convention as
  // Education/Experience above. Family is always saved before Nominees in
  // saveFamilyNominationEntries() so a nominee referencing a not-yet-created
  // (`temp-`) family member gets translated to the real id via idMap before
  // it's sent — see that function's own comment.
  const [familyEntries, setFamilyEntries] = useState<FamilyEntry[]>([]);
  const [nomineeEntries, setNomineeEntries] = useState<NomineeEntry[]>([]);
  const [familyNominationErr, setFamilyNominationErr] = useState<string | null>(null);
  const tempFamilyIdRef = useRef(0);
  const tempNomineeIdRef = useRef(0);
  const deletedFamilyIdsRef = useRef<Set<string>>(new Set());
  const deletedNomineeIdsRef = useRef<Set<string>>(new Set());

  const [assetEntries, setAssetEntries] = useState<AssetEntry[]>([]);
  const [assetErr, setAssetErr] = useState<string | null>(null);
  const tempAssetIdRef = useRef(0);
  const deletedAssetIdsRef = useRef<Set<string>>(new Set());

  // Total Experience (Years) is derived server-side from the experience
  // entries themselves (see backend's _compute_total_experience_years) —
  // refetched after every successful saveExperienceEntries() so the
  // read-only display in ExperienceList stays current.
  const refetchTotalExperience = useCallback(() => {
    if (!employeeUuid) return;
    clientApi.get<{ data: { total_experience_years: number | null } }>(API.onboarding.employees.experienceSummary(employeeUuid)).then(r => {
      const v = r.data?.data?.total_experience_years;
      setTotalExperienceYears(v != null ? String(v) : null);
    }).catch(() => {});
  }, [employeeUuid]);

  useEffect(() => {
    if (!employeeUuid) return;
    clientApi.get(API.onboarding.employees.summary(employeeUuid)).then(r => {
      const d = r.data?.data ?? {};
      setForm(prev => ({ ...prev, ...Object.fromEntries(Object.keys(EMPTY).map(k => [
        k,
        k === "permanent_same_as_current" ? String(Boolean(d[k])) : (d[k] ?? ""),
      ])) }));
      setCustomValues(Object.fromEntries(
        Object.entries(d.custom_field_values ?? {}).map(([k, v]) => [k, v == null ? "" : String(v)]),
      ));
      setCompletedStepNumbers(d.completed_steps ?? []);
    }).catch(() => {});
    clientApi.get(API.onboarding.employees.documents(employeeUuid)).then(r => {
      setDocs(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get(API.onboarding.employees.customFileFields(employeeUuid)).then(r => {
      setCustomFileValues(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get(API.onboarding.fieldConfig).then(r => setFieldConfig(r.data?.data ?? {})).catch(() => {});
    clientApi.get<{ data: EducationExperienceFieldConfigResponse }>(API.onboarding.educationExperienceFieldConfig).then(r => {
      setEduExpFieldConfig(r.data?.data ?? { education: [], experience: [] });
    }).catch(() => {});
    clientApi.get(API.onboarding.sections).then(r => setCustomSections(r.data?.data ?? [])).catch(() => {});
    clientApi.get(API.onboarding.documentTypeConfig).then(r => setDocTypeConfig(r.data?.data ?? [])).catch(() => {});
    clientApi.get<{ data: EducationEntry[] }>(API.onboarding.employees.education(employeeUuid)).then(r => {
      setEducationEntries(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get<{ data: ExperienceEntry[] }>(API.onboarding.employees.experience(employeeUuid)).then(r => {
      setExperienceEntries(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get<{ data: FamilyEntry[] }>(API.onboarding.employees.family(employeeUuid)).then(r => {
      setFamilyEntries(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get<{ data: NomineeEntry[] }>(API.onboarding.employees.nominees(employeeUuid)).then(r => {
      setNomineeEntries(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get<{ data: AssetEntry[] }>(API.onboarding.employees.assets(employeeUuid)).then(r => {
      setAssetEntries(r.data?.data ?? []);
    }).catch(() => {});
    refetchTotalExperience();
  }, [employeeUuid, refetchTotalExperience]);

  function handleAddEducation() {
    tempEducationIdRef.current += 1;
    setEducationEntries(prev => [...prev, {
      id: `temp-${tempEducationIdRef.current}`,
      level: "", custom_level_label: "", institution: "", specialization: "",
      percentage: "", start_date: "", end_date: "",
    }]);
  }

  function handleEducationFieldChange(id: string, field: keyof EducationEntry, value: string) {
    setEducationEntries(prev => prev.map(e => (e.id === id ? { ...e, [field]: value } : e)));
  }

  function handleRemoveEducation(id: string) {
    if (!id.startsWith("temp-")) deletedEducationIdsRef.current.add(id);
    setEducationEntries(prev => prev.filter(e => e.id !== id));
  }

  // Reconciles the whole Education list against the server in one go —
  // called from saveSection()'s "education" branch, not from any per-entry
  // button. Deletes first (removed entries), then creates/updates whatever
  // remains.
  const saveEducationEntries = useCallback(async (): Promise<boolean> => {
    if (!educationEntries.some(e => e.institution.trim())) {
      setEducationErr("Please add at least one education entry (with an institution) before continuing.");
      return false;
    }
    for (const entry of educationEntries) {
      if (!entry.level) {
        setEducationErr("Select an education type for every entry.");
        return false;
      }
      if (entry.level === "other" && !entry.custom_level_label.trim()) {
        setEducationErr("Name the custom education type for every entry marked \"Other\".");
        return false;
      }
    }
    setEducationErr(null);
    try {
      for (const id of deletedEducationIdsRef.current) {
        await clientApi.delete(API.onboarding.employees.educationDetail(employeeUuid, id));
      }
      deletedEducationIdsRef.current.clear();

      const saved: EducationEntry[] = [];
      for (const entry of educationEntries) {
        const payload = {
          level: entry.level,
          custom_level_label: entry.level === "other" ? entry.custom_level_label.trim() : "",
          institution: entry.institution,
          specialization: entry.specialization,
          percentage: entry.percentage,
          start_date: entry.start_date || null,
          end_date: entry.end_date || null,
        };
        const isNew = entry.id.startsWith("temp-");
        const res = isNew
          ? await clientApi.post<{ data: EducationEntry }>(API.onboarding.employees.education(employeeUuid), payload)
          : await clientApi.patch<{ data: EducationEntry }>(API.onboarding.employees.educationDetail(employeeUuid, entry.id), payload);
        saved.push(res.data?.data ?? entry);
      }
      setEducationEntries(saved);
      return true;
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setEducationErr(msg ?? "Failed to save. Please try again.");
      return false;
    }
  }, [educationEntries, employeeUuid]);

  function handleAddExperience() {
    tempExperienceIdRef.current += 1;
    setExperienceEntries(prev => [...prev, {
      id: `temp-${tempExperienceIdRef.current}`,
      employer_name: "", designation: "", employment_type: "",
      start_date: "", end_date: "", is_current: false,
      responsibilities: "", reason_for_leaving: "",
    }]);
  }

  function handleExperienceFieldChange(id: string, field: keyof ExperienceEntry, value: string | boolean) {
    setExperienceEntries(prev => prev.map(e => (e.id === id ? { ...e, [field]: value } : e)));
  }

  function handleRemoveExperience(id: string) {
    if (!id.startsWith("temp-")) deletedExperienceIdsRef.current.add(id);
    setExperienceEntries(prev => prev.filter(e => e.id !== id));
  }

  // Reconciles the whole Experience list against the server in one go —
  // called from saveSection()'s "experience" branch. Experience has no
  // required-count rule (a fresher can leave it empty), so the only
  // per-entry check is "if you started one, name the employer".
  const saveExperienceEntries = useCallback(async (): Promise<boolean> => {
    for (const entry of experienceEntries) {
      if (!entry.employer_name.trim()) {
        setExperienceErr("Employer name is required for every entry — remove any blank ones, or fill them in.");
        return false;
      }
    }
    setExperienceErr(null);
    try {
      for (const id of deletedExperienceIdsRef.current) {
        await clientApi.delete(API.onboarding.employees.experienceDetail(employeeUuid, id));
      }
      deletedExperienceIdsRef.current.clear();

      const saved: ExperienceEntry[] = [];
      for (const entry of experienceEntries) {
        const payload = {
          employer_name: entry.employer_name.trim(),
          designation: entry.designation,
          employment_type: entry.employment_type,
          start_date: entry.start_date || null,
          end_date: entry.is_current ? null : (entry.end_date || null),
          is_current: entry.is_current,
          responsibilities: entry.responsibilities,
          reason_for_leaving: entry.reason_for_leaving,
        };
        const isNew = entry.id.startsWith("temp-");
        const res = isNew
          ? await clientApi.post<{ data: ExperienceEntry }>(API.onboarding.employees.experience(employeeUuid), payload)
          : await clientApi.patch<{ data: ExperienceEntry }>(API.onboarding.employees.experienceDetail(employeeUuid, entry.id), payload);
        saved.push(res.data?.data ?? entry);
      }
      setExperienceEntries(saved);
      refetchTotalExperience();
      return true;
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setExperienceErr(msg ?? "Failed to save. Please try again.");
      return false;
    }
  }, [experienceEntries, employeeUuid, refetchTotalExperience]);

  function handleAddFamily() {
    tempFamilyIdRef.current += 1;
    setFamilyEntries(prev => [...prev, {
      id: `temp-${tempFamilyIdRef.current}`,
      name: "", relationship: "", date_of_birth: "", gender: "", blood_group: "", is_dependent: false,
    }]);
  }

  function handleFamilyFieldChange(id: string, field: keyof FamilyEntry, value: string | boolean) {
    setFamilyEntries(prev => prev.map(e => (e.id === id ? { ...e, [field]: value } : e)));
  }

  function handleRemoveFamily(id: string) {
    if (!id.startsWith("temp-")) deletedFamilyIdsRef.current.add(id);
    setFamilyEntries(prev => prev.filter(e => e.id !== id));
    // A nominee pointing at the removed family member no longer has anyone
    // to reference — drop it locally too, same as the self-service wizard.
    setNomineeEntries(prev => prev.filter(n => n.family_member !== id));
  }

  function handleAddNominee() {
    tempNomineeIdRef.current += 1;
    setNomineeEntries(prev => [...prev, {
      id: `temp-${tempNomineeIdRef.current}`,
      family_member: "", scheme: "epf_eps", share_percentage: "",
    }]);
  }

  function handleNomineeFieldChange(id: string, field: keyof NomineeEntry, value: string) {
    setNomineeEntries(prev => prev.map(e => (e.id === id ? { ...e, [field]: value } : e)));
  }

  function handleRemoveNominee(id: string) {
    if (!id.startsWith("temp-")) deletedNomineeIdsRef.current.add(id);
    setNomineeEntries(prev => prev.filter(e => e.id !== id));
  }

  // Reconciles Family, then Nominees, in one go — family MUST be saved
  // first since a nominee references a family member by id, and a
  // not-yet-created family entry only has a temp- id until this save
  // returns. idMap translates temp- family ids to the real ids the family
  // save just returned before nominee payloads are sent.
  const saveFamilyNominationEntries = useCallback(async (): Promise<boolean> => {
    if (!familyEntries.every(e => e.name.trim())) {
      setFamilyNominationErr("Name is required for every family member entry.");
      return false;
    }
    if (!nomineeEntries.every(e => e.family_member)) {
      setFamilyNominationErr("Select a family member for every nominee entry.");
      return false;
    }
    setFamilyNominationErr(null);
    try {
      for (const id of deletedFamilyIdsRef.current) {
        await clientApi.delete(API.onboarding.employees.familyDetail(employeeUuid, id));
      }
      deletedFamilyIdsRef.current.clear();

      const idMap = new Map<string, string>();
      const savedFamily: FamilyEntry[] = [];
      for (const entry of familyEntries) {
        const payload = {
          name: entry.name.trim(),
          relationship: entry.relationship,
          date_of_birth: entry.date_of_birth || null,
          gender: entry.gender,
          blood_group: entry.blood_group,
          is_dependent: entry.is_dependent,
        };
        const isNew = entry.id.startsWith("temp-");
        const res = isNew
          ? await clientApi.post<{ data: FamilyEntry }>(API.onboarding.employees.family(employeeUuid), payload)
          : await clientApi.patch<{ data: FamilyEntry }>(API.onboarding.employees.familyDetail(employeeUuid, entry.id), payload);
        const saved = res.data?.data ?? entry;
        if (isNew) idMap.set(entry.id, saved.id);
        savedFamily.push(saved);
      }
      setFamilyEntries(savedFamily);

      for (const id of deletedNomineeIdsRef.current) {
        await clientApi.delete(API.onboarding.employees.nomineeDetail(employeeUuid, id));
      }
      deletedNomineeIdsRef.current.clear();

      const savedNominees: NomineeEntry[] = [];
      for (const entry of nomineeEntries) {
        const realFamilyId = idMap.get(entry.family_member) ?? entry.family_member;
        const payload = {
          family_member: realFamilyId,
          scheme: entry.scheme,
          share_percentage: entry.share_percentage || "0",
        };
        const isNew = entry.id.startsWith("temp-");
        const res = isNew
          ? await clientApi.post<{ data: NomineeEntry }>(API.onboarding.employees.nominees(employeeUuid), payload)
          : await clientApi.patch<{ data: NomineeEntry }>(API.onboarding.employees.nomineeDetail(employeeUuid, entry.id), payload);
        savedNominees.push(res.data?.data ?? { ...entry, family_member: realFamilyId });
      }
      setNomineeEntries(savedNominees);
      return true;
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setFamilyNominationErr(msg ?? "Failed to save. Please try again.");
      return false;
    }
  }, [familyEntries, nomineeEntries, employeeUuid]);

  function handleAddAsset() {
    tempAssetIdRef.current += 1;
    setAssetEntries(prev => [...prev, {
      id: `temp-${tempAssetIdRef.current}`,
      asset_type: "", tag_number: "", condition: "new",
    }]);
  }

  function handleAssetFieldChange(id: string, field: keyof AssetEntry, value: string) {
    setAssetEntries(prev => prev.map(e => (e.id === id ? { ...e, [field]: value } : e)));
  }

  function handleRemoveAsset(id: string) {
    if (!id.startsWith("temp-")) deletedAssetIdsRef.current.add(id);
    setAssetEntries(prev => prev.filter(e => e.id !== id));
  }

  const saveAssetEntries = useCallback(async (): Promise<boolean> => {
    if (!assetEntries.every(e => e.asset_type)) {
      setAssetErr("Select an asset type for every entry.");
      return false;
    }
    setAssetErr(null);
    try {
      for (const id of deletedAssetIdsRef.current) {
        await clientApi.delete(API.onboarding.employees.assetDetail(employeeUuid, id));
      }
      deletedAssetIdsRef.current.clear();

      const saved: AssetEntry[] = [];
      for (const entry of assetEntries) {
        const payload = { asset_type: entry.asset_type, tag_number: entry.tag_number, condition: entry.condition };
        const isNew = entry.id.startsWith("temp-");
        const res = isNew
          ? await clientApi.post<{ data: AssetEntry }>(API.onboarding.employees.assets(employeeUuid), payload)
          : await clientApi.patch<{ data: AssetEntry }>(API.onboarding.employees.assetDetail(employeeUuid, entry.id), payload);
        saved.push(res.data?.data ?? entry);
      }
      setAssetEntries(saved);
      return true;
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setAssetErr(msg ?? "Failed to save. Please try again.");
      return false;
    }
  }, [assetEntries, employeeUuid]);

  function set(field: keyof ProfileForm, value: string) {
    setForm(prev => ({ ...prev, [field]: value }));
  }
  function setCustom(fieldKey: string, value: string) {
    setCustomValues(prev => ({ ...prev, [fieldKey]: value }));
  }

  const saveSection = useCallback(async (): Promise<boolean> => {
    setSaveMsg(null); setSaveErr(null);
    const currentStep = steps[tab];

    // Education and Experience each reconcile their whole list in one go
    // here — add/edit/remove is purely local state until this point (see
    // saveEducationEntries()/saveExperienceEntries()'s own docstrings).
    // Errors render inline via each component's own `error` prop, not the
    // page-level saveErr banner above — showing both would just duplicate
    // the same message twice on screen.
    if (currentStep.kind === "education") return saveEducationEntries();
    if (currentStep.kind === "experience") return saveExperienceEntries();
    if (currentStep.kind === "family-nomination") return saveFamilyNominationEntries();
    if (currentStep.kind === "assets") return saveAssetEntries();
    if (currentStep.kind !== "fields") return true;

    const stepConfigs = fieldConfig[String(currentStep.step)] ?? [];
    const customForStep = Object.fromEntries(
      stepConfigs.filter(c => c.is_custom && c.field_type !== "file").map(c => [c.field_key, customValues[c.field_key] ?? ""]),
    );

    setSaving(true);
    try {
      const res = await clientApi.patch<{ success: boolean; message: string }>(
        API.onboarding.employees.step(employeeUuid, currentStep.step), { ...form, ...customForStep },
      );
      if (res.data?.success === false) {
        setSaveErr(res.data.message ?? "Please fill in all required fields.");
        return false;
      }
      setSaveMsg("Saved.");
      setTimeout(() => setSaveMsg(null), 2000);
      return true;
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveErr(msg ?? "Save failed. Please try again.");
      return false;
    } finally {
      setSaving(false);
    }
  }, [tab, steps, fieldConfig, customValues, form, employeeUuid, saveEducationEntries, saveExperienceEntries, saveFamilyNominationEntries, saveAssetEntries]);

  async function handlePanCardUpload(file: File) {
    const value = form.pan_number.trim().toUpperCase();
    if (!value) { setPanErr("Enter the PAN number before uploading the PAN card."); return; }
    if (!PAN_RE.test(value)) { setPanErr("Enter a valid PAN (e.g. ABCDE1234F) — 5 letters, 4 digits, 1 letter."); return; }
    setPanErr(null);
    setPanSaving(true);
    try {
      await clientApi.patch(API.onboarding.employees.step(employeeUuid, 4), { pan_number: value });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setPanErr(msg ?? "Could not save PAN number. Please try again.");
      return;
    } finally {
      setPanSaving(false);
    }
    set("pan_number", value);
    await handleUpload("pan_card", file);
  }

  async function handleUpload(docType: string, file: File) {
    setUploading(docType);
    try {
      const existing = docs.find(d => d.document_type === docType);
      if (existing) await clientApi.delete(API.onboarding.documentDetail(existing.id));
      const fd = new FormData();
      fd.append("document_type", docType);
      fd.append("file", file);
      await clientApi.post(API.onboarding.employees.documents(employeeUuid), fd);
      const r = await clientApi.get(API.onboarding.employees.documents(employeeUuid));
      setDocs(r.data?.data ?? []);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveErr(msg ?? "Upload failed. Max 5 MB, PDF/JPG/PNG only.");
    } finally {
      setUploading(null);
    }
  }

  async function handleCustomFileUpload(fieldKey: string, file: File) {
    setFileUploadError(null);
    setUploadingFileKey(fieldKey);
    try {
      const formData = new FormData();
      formData.append("field_key", fieldKey);
      formData.append("file", file);
      await clientApi.post(API.onboarding.employees.customFileFields(employeeUuid), formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const { data } = await clientApi.get(API.onboarding.employees.customFileFields(employeeUuid));
      setCustomFileValues(data?.data ?? []);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setFileUploadError(msg ?? "Failed to upload file. Please try again.");
    } finally {
      setUploadingFileKey(null);
    }
  }

  async function handleCustomFileDelete(fieldKey: string, valueId: number) {
    setFileUploadError(null);
    try {
      await clientApi.delete(API.onboarding.customFileFieldDetail(valueId));
      setCustomFileValues(prev => prev.filter(v => v.id !== valueId));
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setFileUploadError(msg ?? "Failed to delete file. Please try again.");
    }
  }

  async function next() {
    const ok = await saveSection();
    if (ok) {
      setHighestSaved(prev => Math.max(prev, tab));
      if (tab < steps.length - 1) setTab(t => t + 1);
    }
  }

  async function handleSubmit() {
    const ok = await saveSection();
    if (!ok) return;
    setSaving(true);
    try {
      await clientApi.post(API.onboarding.employees.submit(employeeUuid), {}, { timeout: 60000 });
      setHighestSaved(steps.length - 1);
      setSubmitted(true);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveErr(msg ?? "Submission failed. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  async function handleApproveNow() {
    if (!window.confirm(`Approve and activate ${employeeName || "this employee"}'s account? They'll get full access immediately.`)) return;
    setApproving(true);
    try {
      await clientApi.post(API.onboarding.approve(employeeUuid), { decision: "approve" });
      router.push(`/dashboard/employees/${id}`);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveErr(msg ?? "Approval failed — approve it from the Onboarding Approvals screen instead.");
    } finally {
      setApproving(false);
    }
  }

  const stepConfigsForTab = useMemo(
    () => (fieldConfig[String(steps[tab].step)] ?? []).filter(c => c.visible),
    [fieldConfig, steps, tab],
  );

  if (loading) return <div style={{ padding: 40, textAlign: "center", color: "var(--on-variant)" }}>Loading…</div>;
  if (notFound) return <div className="alert alert-error">Employee not found.</div>;
  if (!canEdit) return <div className="alert alert-error">You do not have permission to complete onboarding for this employee.</div>;

  if (submitted) {
    return (
      <div className="card" style={{ maxWidth: 560, margin: "40px auto", padding: "2.5rem", textAlign: "center" }}>
        <div style={{ width: 64, height: 64, borderRadius: "50%", background: "var(--success-c)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 1.25rem" }}>
          <i className="ti ti-check" style={{ color: "var(--success)", fontSize: 30 }} />
        </div>
        <h2 style={{ fontSize: "1.25rem", fontWeight: 700, marginBottom: ".5rem" }}>Onboarding submitted for {employeeName}</h2>
        <p style={{ color: "var(--on-variant)", marginBottom: "1.5rem" }}>
          {canApprove
            ? "You can approve it now, or leave it for review in Onboarding Approvals."
            : "It's now awaiting HR approval."}
        </p>
        {saveErr && <div className="alert alert-error" style={{ marginBottom: 16, textAlign: "left" }}>{saveErr}</div>}
        <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
          <button className="btn btn-ghost" onClick={() => router.push(`/dashboard/employees/${id}`)}>
            Back to Profile
          </button>
          {canApprove && (
            <button className="btn btn-filled" onClick={handleApproveNow} disabled={approving}>
              {approving ? "Approving…" : "Approve Now"}
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Complete Onboarding — {employeeName}</div>
          <div className="page-sub">Fill in the employee&apos;s onboarding profile on their behalf.</div>
        </div>
        <button className="btn btn-ghost" onClick={() => router.push(`/dashboard/employees/${id}`)}>
          <i className="ti ti-arrow-left" /> Back
        </button>
      </div>

      <StepIndicator
        steps={steps}
        currentStep={tab}
        highestSaved={highestSaved}
        onStepClick={setTab}
      />

      <div className="card" style={{ padding: "1.75rem" }}>
        {saveErr && <div className="alert alert-error" style={{ marginBottom: "1.25rem" }}>{saveErr}</div>}
        {saveMsg && <div className="alert alert-success" style={{ marginBottom: "1.25rem" }}>{saveMsg}</div>}

        {tab === 0 && basicDetails && (
          <BasicDetailsCard
            employeeId={id}
            details={basicDetails}
            editable={canEditBasicDetails}
            onSaved={updated => {
              setBasicDetails(updated);
              setEmployeeName(updated.full_name || updated.email || id);
            }}
          />
        )}

        {steps[tab].kind === "fields" && (
          <DynamicStepFields
            configs={stepConfigsForTab}
            form={form}
            customValues={customValues}
            onBuiltinChange={set}
            onCustomChange={setCustom}
            customFileValues={customFileValues}
            uploadingFileKey={uploadingFileKey}
            fileUploadError={fileUploadError}
            onCustomFileUpload={handleCustomFileUpload}
            onCustomFileDelete={handleCustomFileDelete}
          />
        )}
        {steps[tab].kind === "documents" && (
          <TabDocuments
            docTypes={docTypes}
            docs={docs}
            uploadedTypes={uploadedTypes}
            uploading={uploading}
            fileRefs={fileRefs}
            onUpload={handleUpload}
            panNumber={form.pan_number}
            onPanNumberChange={v => { set("pan_number", v); setPanErr(null); }}
            onPanCardUpload={handlePanCardUpload}
            onPanValidationError={setPanErr}
            panErr={panErr}
            panSaving={panSaving}
          />
        )}
        {steps[tab].kind === "education" && (
          <EducationChecklist
            entries={educationEntries}
            fieldConfig={eduExpFieldConfig.education}
            onAdd={handleAddEducation}
            onFieldChange={handleEducationFieldChange}
            onRemove={handleRemoveEducation}
            error={educationErr}
          />
        )}
        {steps[tab].kind === "experience" && (
          <ExperienceList
            totalExperienceYears={totalExperienceYears}
            entries={experienceEntries}
            fieldConfig={eduExpFieldConfig.experience}
            onAdd={handleAddExperience}
            onFieldChange={handleExperienceFieldChange}
            onRemove={handleRemoveExperience}
            error={experienceErr}
          />
        )}
        {steps[tab].kind === "family-nomination" && (
          <FamilyNominationStep
            familyEntries={familyEntries}
            nomineeEntries={nomineeEntries}
            onAddFamily={handleAddFamily}
            onFamilyFieldChange={handleFamilyFieldChange}
            onRemoveFamily={handleRemoveFamily}
            onAddNominee={handleAddNominee}
            onNomineeFieldChange={handleNomineeFieldChange}
            onRemoveNominee={handleRemoveNominee}
            error={familyNominationErr}
          />
        )}
        {steps[tab].kind === "assets" && (
          <AssetsList
            entries={assetEntries}
            onAdd={handleAddAsset}
            onFieldChange={handleAssetFieldChange}
            onRemove={handleRemoveAsset}
            error={assetErr}
          />
        )}

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "2rem", paddingTop: "1.25rem", borderTop: "1px solid var(--outline-v)" }}>
          <button className="btn btn-ghost" onClick={() => setTab(t => Math.max(0, t - 1))} disabled={tab === 0 || saving} type="button">
            <i className="ti ti-arrow-left" /> Previous
          </button>
          {tab < steps.length - 1 ? (
            <button className="btn btn-filled" onClick={next} disabled={saving} type="button">
              {saving ? "Saving…" : <>Save & Continue <i className="ti ti-arrow-right" /></>}
            </button>
          ) : (
            <div style={{ display: "flex", gap: ".75rem" }}>
              <button className="btn btn-ghost" onClick={saveSection} disabled={saving} type="button">
                {saving ? "Saving…" : "Save"}
              </button>
              <button
                className="btn btn-filled"
                onClick={handleSubmit}
                disabled={saving}
                type="button"
                style={{ background: "var(--success)", borderColor: "var(--success)" }}
              >
                {saving ? "Submitting…" : <><i className="ti ti-check" /> Submit for Approval</>}
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="alert alert-info" style={{ marginTop: 20 }}>
        <i className="ti ti-info-circle" />
        <div>
          Face ID registration (if required by your organisation) isn&apos;t part of this wizard — register it
          in person from{" "}
          <a href="/dashboard/face-id-registrations" style={{ color: "var(--primary)", fontWeight: 600 }}>
            Face ID Registrations
          </a>{" "}
          before submitting, if your Attendance Settings require it.
        </div>
      </div>
    </>
  );
}

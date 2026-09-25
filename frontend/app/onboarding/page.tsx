"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useRouter } from "next/navigation";
import clientApi, { markIntentionalLogout } from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { getStoredUser, setOnboardingStatus, clearAuth } from "@/lib/auth";
import FaceRegistrationModal from "@/components/FaceRegistrationModal";
import type { FaceRegistrationRequest } from "@/types/faceRegistration";
import type { OnboardingFieldConfigByStep, CustomFieldFileValue, OnboardingSection, EducationExperienceFieldConfigResponse } from "@/types/onboardingFieldConfig";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import type { ProfileForm } from "./_types";
import DynamicStepFields from "./_components/DynamicStepFields";
import TabDocuments, { type UploadedDoc } from "./_components/TabDocuments";
import TabFaceId from "./_components/TabFaceId";
import StepIndicator from "./_components/StepIndicator";
import BasicDetailsCard, { type BasicDetails } from "./_components/BasicDetailsCard";
import EducationChecklist, { type EducationEntry } from "./_components/EducationChecklist";
import ExperienceList, { type ExperienceEntry } from "./_components/ExperienceList";
import FamilyNominationStep, { type FamilyEntry, type NomineeEntry } from "./_components/FamilyNominationStep";
import AssetsList, { type AssetEntry } from "./_components/AssetsList";
import { EMPTY, PAN_RE, BUILTIN_STEPS, DOCUMENTS_STEP, FACE_STEP, type WizardStep } from "./_wizardSteps";

// ── Component ───────────────────────────────────────────────────────────────

export default function OnboardingPage() {
  const router = useRouter();
  const [loggingOut, setLoggingOut] = useState(false);
  const [tab,       setTab]       = useState(0);
  const [form,      setForm]      = useState<ProfileForm>(EMPTY);
  const [docs,      setDocs]      = useState<UploadedDoc[]>([]);
  const [saving,    setSaving]    = useState(false);
  const [saveMsg,   setSaveMsg]   = useState<string | null>(null);
  const [saveErr,   setSaveErr]   = useState<string | null>(null);
  const [uploading,    setUploading]    = useState<string | null>(null);
  const [panErr,       setPanErr]       = useState<string | null>(null);
  const [panSaving,    setPanSaving]    = useState(false);
  const [submitted,          setSubmitted]          = useState(false);
  const [isAlreadySubmitted, setIsAlreadySubmitted] = useState(false);
  const [checkingApproval,   setCheckingApproval]   = useState(false);
  const [highestSaved, setHighestSaved] = useState(-1);
  // Raw step numbers the backend already considers complete (GET
  // /onboarding/'s own `completed_steps`) — restores unlocked progress when
  // reopening onboarding partway through, instead of resetting to only
  // Step 1 unlocked on every fresh page load regardless of what's actually
  // saved server-side. Experience (-3) is deliberately never in this list
  // (it has no required fields, see _missing_education_experience) but
  // never blocks advancing either — treated as always-passed below, same
  // as saveSection()'s own "experience" branch always returning true.
  const [completedStepNumbers, setCompletedStepNumbers] = useState<number[]>([]);
  // "none" | "pending" — a self-service bank-detail edit that would
  // overwrite an already-filled value is held for HR review instead of
  // applying immediately (see backend's bank-change verification gate).
  const [bankChangeStatus, setBankChangeStatus] = useState<string>("none");
  const fileRefs = useRef<Record<string, HTMLInputElement | null>>({});

  // Per-company configurable fields (steps 0-3) — see Settings > Onboarding
  // Fields. Empty object until fetched; DynamicStepFields renders nothing for
  // a step until its config arrives, same "nothing to show yet" behavior as
  // every other useFetch-backed list in this app.
  const [fieldConfig, setFieldConfig] = useState<OnboardingFieldConfigByStep>({});
  // Show/require toggles for Education/Experience list-entry fields — see
  // Settings > Onboarding Fields > Education & Experience. Empty arrays
  // until fetched, same "everything defaults to shown/optional" fallback
  // EducationChecklist/ExperienceList themselves use.
  const [eduExpFieldConfig, setEduExpFieldConfig] = useState<EducationExperienceFieldConfigResponse>({ education: [], experience: [] });
  // HR-created custom sections beyond the 4 built-ins — see OnboardingSection.
  const [customSections, setCustomSections] = useState<OnboardingSection[]>([]);
  const [customValues, setCustomValues] = useState<Record<string, string>>({});
  const [customFileValues, setCustomFileValues] = useState<CustomFieldFileValue[]>([]);
  // Per-company configurable document types (Settings > Onboarding Fields >
  // Documents) — same fetch-all-filter-visible pattern as fieldConfig above.
  const [docTypeConfig, setDocTypeConfig] = useState<DocumentTypeConfig[]>([]);
  const docTypes = docTypeConfig.filter(t => t.visible).sort((a, b) => a.order - b.order);
  const [uploadingFileKey, setUploadingFileKey] = useState<string | null>(null);
  const [fileUploadError, setFileUploadError] = useState<string | null>(null);

  const [faceMandatory, setFaceMandatory] = useState(false);
  const [faceRegistration, setFaceRegistration] = useState<Partial<FaceRegistrationRequest> | null>(null);
  const [showFaceCapture, setShowFaceCapture] = useState(false);

  // "Basic details" — read-only here (self-service). An employee must never
  // be able to change their own Role/Company Code, so this whole section is
  // view-only, not just those two fields — see BasicDetailsCard's own header
  // comment for the full reasoning.
  const [basicDetails, setBasicDetails] = useState<BasicDetails | null>(null);
  useEffect(() => {
    clientApi.get<{ data: Record<string, unknown> }>(API.employees.me).then(r => {
      const d = r.data?.data;
      if (!d) return;
      setBasicDetails({
        full_name:       String(d.full_name ?? ""),
        email:           String(d.email ?? ""),
        phone:           String(d.phone ?? ""),
        employee_type:   String(d.employee_type ?? ""),
        date_of_joining: String(d.date_of_joining ?? ""),
        // /employees/me/ (MyProfileSerializer) names this role_name, not
        // role — different from /employees/<id>/'s _employee_dict() shape,
        // normalized here so BasicDetailsCard itself stays endpoint-agnostic.
        role:            String(d.role_name ?? ""),
        role_display:    String(d.role_display ?? ""),
        branch:          String(d.branch ?? ""),
        department:      String(d.department ?? ""),
        designation:     String(d.designation ?? ""),
        org_unit_name:   d.org_unit_name != null ? String(d.org_unit_name) : null,
      });
    }).catch(() => {});
  }, []);

  // Education + Experience — both real add/remove lists, see BUILTIN_STEPS'
  // comment above for why these are their own bespoke steps. Add/edit/remove
  // is purely local state; nothing reaches the server until the step's own
  // Save & Continue reconciles the whole list at once (see saveSection()'s
  // "education"/"experience" branches below) — deletedEducationIdsRef/
  // deletedExperienceIdsRef track which real (non-temp) ids were removed
  // locally so that reconciliation knows what to DELETE server-side.
  const [educationEntries, setEducationEntries] = useState<EducationEntry[]>([]);
  const [educationErr, setEducationErr] = useState<string | null>(null);
  const tempEducationIdRef = useRef(0);
  const deletedEducationIdsRef = useRef<Set<string>>(new Set());
  const [experienceEntries, setExperienceEntries] = useState<ExperienceEntry[]>([]);
  const [totalExperienceYears, setTotalExperienceYears] = useState<string | null>(null);
  const [experienceErr, setExperienceErr] = useState<string | null>(null);
  const tempExperienceIdRef = useRef(0);
  const deletedExperienceIdsRef = useRef<Set<string>>(new Set());

  // Family & Nomination — two related lists reconciled together (see
  // saveFamilyNominationEntries() below): Family is always saved FIRST so
  // any nominee referencing a not-yet-created (`temp-`) family member gets
  // translated to the real id the family save just returned.
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
    clientApi.get<{ data: { total_experience_years: number | null } }>(API.onboarding.experienceSummary).then(r => {
      const v = r.data?.data?.total_experience_years;
      setTotalExperienceYears(v != null ? String(v) : null);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    clientApi.get<{ data: EducationEntry[] }>(API.onboarding.education).then(r => {
      setEducationEntries(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get<{ data: ExperienceEntry[] }>(API.onboarding.experience).then(r => {
      setExperienceEntries(r.data?.data ?? []);
    }).catch(() => {});
    refetchTotalExperience();
    clientApi.get<{ data: FamilyEntry[] }>(API.onboarding.family).then(r => {
      setFamilyEntries(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get<{ data: NomineeEntry[] }>(API.onboarding.nominees).then(r => {
      setNomineeEntries(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get<{ data: AssetEntry[] }>(API.onboarding.assets).then(r => {
      setAssetEntries(r.data?.data ?? []);
    }).catch(() => {});
  }, [refetchTotalExperience]);

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
  // remains, so a removed-then-re-added entry never collides with itself.
  async function saveEducationEntries(): Promise<boolean> {
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
        await clientApi.delete(API.onboarding.educationDetail(id));
      }
      deletedEducationIdsRef.current.clear();

      const saved: EducationEntry[] = [];
      for (const entry of educationEntries) {
        const payload = {
          level: entry.level,
          custom_level_label: entry.custom_level_label,
          institution: entry.institution,
          specialization: entry.specialization,
          percentage: entry.percentage,
          start_date: entry.start_date || null,
          end_date: entry.end_date || null,
        };
        const isNew = entry.id.startsWith("temp-");
        const res = isNew
          ? await clientApi.post<{ data: EducationEntry }>(API.onboarding.education, payload)
          : await clientApi.patch<{ data: EducationEntry }>(API.onboarding.educationDetail(entry.id), payload);
        saved.push(res.data?.data ?? entry);
      }
      setEducationEntries(saved);
      return true;
    } catch (err: unknown) {
      setEducationErr((err as { message?: string })?.message ?? "Failed to save. Please try again.");
      return false;
    }
  }

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
  async function saveExperienceEntries(): Promise<boolean> {
    for (const entry of experienceEntries) {
      if (!entry.employer_name.trim()) {
        setExperienceErr("Employer name is required for every entry — remove any blank ones, or fill them in.");
        return false;
      }
    }
    setExperienceErr(null);
    try {
      for (const id of deletedExperienceIdsRef.current) {
        await clientApi.delete(API.onboarding.experienceDetail(id));
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
          ? await clientApi.post<{ data: ExperienceEntry }>(API.onboarding.experience, payload)
          : await clientApi.patch<{ data: ExperienceEntry }>(API.onboarding.experienceDetail(entry.id), payload);
        saved.push(res.data?.data ?? entry);
      }
      setExperienceEntries(saved);
      refetchTotalExperience();
      return true;
    } catch (err: unknown) {
      setExperienceErr((err as { message?: string })?.message ?? "Failed to save. Please try again.");
      return false;
    }
  }

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
    // A nominee pointing at the family member just removed no longer has
    // anything to reference — drop it locally too, same as the family
    // member's own real row cascading server-side (see CompanyAsset's
    // sibling model docstring for the cascade behavior this mirrors).
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

  // Reconciles Family first, then Nominees — a nominee referencing a
  // `temp-` family id gets translated to the real id the family save just
  // returned, via `idMap`, before nominees are sent at all.
  async function saveFamilyNominationEntries(): Promise<boolean> {
    for (const entry of familyEntries) {
      if (!entry.name.trim()) {
        setFamilyNominationErr("Name is required for every family member — remove any blank ones, or fill them in.");
        return false;
      }
    }
    for (const entry of nomineeEntries) {
      if (!entry.family_member) {
        setFamilyNominationErr("Select a family member for every nominee — remove any incomplete ones, or fill them in.");
        return false;
      }
    }
    setFamilyNominationErr(null);
    try {
      for (const id of deletedFamilyIdsRef.current) {
        await clientApi.delete(API.onboarding.familyDetail(id));
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
          ? await clientApi.post<{ data: FamilyEntry }>(API.onboarding.family, payload)
          : await clientApi.patch<{ data: FamilyEntry }>(API.onboarding.familyDetail(entry.id), payload);
        const saved = res.data?.data ?? entry;
        if (isNew) idMap.set(entry.id, saved.id);
        savedFamily.push(saved);
      }
      setFamilyEntries(savedFamily);

      for (const id of deletedNomineeIdsRef.current) {
        await clientApi.delete(API.onboarding.nomineeDetail(id));
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
          ? await clientApi.post<{ data: NomineeEntry }>(API.onboarding.nominees, payload)
          : await clientApi.patch<{ data: NomineeEntry }>(API.onboarding.nomineeDetail(entry.id), payload);
        savedNominees.push(res.data?.data ?? { ...entry, family_member: realFamilyId });
      }
      setNomineeEntries(savedNominees);
      return true;
    } catch (err: unknown) {
      setFamilyNominationErr((err as { message?: string })?.message ?? "Failed to save. Please try again.");
      return false;
    }
  }

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

  async function saveAssetEntries(): Promise<boolean> {
    for (const entry of assetEntries) {
      if (!entry.asset_type) {
        setAssetErr("Select an asset type for every entry — remove any incomplete ones, or fill them in.");
        return false;
      }
    }
    setAssetErr(null);
    try {
      for (const id of deletedAssetIdsRef.current) {
        await clientApi.delete(API.onboarding.assetDetail(id));
      }
      deletedAssetIdsRef.current.clear();

      const saved: AssetEntry[] = [];
      for (const entry of assetEntries) {
        const payload = { asset_type: entry.asset_type, tag_number: entry.tag_number, condition: entry.condition };
        const isNew = entry.id.startsWith("temp-");
        const res = isNew
          ? await clientApi.post<{ data: AssetEntry }>(API.onboarding.assets, payload)
          : await clientApi.patch<{ data: AssetEntry }>(API.onboarding.assetDetail(entry.id), payload);
        saved.push(res.data?.data ?? entry);
      }
      setAssetEntries(saved);
      return true;
    } catch (err: unknown) {
      setAssetErr((err as { message?: string })?.message ?? "Failed to save. Please try again.");
      return false;
    }
  }

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
    return [
      ...BUILTIN_STEPS,
      ...customSteps,
      DOCUMENTS_STEP,
      ...(faceMandatory ? [FACE_STEP] : []),
    ];
  }, [customSections, faceMandatory]);

  // Restores unlocked progress from the backend's own completed_steps once
  // both it and the real step list have arrived — a contiguous PREFIX of
  // "done" steps starting from Step 1, not just "which steps are done"
  // (stopping at the first not-done step matches the same one-at-a-time
  // gate StepIndicator itself enforces from here on). Only ever raises
  // highestSaved (Math.max), never lowers it, so this can't undo progress
  // made after this effect first runs.
  useEffect(() => {
    let highest = -1;
    for (let i = 0; i < steps.length; i++) {
      const passes = steps[i].kind === "experience" || steps[i].kind === "family-nomination" || steps[i].kind === "assets"
        || completedStepNumbers.includes(steps[i].step);
      if (!passes) break;
      highest = i;
    }
    if (highest >= 0) setHighestSaved(prev => Math.max(prev, highest));
  }, [steps, completedStepNumbers]);

  // Mirrors the backend's own gate (OnboardingView._submit,
  // apps/accounts/views.py): submission requires a face registration to
  // *exist* when mandatory — any status (pending/approved/rejected) counts,
  // same "submitted is enough, approval is a separate later step" bar as
  // Documents. Keeping this identical to the backend check avoids a frontend
  // that blocks submission the backend would actually accept, or vice versa.
  const canSubmit = !faceMandatory || Boolean(faceRegistration);

  useEffect(() => {
    const user = getStoredUser();
    if (user?.onboarding_status === "submitted") setIsAlreadySubmitted(true);
  }, []);

  const refetchFaceRegistration = useCallback(() => {
    clientApi.get(API.attendance.faceRegistration.me).then(r => {
      setFaceRegistration(r.data?.data ?? null);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    clientApi.get(API.attendance.faceVerification.status).then(r => {
      setFaceMandatory(Boolean(r.data?.data?.is_mandatory));
    }).catch(() => {});
    refetchFaceRegistration();
  }, [refetchFaceRegistration]);

  // When on the "waiting for approval" screen, poll assessments API.
  // If HR has approved and assigned assessments, redirect the candidate there.
  useEffect(() => {
    if (!submitted && !isAlreadySubmitted) return;
    clientApi.get(API.assessments.my).then(r => {
      const assignments = r.data?.data?.assignments ?? [];
      if (assignments.length > 0) router.replace("/onboarding/assessments");
    }).catch(() => {});
  }, [submitted, isAlreadySubmitted, router]);


  useEffect(() => {
    clientApi.get(API.onboarding.profile).then(r => {
      const d = r.data?.data ?? {};
      setForm(prev => ({ ...prev, ...Object.fromEntries(
        Object.keys(EMPTY).map(k => [
          k,
          // permanent_same_as_current comes back as a real JSON boolean,
          // but every other ProfileForm value (this field included) is a
          // string — `?? ""` alone would let `false` through unconverted
          // since `??` only catches null/undefined, not false.
          k === "permanent_same_as_current" ? String(Boolean(d[k])) : (d[k] ?? ""),
        ])
      ) }));
      setCustomValues(
        Object.fromEntries(
          Object.entries(d.custom_field_values ?? {}).map(([k, v]) => [k, v == null ? "" : String(v)]),
        ),
      );
      setCompletedStepNumbers(d.completed_steps ?? []);
      setBankChangeStatus(d.bank_change_status ?? "none");
    }).catch(() => {});
    clientApi.get(API.onboarding.documents).then(r => {
      setDocs(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get(API.onboarding.fieldConfig).then(r => {
      setFieldConfig(r.data?.data ?? {});
    }).catch(() => {});
    clientApi.get<{ data: EducationExperienceFieldConfigResponse }>(API.onboarding.educationExperienceFieldConfig).then(r => {
      setEduExpFieldConfig(r.data?.data ?? { education: [], experience: [] });
    }).catch(() => {});
    clientApi.get(API.onboarding.sections).then(r => {
      setCustomSections(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get(API.onboarding.customFileFields).then(r => {
      setCustomFileValues(r.data?.data ?? []);
    }).catch(() => {});
    clientApi.get(API.onboarding.documentTypeConfig).then(r => {
      setDocTypeConfig(r.data?.data ?? []);
    }).catch(() => {});
  }, []);

  async function handleCustomFileUpload(fieldKey: string, file: File) {
    setFileUploadError(null);
    setUploadingFileKey(fieldKey);
    try {
      const formData = new FormData();
      formData.append("field_key", fieldKey);
      formData.append("file", file);
      await clientApi.post(API.onboarding.customFileFields, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const { data } = await clientApi.get(API.onboarding.customFileFields);
      setCustomFileValues(data?.data ?? []);
    } catch (err: unknown) {
      setFileUploadError((err as { message?: string })?.message ?? "Failed to upload file. Please try again.");
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
      setFileUploadError((err as { message?: string })?.message ?? "Failed to delete file. Please try again.");
    }
  }

  async function handleLogout() {
    setLoggingOut(true);
    try {
      markIntentionalLogout();
      await clientApi.post(API.auth.logout, {});
    } catch { /* proceed regardless */ } finally {
      clearAuth();
      router.replace("/login");
    }
  }

  function set(field: keyof ProfileForm, value: string) {
    setForm(prev => ({ ...prev, [field]: value }));
  }

  function setCustom(fieldKey: string, value: string) {
    setCustomValues(prev => ({ ...prev, [fieldKey]: value }));
  }

  async function saveSection(): Promise<boolean> {
    setSaveMsg(null); setSaveErr(null);

    const currentStepEarly = steps[tab];

    // Education and Experience each reconcile their whole list in one go
    // here — add/edit/remove is purely local state until this point (see
    // saveEducationEntries()/saveExperienceEntries()'s own docstrings).
    // Errors render inline via each component's own `error` prop, not the
    // page-level saveErr banner above — showing both would just duplicate
    // the same message twice on screen.
    if (currentStepEarly.kind === "education") return saveEducationEntries();
    if (currentStepEarly.kind === "experience") return saveExperienceEntries();
    if (currentStepEarly.kind === "family-nomination") return saveFamilyNominationEntries();
    if (currentStepEarly.kind === "assets") return saveAssetEntries();

    // Required-ness is settings-driven now (see Settings > Onboarding
    // Fields) — fieldConfig[step] covers each company's own visible+required
    // choices for both built-in and custom fields. A hidden field can never
    // block saving even if still marked required in the config (matches the
    // backend's _step_required_configs, which checks visible AND required
    // together for the same reason).
    const currentStep = steps[tab];
    const stepConfigs = fieldConfig[String(currentStep.step)] ?? [];
    const missing = stepConfigs
      .filter(c => c.visible && c.required)
      .filter(c => {
        // File-type fields have no entry in `customValues` at all — their
        // presence is checked against the uploaded-files list instead (same
        // choke-point fix as the backend's _field_value()), or a required
        // file field would report missing forever, even after upload.
        if (c.field_type === "file") {
          return !customFileValues.some(v => v.field_key === c.field_key);
        }
        const value = c.is_custom ? customValues[c.field_key] : form[c.field_key as keyof ProfileForm];
        return !value?.trim();
      })
      .map(c => c.label);
    if (missing.length > 0) {
      setSaveErr(`Please fill in: ${missing.join(", ")}`);
      return false;
    }

    // Documents and Face ID (when present) have no profile data to save —
    // documents are uploaded via handleUpload, face ID is submitted via the
    // FaceRegistrationModal. Skip the API call and let handleSubmit fire the
    // single submit request.
    if (currentStep.kind !== "fields") return true;

    // Custom field values for this step ride along in the same PATCH body —
    // the backend filters incoming keys to this step's configured fields
    // (built-in and custom alike), same as it already does for `form`.
    const customForStep = Object.fromEntries(
      stepConfigs.filter(c => c.is_custom && c.field_type !== "file").map(c => [c.field_key, customValues[c.field_key] ?? ""]),
    );

    setSaving(true);
    try {
      const res = await clientApi.patch<{ success: boolean; message: string; data?: { bank_change_status?: string } }>(
        API.onboarding.profileStep(currentStep.step), { ...form, ...customForStep },
      );
      if (res.data?.success === false) {
        setSaveErr(res.data.message ?? "Please fill in all required fields.");
        return false;
      }
      if (res.data?.data?.bank_change_status) setBankChangeStatus(res.data.data.bank_change_status);
      setSaveMsg(res.data?.message?.includes("HR review") ? res.data.message : "Saved successfully.");
      setTimeout(() => setSaveMsg(null), res.data?.message?.includes("HR review") ? 6000 : 2500);
      return true;
    } catch (err: unknown) {
      setSaveErr((err as { message?: string })?.message ?? "Save failed. Please try again.");
      return false;
    } finally {
      setSaving(false);
    }
  }

  async function next() {
    const ok = await saveSection();
    if (ok && tab < steps.length - 1) {
      setHighestSaved(prev => Math.max(prev, tab));
      setTab(t => t + 1);
    }
  }

  // PAN's number is captured at the moment its proof document is uploaded,
  // not on a separate form step — matches how real onboarding flows tie the
  // two together. Validates format + global uniqueness server-side before
  // the file itself is ever sent, so a duplicate/invalid PAN blocks the
  // upload with an immediate, specific error instead of silently accepting
  // an unusable document.
  async function handlePanCardUpload(file: File) {
    const value = form.pan_number.trim().toUpperCase();
    if (!value) {
      setPanErr("Enter your PAN number before uploading the PAN card.");
      return;
    }
    if (!PAN_RE.test(value)) {
      setPanErr("Enter a valid PAN (e.g. ABCDE1234F) — 5 letters, 4 digits, 1 letter.");
      return;
    }
    setPanErr(null);
    setPanSaving(true);
    try {
      await clientApi.patch(API.onboarding.profileStep(4), { pan_number: value });
    } catch (err: unknown) {
      setPanErr((err as { message?: string })?.message ?? "Could not save PAN number. Please try again.");
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
      // If a document of this type already exists, delete it first
      const existing = docs.find(d => d.document_type === docType);
      if (existing) {
        await clientApi.delete(API.onboarding.documentDetail(existing.id));
      }
      const fd = new FormData();
      fd.append("document_type", docType);
      fd.append("file", file);
      await clientApi.post(API.onboarding.documents, fd);
      const r = await clientApi.get(API.onboarding.documents);
      setDocs(r.data?.data ?? []);
    } catch (err: unknown) {
      setSaveErr((err as { message?: string })?.message ?? "Upload failed. Max 5 MB, PDF/JPG/PNG only.");
    } finally {
      setUploading(null);
    }
  }

  async function handleSubmit() {
    const ok = await saveSection();
    if (!ok) return;
    setSaving(true);
    try {
      await clientApi.post(API.onboarding.submit, {}, { timeout: 60000 });
      setHighestSaved(steps.length - 1);
      setOnboardingStatus("submitted");
      setSubmitted(true);
    } catch (err: unknown) {
      setSaveErr((err as { message?: string })?.message ?? "Submission failed. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  const uploadedTypes = new Set(docs.map(d => d.document_type));

  async function handleCheckApproval() {
    setCheckingApproval(true);
    try {
      const r = await clientApi.get(API.assessments.my);
      const assignments = r.data?.data?.assignments ?? [];
      if (assignments.length > 0) {
        router.replace("/onboarding/assessments");
      }
    } catch { /* stay on page */ } finally {
      setCheckingApproval(false);
    }
  }

  // ── Submitted screen ───────────────────────────────────────────────────────
  if (submitted || isAlreadySubmitted) {
    return (
      <div style={ROOT_STYLE}>
        <div style={{ ...CARD_STYLE, textAlign: "center", padding: "3rem 2rem", maxWidth: 480 }}>
          <div style={{ width: 72, height: 72, borderRadius: "50%", background: "var(--success-c)", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 1.5rem", fontSize: 32 }}>
            <i className="ti ti-check" style={{ color: "var(--success)", fontSize: 36 }} />
          </div>
          <h2 style={{ fontSize: "1.4rem", fontWeight: 700, color: "var(--on-bg)", marginBottom: ".75rem" }}>Profile Submitted!</h2>
          <p style={{ color: "var(--on-variant)", lineHeight: 1.6, marginBottom: "1.5rem" }}>
            Your onboarding details have been sent for HR review.<br />
            You will receive access once approved.
          </p>
          <p style={{ fontSize: ".82rem", color: "var(--outline)", background: "var(--bg-low)", padding: ".75rem 1rem", borderRadius: 8, marginBottom: "1.5rem" }}>
            You can close this tab. We will notify you by email when approved.
          </p>
          <button
            onClick={handleCheckApproval}
            disabled={checkingApproval}
            type="button"
            style={{
              display: "inline-flex", alignItems: "center", gap: 7,
              padding: "10px 20px", borderRadius: 10,
              border: "1.5px solid var(--primary)",
              background: "var(--primary)",
              color: "#fff",
              cursor: checkingApproval ? "not-allowed" : "pointer",
              fontSize: ".9rem", fontWeight: 600,
              opacity: checkingApproval ? 0.7 : 1,
            }}
          >
            {checkingApproval
              ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 15 }} /> Checking…</>
              : <><i className="ti ti-refresh" style={{ fontSize: 15 }} /> Check Approval Status</>
            }
          </button>
        </div>

        <button
          onClick={handleLogout}
          disabled={loggingOut}
          type="button"
          style={{
            position: "fixed", bottom: 24, right: 24, zIndex: 100,
            display: "flex", alignItems: "center", gap: 7,
            padding: "10px 18px", borderRadius: 10,
            border: "1.5px solid var(--outline-v)",
            background: "var(--surface)",
            boxShadow: "0 2px 12px rgba(0,0,0,0.10)",
            cursor: loggingOut ? "not-allowed" : "pointer",
            fontSize: ".84rem", fontWeight: 500,
            color: "var(--on-variant)",
          }}
        >
          {loggingOut
            ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 15 }} /> Logging out…</>
            : <><i className="ti ti-logout" style={{ fontSize: 15 }} /> Logout</>
          }
        </button>
      </div>
    );
  }

  // ── Wizard ─────────────────────────────────────────────────────────────────
  return (
    <div style={ROOT_STYLE}>
      <div style={{ width: "100%", maxWidth: 820 }}>

        {/* ── Header ── */}
        <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/logo-icon.png"
            alt="Aira HRMS"
            style={{ height: 56, width: "auto", objectFit: "contain", margin: "0 auto 1.25rem", display: "block" }}
          />
          <h1 style={{ fontSize: "1.75rem", fontWeight: 700, color: "var(--on-bg)", marginBottom: ".5rem", letterSpacing: "-.02em" }}>
            Complete Your Profile
          </h1>
          <p style={{ color: "var(--on-variant)", fontSize: ".95rem" }}>
            Fill in your details to get started. Your information is kept secure.
          </p>
        </div>

        {/* ── Step Indicator ── */}
        <StepIndicator steps={steps} currentStep={tab} highestSaved={highestSaved} onStepClick={setTab} />

        {/* ── Form card ── */}
        <div style={CARD_STYLE}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: "1.5rem", paddingBottom: "1rem", borderBottom: "1px solid var(--outline-v)" }}>
            <div style={{ width: 38, height: 38, borderRadius: 10, background: "rgba(124,58,237,0.08)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
              <i className={`ti ${steps[tab].icon}`} style={{ fontSize: 18, color: "var(--primary)" }} />
            </div>
            <div>
              <div style={{ fontSize: ".7rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: ".06em", color: "var(--outline)", marginBottom: 2 }}>Step {tab + 1} of {steps.length}</div>
              <div style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--on-bg)" }}>{steps[tab].label}</div>
            </div>
            <div style={{ marginLeft: "auto", textAlign: "right" }}>
              <div style={{ fontSize: ".75rem", color: "var(--on-variant)", marginBottom: 4 }}>{Math.round(((highestSaved + 1) / steps.length) * 100)}% complete</div>
              <div style={{ width: 100, height: 5, borderRadius: 3, background: "var(--outline-v)", overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${((highestSaved + 1) / steps.length) * 100}%`, background: "var(--primary)", borderRadius: 3, transition: "width 0.4s ease" }} />
              </div>
            </div>
          </div>

          {saveErr && <div className="alert alert-error"  style={{ marginBottom: "1.25rem" }}>{saveErr}</div>}
          {saveMsg && <div className="alert alert-success" style={{ marginBottom: "1.25rem" }}>{saveMsg}</div>}

          {tab === 0 && basicDetails && (
            // employeeId is unused in read-only mode (save() is only ever
            // reachable from the editable branch) — passed empty here.
            <BasicDetailsCard
              employeeId=""
              details={basicDetails}
              editable={false}
              onSaved={setBasicDetails}
            />
          )}

          {steps[tab].kind === "fields" && steps[tab].step === 2 && bankChangeStatus === "pending" && (
            <div style={{
              display: "flex", alignItems: "flex-start", gap: 10, padding: "0.9rem 1rem",
              marginBottom: "1.25rem", borderRadius: 10,
              background: "var(--warn-c)", color: "var(--warn)", fontSize: 13,
            }}>
              <i className="ti ti-clock-hour-4" style={{ fontSize: 16, marginTop: 1 }} />
              <div>
                A bank detail change you submitted is awaiting HR review — your previous
                details remain active for payroll until it&apos;s approved.
              </div>
            </div>
          )}
          {steps[tab].kind === "fields" && (
            <DynamicStepFields
              configs={(fieldConfig[String(steps[tab].step)] ?? []).filter(c => c.visible)}
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
          {steps[tab].kind === "face" && (
            <TabFaceId
              registration={faceRegistration}
              onRegister={() => setShowFaceCapture(true)}
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
            <button className="btn btn-ghost" onClick={() => setTab(t => t - 1)} disabled={tab === 0 || saving} type="button">
              <i className="ti ti-arrow-left" style={{ fontSize: 14 }} /> Previous
            </button>
            {tab < steps.length - 1 ? (
              <button className="btn btn-filled" onClick={next} disabled={saving} type="button">
                {saving
                  ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 14 }} /> Saving…</>
                  : <>Save & Continue <i className="ti ti-arrow-right" style={{ fontSize: 14 }} /></>
                }
              </button>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: ".5rem" }}>
                <div style={{ display: "flex", gap: ".75rem" }}>
                  <button className="btn btn-ghost" onClick={saveSection} disabled={saving} type="button">
                    {saving ? "Saving…" : "Save Draft"}
                  </button>
                  <button
                    className="btn btn-filled"
                    onClick={handleSubmit}
                    disabled={saving || !canSubmit}
                    type="button"
                    style={{ background: "var(--success)", borderColor: "var(--success)" }}
                    title={canSubmit ? undefined : "Complete Face ID registration (Step 6) before submitting."}
                  >
                    {saving
                      ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 14 }} /> Submitting…</>
                      : <><i className="ti ti-check" style={{ fontSize: 14 }} /> Submit for Approval</>
                    }
                  </button>
                </div>
                {!canSubmit && (
                  <span style={{ fontSize: ".78rem", color: "var(--outline)" }}>
                    Complete Face ID registration (Step 6) to enable submission.
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Fixed logout button ── */}
      <button
        onClick={handleLogout}
        disabled={loggingOut}
        type="button"
        style={{
          position: "fixed", bottom: 24, right: 24, zIndex: 100,
          display: "flex", alignItems: "center", gap: 7,
          padding: "10px 18px", borderRadius: 10,
          border: "1.5px solid var(--outline-v)",
          background: "var(--surface)",
          boxShadow: "0 2px 12px rgba(0,0,0,0.10)",
          cursor: loggingOut ? "not-allowed" : "pointer",
          fontSize: ".84rem", fontWeight: 500,
          color: "var(--on-variant)",
        }}
      >
        {loggingOut
          ? <><i className="ti ti-loader-2 animate-spin" style={{ fontSize: 15 }} /> Logging out…</>
          : <><i className="ti ti-logout" style={{ fontSize: 15 }} /> Logout</>
        }
      </button>

      {showFaceCapture && (
        <FaceRegistrationModal
          mode="register"
          onClose={() => { setShowFaceCapture(false); refetchFaceRegistration(); }}
        />
      )}
    </div>
  );
}

// ── Layout constants ───────────────────────────────────────────────────────────

// The global stylesheet makes <body> a fixed, non-scrolling 100vh frame by
// design (see globals.css) — every full page is expected to supply its own
// inner overflow-y:auto region. This page previously relied on ordinary
// document scroll via `minHeight: 100vh`, which body's `overflow: hidden`
// silently blocked once the form got taller than the viewport (visible as
// "the page won't scroll" on longer steps or smaller screens).
const ROOT_STYLE: React.CSSProperties = {
  height: "100vh",
  overflowY: "auto",
  background: "linear-gradient(140deg, #f0f4ff 0%, #e9effe 45%, #f3f0ff 100%)",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "flex-start",
  padding: "3rem 1rem 4rem",
};

const CARD_STYLE: React.CSSProperties = {
  background: "var(--surface)",
  borderRadius: 16,
  padding: "2rem",
  boxShadow: "0 4px 24px rgba(124,58,237,0.08), 0 1px 4px rgba(0,0,0,0.04)",
  border: "1px solid rgba(124,58,237,0.08)",
};

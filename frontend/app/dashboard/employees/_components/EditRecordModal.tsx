"use client";

// ── "Edit full record" modal ──────────────────────────────────────────────
// Reuses the Hire Wizard's own visual shell (Modal + .wiz/.wiz-nav/.wiz-main
// classes from aira-theme.css, HireWizardSidebar, and the exact STEPS label/
// sub/group/tag list from _wizardData.ts) so this looks like the same
// system as the Hire flow, per the reference mockup's own "editmode" variant
// of that same modal. Content panels are NOT the Hire Wizard's draft-bound
// step components (those are wired to a HireAction draft, not an existing
// employee) — they reuse this page's own already-real, already-working
// pieces instead: ProfileForm (personal/employment/statutory/education),
// SalaryTab (basic pay), FamilyNominationStep + AssetsList (bound here via
// the same /onboarding/employees/<uuid>/... endpoints the HR-onboarding
// wizard already uses for an existing employee).
//
// Known, deliberate simplifications versus the full page at
// /dashboard/employees/[id]:
//  - No per-company custom-field support (Settings > Onboarding Fields) —
//    only the fixed built-in fields render here.
//  - No document upload/custom-file-field section is included beyond what
//    DocsCards already shows — "Documents" reuses the existing docs section
//    as-is.
//  - Emergency contact fields (not part of the new 8-section layout) are
//    folded into the bottom of "Family & nomination" rather than dropped.

import { useCallback, useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import {
  PROFILE_SECTIONS,
  type DetailValues,
  type Employee,
  type FieldOption,
  type GridSection,
} from "../_data";
import { apiToEmployee, type ApiEmployee } from "../[id]/_apiMapping";
import ProfileForm from "../[id]/_components/ProfileForm";
import SalaryTab from "../[id]/_components/SalaryTab";
import HireWizardSidebar from "../../hire/[hireActionId]/_components/HireWizardSidebar";
import { STEPS as HIRE_STEPS } from "../../hire/[hireActionId]/_components/_wizardData";
import StatutoryAccountsStep, { EMPTY_STATUTORY, type StatutoryDraft } from "../../hire/[hireActionId]/_components/StatutoryAccountsStep";
import FamilyNominationStep, {
  type FamilyEntry,
  type NomineeEntry,
} from "@/app/onboarding/_components/FamilyNominationStep";
import AssetsList, { type AssetEntry } from "@/app/onboarding/_components/AssetsList";
import FormField from "../_components/FormField";
import type { HireDocument } from "@/components/DocUploadButton";

const STEPS = HIRE_STEPS.slice(0, -1); // drop "Review" — not applicable to editing an existing record

const PERSONAL_IDENTITY_KEYS = [
  "code", "firstName", "lastName", "loginEmail", "mobileNumber",
  "dateOfBirth", "gender", "maritalStatus", "fatherName", "bloodGroup",
  "currentAddress", "currentAddressLine2", "currentVillage", "currentDistrict", "currentState", "currentPinCode",
  "permanentSameAsCurrent", "permanentAddress", "permanentAddressLine2", "permanentVillage", "permanentDistrict", "permanentState", "permanentPinCode",
];
const EMPLOYMENT_KEYS = ["dateOfJoining", "department", "designation", "ssRole", "branch", "reportingManager", "reportingApprover", "hr"];

function pickSection(id: string, label: string, icon: string, keys: string[]): GridSection {
  const source = PROFILE_SECTIONS.find(s => s.id === id);
  const fields = source && source.kind === "grid" ? source.fields.filter(f => keys.includes(f.key)) : [];
  return { id: `edit-${id}`, label, icon, kind: "grid", fields };
}

let tempId = 0;
const nextTempId = () => `temp-${++tempId}`;

export default function EditRecordModal({ employee, onClose }: { employee: Employee; onClose: () => void }) {
  const [uuid, setUuid] = useState("");
  const [loading, setLoading] = useState(true);
  const [values, setValues] = useState<DetailValues>({});
  const [baseValues, setBaseValues] = useState<DetailValues>({});
  const [docs, setDocs] = useState<ReturnType<typeof apiToEmployee>["documents"]>([]);
  const [hireDocs, setHireDocs] = useState<HireDocument[]>([]);
  const [uploadingDocType, setUploadingDocType] = useState<string | null>(null);
  const [docUploadError, setDocUploadError] = useState("");

  // Statutory & accounts — same field set and components as the Hire
  // Wizard (StatutoryAccountsStep/StatutoryDraft), per explicit feedback
  // that this modal must show the SAME fields as the hire flow, not a
  // smaller ad-hoc subset. PAN/Aadhaar/passport/PF/ESI are write-only here
  // (masked server-side, same "handled as sensitive data" posture as the
  // Hire Wizard's own banner) — left blank means "no change", not "clear
  // the value". account_*/bank_* fields DO come back from the employee GET
  // (not masked) and are pre-filled from `values` below.
  const [statutory, setStatutory] = useState<StatutoryDraft>(EMPTY_STATUTORY);

  const [roleOptions, setRoleOptions] = useState<FieldOption[]>([]);
  const [branchOptions, setBranchOptions] = useState<FieldOption[]>([]);

  const [familyEntries, setFamilyEntries] = useState<FamilyEntry[]>([]);
  const [nomineeEntries, setNomineeEntries] = useState<NomineeEntry[]>([]);
  const [assetEntries, setAssetEntries] = useState<AssetEntry[]>([]);
  const [familyErr, setFamilyErr] = useState<string | null>(null);
  const [assetErr, setAssetErr] = useState<string | null>(null);
  const deletedFamilyIds = useRef<Set<string>>(new Set());
  const deletedNomineeIds = useRef<Set<string>>(new Set());
  const deletedAssetIds = useRef<Set<string>>(new Set());

  const [step, setStep] = useState(0);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedMsg, setSavedMsg] = useState(false);

  useEffect(() => {
    Promise.allSettled([
      clientApi.get<{ data: ApiEmployee }>(API.employees.detail(employee.id)),
      clientApi.get<{ data: { results: { id: number; name: string; display_name: string }[] } }>(`${API.roles.list}?page_size=100`),
      clientApi.get<{ data: { results: { id: number; branch_name: string }[] } }>(API.branches.list),
    ]).then(([empRes, roles, branches]) => {
      if (empRes.status === "fulfilled") {
        const raw = empRes.value.data.data;
        const emp = apiToEmployee(raw, []);
        setUuid(raw.uuid);
        setValues(emp.details);
        setBaseValues({ ...emp.details });
        setDocs(emp.documents);
        setHireDocs((raw.documents ?? []).map(d => ({
          id: String(d.id), document_type: d.document_type, document_type_display: d.document_type_display,
          entry_ref: "", file_name: d.file_name, file_size: d.file_size, uploaded_at: d.uploaded_at,
        })));
        // pf_covered/esi_covered aren't declared on ApiEmployee (that type
        // mirrors what page.tsx's own payload builder sends, which never
        // included them until this fix) but the backend's _employee_dict
        // does return them — read defensively rather than widening the
        // shared type for 2 fields only this modal uses.
        const rawRecord = raw as unknown as Record<string, unknown>;
        setStatutory(s => ({
          ...s,
          account_holder_name: emp.details.accountHolderName ?? "",
          account_number: emp.details.accountNumber ?? "",
          ifsc_code: emp.details.ifscCode ?? "",
          bank_name: emp.details.bankName ?? "",
          bank_branch_address: emp.details.bankBranch ?? "",
          uan_number: emp.details.uanNumber ?? "",
          esi_number: emp.details.esiNumber ?? "",
          pf_covered: typeof rawRecord.pf_covered === "boolean" ? String(rawRecord.pf_covered) : s.pf_covered,
          esi_covered: typeof rawRecord.esi_covered === "boolean" ? String(rawRecord.esi_covered) : s.esi_covered,
        }));
      }
      if (roles.status === "fulfilled") {
        setRoleOptions(roles.value.data.data.results.filter(r => r.name !== "system_admin").map(r => ({ value: r.name, label: r.display_name })));
      }
      if (branches.status === "fulfilled") {
        setBranchOptions(branches.value.data.data.results.map(b => ({ value: b.branch_name, label: b.branch_name })));
      }
      setLoading(false);
    });
  }, [employee.id]);

  useEffect(() => {
    if (!uuid) return;
    clientApi.get<{ data: FamilyEntry[] }>(API.onboarding.employees.family(uuid)).then(r => setFamilyEntries(r.data?.data ?? [])).catch(() => {});
    clientApi.get<{ data: NomineeEntry[] }>(API.onboarding.employees.nominees(uuid)).then(r => setNomineeEntries(r.data?.data ?? [])).catch(() => {});
    clientApi.get<{ data: AssetEntry[] }>(API.onboarding.employees.assets(uuid)).then(r => setAssetEntries(r.data?.data ?? [])).catch(() => {});
  }, [uuid]);

  const dirty = JSON.stringify(values) !== JSON.stringify(baseValues);

  function onFieldChange(key: string, val: string) {
    setValues(v => ({ ...v, [key]: val }));
    setSavedMsg(false);
  }

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
      const raw = data.data;
      setHireDocs((raw.documents ?? []).map(d => ({
        id: String(d.id), document_type: d.document_type, document_type_display: d.document_type_display,
        entry_ref: "", file_name: d.file_name, file_size: d.file_size, uploaded_at: d.uploaded_at,
      })));
      setDocs(apiToEmployee(raw, []).documents);
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
      const payload = {
        branch: values.branch || null,
        role: values.ssRole || null,
        reporting_manager_id: values.reportingManagerId || null,
        reporting_approver_id: values.reportingApproverId || null,
        hr_id: values.hrId || null,
        date_of_birth: values.dateOfBirth || null,
        gender: values.gender || "",
        marital_status: values.maritalStatus?.toLowerCase() || "",
        father_name: values.fatherName || "",
        blood_group: values.bloodGroup || "",
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
        highest_qualification: values.highestQualification || "",
        institution: values.institution || "",
        year_of_passing: values.yearOfPassing || null,
        specialization: values.specialization || "",
        total_experience_years: values.totalExperienceYears || null,
        previous_employer: values.previousEmployer || "",
        previous_designation: values.previousDesignation || "",
        leaving_reason: values.leavingReason || "",
        account_holder_name: statutory.account_holder_name || "",
        account_type: values.accountType || "",
        account_number: statutory.account_number || "",
        ifsc_code: statutory.ifsc_code || "",
        bank_name: statutory.bank_name || "",
        bank_branch_name: statutory.bank_branch_address || "",
        emergency_name: values.emergencyName || "",
        emergency_relationship: values.emergencyRelationship || "",
        emergency_phone: values.emergencyPhone || "",
        emergency_email: values.emergencyEmail || "",
        uan_number: statutory.uan_number || "",
        name_as_per_aadhar: values.nameAsPerAadhar || "",
        esi_number: statutory.esi_number || "",
        pf_covered: statutory.pf_covered === "true",
        esi_covered: statutory.esi_covered === "true",
        // Write-only re-entry (see the `statutory` state comment above) —
        // blank means "no change". Sending "" for these would otherwise
        // overwrite an existing encrypted value with an empty string.
        ...(statutory.pan_number ? { pan_number: statutory.pan_number } : {}),
        ...(statutory.aadhaar_number ? { aadhaar_number: statutory.aadhaar_number } : {}),
        ...(statutory.passport_number ? { passport_number: statutory.passport_number, passport_expiry: statutory.passport_expiry || null } : {}),
      };
      await clientApi.put(API.employees.detail(employee.id), payload);

      const familyOk = await saveFamilyAndNominees();
      const assetsOk = await saveAssets();

      setBaseValues(values);
      setSavedMsg(familyOk && assetsOk);
      if (!familyOk || !assetsOk) setSaveError("Some sections could not be saved — see the errors above.");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSaveError(msg ?? "Failed to save changes. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  function onDiscard() {
    setValues(baseValues);
    setSaveError(null);
    setSavedMsg(false);
  }

  const sections: Record<number, GridSection> = {
    0: pickSection("personal", "Personal identity", "ti-user", PERSONAL_IDENTITY_KEYS),
    1: pickSection("personal", "Employment", "ti-briefcase", EMPLOYMENT_KEYS),
    5: (PROFILE_SECTIONS.find(s => s.id === "education") as GridSection),
  };

  const fieldOptions: Record<string, FieldOption[]> = { ssRole: roleOptions, branch: branchOptions };

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
          <button onClick={onDiscard} disabled={!dirty || saving} className="btn btn-ghost">Discard</button>
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
          <HireWizardSidebar steps={STEPS} currentStep={step} highestSaved={-1} onStepClick={setStep} missingByStep={{}} />

          <div className="wiz-main">
            <div className="stephead" style={{ padding: "20px 24px 0" }}>
              <div>
                <h3>{STEPS[step].label}</h3>
                <p>{STEPS[step].sub}</p>
              </div>
            </div>

            <div style={{ padding: 24 }}>
              {(step === 0 || step === 1 || step === 5) && (
                <ProfileForm
                  section={sections[step]}
                  values={values}
                  rows={[]}
                  dirty={dirty}
                  fieldOptions={fieldOptions}
                  onFieldChange={onFieldChange}
                  onRowsChange={() => {}}
                  onSave={onSaveChanges}
                  onCancel={onDiscard}
                />
              )}

              {step === 3 && (
                <StatutoryAccountsStep
                  value={statutory}
                  onChange={setStatutory}
                  documents={hireDocs}
                  uploading={uploadingDocType}
                  docError={docUploadError}
                  onUploadDoc={onUploadDocument}
                  // No per-document delete endpoint exists for an existing
                  // employee's documents today (only list/create) — re-upload
                  // the same type to replace it, same convention used
                  // elsewhere in this app.
                  onDeleteDoc={() => setDocUploadError("To replace a document, upload a new file of the same type.")}
                />
              )}

              {step === 2 && <SalaryTab employeeId={uuid} employeeCode={employee.code} />}

              {step === 4 && (
                <div>
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
                  <div className="divider" style={{ margin: "20px 0" }} />
                  <div className="sechead">EMERGENCY CONTACT</div>
                  <div className="grid grid-cols-2 gap-x-6 gap-y-5" style={{ marginTop: 12 }}>
                    {(PROFILE_SECTIONS.find(s => s.id === "emergency") as GridSection).fields.map(f => (
                      <FormField key={f.key} field={f} value={values[f.key] ?? ""} onChange={onFieldChange} disabled={false} />
                    ))}
                  </div>
                </div>
              )}

              {step === 6 && (
                <ProfileForm
                  section={PROFILE_SECTIONS.find(s => s.id === "documents") as GridSection}
                  values={values}
                  rows={[]}
                  dirty={false}
                  liveDocuments={docs}
                  onFieldChange={() => {}}
                  onRowsChange={() => {}}
                  onSave={() => {}}
                  onCancel={() => {}}
                  readOnly
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

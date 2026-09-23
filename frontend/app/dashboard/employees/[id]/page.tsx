"use client";

import { use, useState, useEffect } from "react";
import Link from "next/link";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import { useFetch } from "@/hooks/useFetch";
import type { CustomFieldFileValue, OnboardingFieldConfigByStep } from "@/types/onboardingFieldConfig";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import CustomFieldFileUpload from "@/components/CustomFieldFileUpload";
import {
  PROFILE_SECTIONS,
  PROFILE_TABS,
  applyFieldConfig,
  customFieldKeys,
  type DetailValues,
  type FieldOption,
  type TableRow,
  type Employee,
  type ApiDocument,
} from "../_data";
import { buildDocEntries, apiToEmployee, type ApiEmployee } from "./_apiMapping";
import ProfileHeader from "./_components/ProfileHeader";
import ProfileTabBar from "./_components/ProfileTabBar";
import ProfileSidebar from "./_components/ProfileSidebar";
import ProfileForm from "./_components/ProfileForm";
import { EmployeePickerInline } from "./_components/ReportingManagerCard";
import { ApprovalMatrixTab } from "./_components/ApprovalMatrixTab";
import { WishesTab } from "./_components/WishesTab";
import { LeaveTab } from "./_components/LeaveTab";
import { AttendanceTab } from "./_components/AttendanceTab";
import SalaryTab from "./_components/SalaryTab";
import PayrollTab from "./_components/PayrollTab";
import PromotionTab from "./_components/PromotionTab";
import AuditTrailTab from "./_components/AuditTrailTab";

export default function EmployeeProfilePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const canEdit = usePermission("employees.edit");
  const canEditOnboarding = usePermission("onboarding.edit");
  const [tab,       setTab]       = useState<string>("profile");
  const [sectionId, setSectionId] = useState<string>("personal");

  const [employee,          setEmployee]          = useState<Employee | null>(null);
  const [employeeUuid,      setEmployeeUuid]      = useState<string>("");
  const [currentPositionId, setCurrentPositionId] = useState<string>("");
  const [currentOrgUnitId,  setCurrentOrgUnitId]  = useState<string>("");
  const [onboardingStatus,  setOnboardingStatus]  = useState<string>("");
  const [loading,           setLoading]           = useState(true);
  const [notFound,          setNotFound]          = useState(false);

  const [values,     setValues]     = useState<DetailValues>({});
  const [tables,     setTables]     = useState<Record<string, TableRow[]>>({});
  const [baseValues, setBaseValues] = useState<DetailValues>({});
  const [baseTables, setBaseTables] = useState<Record<string, TableRow[]>>({});
  const [justSaved,  setJustSaved]  = useState(false);
  const [saving,     setSaving]     = useState(false);
  const [saveError,  setSaveError]  = useState<string | null>(null);
  const [isEditing,  setIsEditing]  = useState(false);

  const [uploadingDocType, setUploadingDocType] = useState<string | null>(null);
  const [docUploadError,   setDocUploadError]   = useState<string>("");

  const [customFileFields, setCustomFileFields] = useState<CustomFieldFileValue[]>([]);
  const [uploadingFileKey, setUploadingFileKey] = useState<string | null>(null);
  const [fileUploadError,  setFileUploadError]  = useState<string>("");

  // Raw (unmerged) documents from the last successful fetch — kept around so
  // the documents list can be rebuilt once documentTypeConfig arrives, since
  // that fetch is independent of (and may resolve after) the employee fetch
  // that first builds `employee.documents`.
  const [rawApiDocuments, setRawApiDocuments] = useState<ApiDocument[]>([]);
  const { data: documentTypeConfigData } = useFetch<DocumentTypeConfig[]>(API.onboarding.documentTypeConfig);

  const [roleOptions,     setRoleOptions]     = useState<FieldOption[]>([]);
  const [branchOptions,   setBranchOptions]   = useState<FieldOption[]>([]);

  // fetch dropdown lists once on mount — use allSettled so one failure does
  // not block the others from loading. GET /roles/ is intentionally open to
  // any authenticated user (needed for role-selector dropdowns like this
  // one) — see RoleListCreateView.get().
  useEffect(() => {
    Promise.allSettled([
      clientApi.get<{ data: { results: { id: number; name: string; display_name: string }[] } }>(`${API.roles.list}?page_size=100`),
      clientApi.get<{ data: { results: { id: number; branch_name: string }[] } }>(API.branches.list),
    ]).then(([roles, branches]) => {
      if (roles.status === "fulfilled")
        setRoleOptions(
          roles.value.data.data.results
            .filter(r => r.name !== "system_admin")
            .map(r => ({ value: r.name, label: r.display_name }))
        );
      if (branches.status === "fulfilled")
        setBranchOptions(branches.value.data.data.results.map(b => ({ value: b.branch_name, label: b.branch_name })));
    });
  }, []);

  useEffect(() => {
    setLoading(true);
    setNotFound(false);
    clientApi
      .get<{ data: ApiEmployee }>(API.employees.detail(id))
      .then(async ({ data }) => {
        const raw = data.data;
        // documentTypeConfig isn't a dependency of this effect (only `id` is)
        // — it's applied here with whatever's in cache/empty on first render,
        // then the effect below reactively rebuilds `documents` once/whenever
        // documentTypeConfigData actually resolves, so this never needs to
        // re-run just because that fetch settles later.
        const emp = apiToEmployee(raw, []);
        setEmployee(emp);
        setEmployeeUuid(raw.uuid);
        setCurrentPositionId(raw.position_id ?? "");
        setCurrentOrgUnitId(raw.org_unit_id ?? "");
        setOnboardingStatus(raw.onboarding_status ?? "");
        setRawApiDocuments(raw.documents ?? []);
        setCustomFileFields(
          (raw.custom_file_fields ?? []).map(f => ({
            id: f.id, field_key: f.field_key, file_url: f.file,
            file_name: f.file_name, file_size: f.file_size, uploaded_at: f.uploaded_at,
          })),
        );

        const details = { ...emp.details };

        // Auto-assign the sole HR in the branch when none is set yet
        if (!details.hr && !details.hrId && details.branch) {
          try {
            const hrRes = await clientApi.get<{ data: { id: string; full_name: string }[] }>(
              `${API.employees.hrList}?branch=${encodeURIComponent(details.branch)}`,
            );
            const hrs = hrRes.data?.data ?? [];
            if (hrs.length === 1) {
              details.hr   = hrs[0].full_name;
              details.hrId = hrs[0].id;
            }
          } catch {
            // Non-blocking — leave hr unassigned if the lookup fails
          }
        }

        setValues(details);
        setBaseValues({ ...details });
        setTables({});
        setBaseTables({});
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [id]);

  // documentTypeConfig is fetched independently of the employee GET above and
  // may resolve after it — rebuild the documents list once it arrives so a
  // hidden/reordered/custom type is reflected without needing a full refetch.
  useEffect(() => {
    if (!documentTypeConfigData) return;
    setEmployee(prev => prev && { ...prev, documents: buildDocEntries(rawApiDocuments, documentTypeConfigData) });
  }, [documentTypeConfigData, rawApiDocuments]);

  // Per-company field visibility/custom fields — same endpoint the
  // onboarding wizard and self-service Profile page read.
  const { data: fieldConfigData } = useFetch<OnboardingFieldConfigByStep>(API.onboarding.fieldConfig);
  const fieldConfig = fieldConfigData ?? {};

  const rawSection = PROFILE_SECTIONS.find(s => s.id === sectionId)!;
  const section = applyFieldConfig(rawSection, fieldConfig);

  const dirty =
    JSON.stringify(values) !== JSON.stringify(baseValues) ||
    JSON.stringify(tables) !== JSON.stringify(baseTables);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 gap-2 text-[13px] text-[var(--on-variant)]">
        <i className="ti ti-loader-2 animate-spin text-[22px]" style={{ color: "var(--primary)" }} />
        Loading employee…
      </div>
    );
  }

  if (notFound || !employee) {
    return (
      <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] p-12 text-center max-w-lg mx-auto mt-10">
        <i className="ti ti-user-question text-5xl text-[var(--outline)] block mb-4" />
        <h2 className="text-[17px] font-semibold text-[var(--on-bg)] mb-1.5">Employee not found</h2>
        <p className="text-[13px] text-[var(--on-variant)] mb-5">
          No employee exists with code <span className="font-semibold">{id}</span>.
        </p>
        <Link
          href="/dashboard/employees"
          className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-[13px] font-semibold bg-[var(--primary)] text-white hover:bg-[#6d28d9] transition-colors"
        >
          <i className="ti ti-arrow-left text-[15px]" />
          Back to Employees
        </Link>
      </div>
    );
  }

  function onFieldChange(key: string, val: string) {
    setValues(v => ({ ...v, [key]: val }));
    setJustSaved(false);
  }
  function onRowsChange(rows: TableRow[]) {
    setTables(t => ({ ...t, [sectionId]: rows }));
    setJustSaved(false);
  }
  async function onSave() {
    setSaving(true);
    setSaveError(null);
    setJustSaved(false);
    try {
      const employeePayload = {
        // Employment fields — department/designation are Position-derived
        // only now (see PromotionTab.tsx's "Reassign Position" action), not
        // editable through this generic save.
        branch:                 values.branch                || null,
        role:                   values.ssRole                || null,
        is_active:              employee?.status !== "inactive",
        reporting_manager_id:   values.reportingManagerId   || null,
        reporting_approver_id:  values.reportingApproverId  || null,
        hr_id:                  values.hrId                  || null,
        // Personal fields
        // date_of_birth/year_of_passing/total_experience_years are the only
        // fields below backed by a nullable model column — everything else
        // is `blank=True` without `null=True`, so the serializer rejects an
        // explicit null and an empty string must be sent instead.
        date_of_birth:          values.dateOfBirth          || null,
        gender:                 values.gender               || "",
        marital_status:         values.maritalStatus?.toLowerCase() || "",
        father_name:            values.fatherName           || "",
        blood_group:            values.bloodGroup           || "",
        current_address:        values.currentAddress       || "",
        current_address_line2:  values.currentAddressLine2  || "",
        current_village:        values.currentVillage       || "",
        current_district:       values.currentDistrict      || "",
        current_state:          values.currentState         || "",
        current_pin_code:       values.currentPinCode       || "",
        permanent_address:      values.permanentAddress     || "",
        permanent_address_line2: values.permanentAddressLine2 || "",
        permanent_village:      values.permanentVillage     || "",
        permanent_district:     values.permanentDistrict    || "",
        permanent_state:        values.permanentState       || "",
        permanent_pin_code:     values.permanentPinCode     || "",
        permanent_same_as_current: values.permanentSameAsCurrent === "true",
        // Education & experience
        highest_qualification:  values.highestQualification || "",
        institution:            values.institution          || "",
        year_of_passing:        values.yearOfPassing        || null,
        specialization:         values.specialization       || "",
        total_experience_years: values.totalExperienceYears || null,
        previous_employer:      values.previousEmployer     || "",
        previous_designation:   values.previousDesignation  || "",
        leaving_reason:         values.leavingReason        || "",
        // Bank details
        account_holder_name:    values.accountHolderName    || "",
        account_type:           values.accountType          || "",
        account_number:         values.accountNumber        || "",
        ifsc_code:              values.ifscCode             || "",
        bank_name:              values.bankName             || "",
        bank_branch_name:       values.bankBranch           || "",
        // Emergency contact
        emergency_name:         values.emergencyName        || "",
        emergency_relationship: values.emergencyRelationship || "",
        emergency_phone:        values.emergencyPhone       || "",
        emergency_email:        values.emergencyEmail       || "",
        // EPF / Statutory
        uan_number:          values.uanNumber       || "",
        name_as_per_aadhar:  values.nameAsPerAadhar || "",
        esi_number:          values.esiNumber       || "",
        // HR-created custom fields (Settings > Onboarding Fields) — this page
        // edits any category's custom fields under the same isEditing/
        // employees.edit gate as their section's built-ins.
        custom_field_values: Object.fromEntries(
          customFieldKeys(fieldConfig).map(key => [key, values[key] ?? ""]),
        ),
      };

      await clientApi.put(API.employees.detail(id), employeePayload);

      setBaseValues(values);
      setBaseTables(tables);
      setJustSaved(true);
      setIsEditing(false);
    } catch (err: unknown) {
      setSaveError((err as { message?: string })?.message ?? "Failed to save changes. Please try again.");
    } finally {
      setSaving(false);
    }
  }
  function onPositionReassigned(designation: string, department: string, role: string, positionId: string, orgUnitId: string) {
    setValues(v => ({ ...v, designation, ssRole: role, ...(department ? { department } : {}) }));
    setBaseValues(v => ({ ...v, designation, ssRole: role, ...(department ? { department } : {}) }));
    setEmployee(prev => (prev ? { ...prev, designation, ...(department ? { department } : {}) } : prev));
    setCurrentPositionId(positionId);
    setCurrentOrgUnitId(orgUnitId);
  }
  async function onUploadDocument(documentType: string, file: File) {
    setDocUploadError("");
    setUploadingDocType(documentType);
    try {
      const formData = new FormData();
      formData.append("document_type", documentType);
      formData.append("file", file);
      await clientApi.post(API.employees.documents(id), formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      // Re-fetch so the card picks up the real uploaded_at/file_size/file_url
      // from the server rather than guessing them client-side.
      const { data } = await clientApi.get<{ data: ApiEmployee }>(API.employees.detail(id));
      setRawApiDocuments(data.data.documents ?? []);
      const freshDocs = buildDocEntries(data.data.documents ?? [], documentTypeConfigData ?? []);
      setEmployee(prev => (prev ? { ...prev, documents: freshDocs } : prev));
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setDocUploadError(msg || "Failed to upload document. Please try again.");
    } finally {
      setUploadingDocType(null);
    }
  }
  function onCancel() {
    setValues(baseValues);
    setTables(baseTables);
    setJustSaved(false);
    setIsEditing(false);
  }
  async function onUploadCustomFile(fieldKey: string, file: File) {
    setFileUploadError("");
    setUploadingFileKey(fieldKey);
    try {
      const formData = new FormData();
      formData.append("field_key", fieldKey);
      formData.append("file", file);
      await clientApi.post(API.employees.customFileFields(id), formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const { data } = await clientApi.get<{ data: ApiEmployee["custom_file_fields"] }>(API.employees.customFileFields(id));
      setCustomFileFields(
        (data.data ?? []).map(f => ({
          id: f.id, field_key: f.field_key, file_url: f.file,
          file_name: f.file_name, file_size: f.file_size, uploaded_at: f.uploaded_at,
        })),
      );
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setFileUploadError(msg || "Failed to upload file. Please try again.");
    } finally {
      setUploadingFileKey(null);
    }
  }

  async function onDeleteCustomFile(_fieldKey: string, valueId: number) {
    setFileUploadError("");
    try {
      await clientApi.delete(API.onboarding.customFileFieldDetail(valueId));
      setCustomFileFields(prev => prev.filter(v => v.id !== valueId));
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setFileUploadError(msg || "Failed to delete file. Please try again.");
    }
  }

  const activeTab = PROFILE_TABS.find(t => t.id === tab)!;
  const isPendingOnboarding = onboardingStatus === "pending" || onboardingStatus === "draft";

  return (
    <div>
      <ProfileHeader
        employee={employee}
        employeeUuid={employeeUuid}
      />

      {isPendingOnboarding ? (
        <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] p-14 text-center mt-4">
          <div className="w-14 h-14 rounded-2xl bg-[var(--bg-mid)] flex items-center justify-center mx-auto mb-4">
            <i className="ti ti-clipboard-text text-[26px] text-[var(--primary)]" />
          </div>
          <h3 className="text-[16px] font-semibold text-[var(--on-bg)] mb-1.5">
            Onboarding form not submitted
          </h3>
          <p className="text-[13px] text-[var(--on-variant)] max-w-sm mx-auto">
            This employee has not yet submitted their onboarding form for approval.
            Profile details will appear here once they submit and HR approves their application.
          </p>
          <div className="mt-5">
            <span className="badge badge-warn" style={{ fontSize: "0.8rem", padding: "5px 12px" }}>
              <i className="ti ti-clock-hour-4 mr-1" />
              {onboardingStatus === "draft" ? "Form saved as draft" : "Awaiting employee submission"}
            </span>
          </div>
          {canEditOnboarding && (
            <div className="mt-5">
              <Link href={`/dashboard/employees/${id}/onboarding`} className="btn btn-filled">
                <i className="ti ti-clipboard-check" /> Complete Onboarding for this Employee
              </Link>
            </div>
          )}
        </div>
      ) : (
        <>
          <ProfileTabBar active={tab} onChange={setTab} />

          {justSaved && (
            <div className="flex items-center gap-2 px-4 py-2.5 mb-4 rounded-lg bg-[var(--success-c)] text-[var(--success)] text-[13px] font-medium">
              <i className="ti ti-circle-check text-[16px]" />
              Changes saved successfully.
            </div>
          )}
          {saveError && (
            <div className="flex items-center gap-2 px-4 py-2.5 mb-4 rounded-lg bg-[var(--error-c)] text-[var(--error)] text-[13px] font-medium">
              <i className="ti ti-alert-circle text-[16px]" />
              {saveError}
            </div>
          )}
          {fileUploadError && (
            <div className="flex items-center gap-2 px-4 py-2.5 mb-4 rounded-lg bg-[var(--error-c)] text-[var(--error)] text-[13px] font-medium">
              <i className="ti ti-alert-circle text-[16px]" />
              {fileUploadError}
            </div>
          )}
        </>
      )}

      {!isPendingOnboarding && (tab === "profile" ? (
        <div style={{ display: "flex", gap: "1rem", alignItems: "flex-start" }}>
          <div style={{ width: "220px", flexShrink: 0 }}>
            <ProfileSidebar active={sectionId} onChange={setSectionId} />
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <ProfileForm
              section={section}
              values={values}
              rows={tables[sectionId] ?? []}
              dirty={dirty}
              saving={saving}
              liveDocuments={sectionId === "documents" ? employee.documents : undefined}
              onUploadDocument={onUploadDocument}
              uploadingDocType={uploadingDocType}
              docUploadError={docUploadError}
              fieldOptions={{
                ssRole: [
                  { value: "", label: "Select role" },
                  ...(values.ssRole && !roleOptions.find(o => o.value === values.ssRole)
                    ? [{ value: values.ssRole, label: values.ssRole }]
                    : []),
                  ...roleOptions,
                ],
                branch: [
                  { value: "", label: "Select branch" },
                  ...(values.branch && !branchOptions.find(o => o.value === values.branch)
                    ? [{ value: values.branch, label: values.branch }]
                    : []),
                  ...branchOptions,
                ],
              }}
              fieldSlot={(key, disabled) => {
                if (key === "permanentSameAsCurrent") {
                  // No informational value in read mode — the permanent
                  // fields below already display whatever was actually
                  // saved (the backend keeps them mirroring current_* when
                  // this is on), so showing the toggle itself there too
                  // would be redundant.
                  if (disabled) return "hidden";
                  return (
                    <label className="module-check">
                      <input
                        type="checkbox"
                        checked={values.permanentSameAsCurrent === "true"}
                        onChange={e => onFieldChange("permanentSameAsCurrent", e.target.checked ? "true" : "false")}
                      />
                      <span>Permanent address is the same as current address</span>
                    </label>
                  );
                }
                if (
                  !disabled
                  && values.permanentSameAsCurrent === "true"
                  && ["permanentAddress", "permanentAddressLine2", "permanentVillage", "permanentDistrict", "permanentState", "permanentPinCode"].includes(key)
                ) {
                  return "hidden";
                }
                if (key === "reportingManager") {
                  // Read mode: let ProfileForm show the value as a standard readonly field (always visible)
                  if (disabled) return null;
                  return (
                    <EmployeePickerInline
                      label="Reporting Manager"
                      value={values.reportingManager ?? ""}
                      selectedId={values.reportingManagerId ?? ""}
                      disabled={false}
                      listEndpoint={values.branch ? `${API.employees.managerList}?branch=${encodeURIComponent(values.branch)}` : API.employees.managerList}
                      onSelect={(uuid, name) =>
                        setValues(v => ({ ...v, reportingManager: name ?? "", reportingManagerId: uuid ?? "" }))
                      }
                    />
                  );
                }
                if (key === "reportingApprover") {
                  // Read mode: let ProfileForm show the value as a standard readonly field (always visible)
                  if (disabled) return null;
                  return (
                    <EmployeePickerInline
                      label="Reporting Approver"
                      value={values.reportingApprover ?? ""}
                      selectedId={values.reportingApproverId ?? ""}
                      disabled={false}
                      listEndpoint={values.branch ? `${API.employees.managerList}?branch=${encodeURIComponent(values.branch)}` : API.employees.managerList}
                      onSelect={(uuid, name) =>
                        setValues(v => ({ ...v, reportingApprover: name ?? "", reportingApproverId: uuid ?? "" }))
                      }
                    />
                  );
                }
                if (key === "hr") {
                  // Read mode: let ProfileForm show the value as a standard readonly field (always visible)
                  if (disabled) return null;
                  return (
                    <EmployeePickerInline
                      label="Company Code HR"
                      value={values.hr ?? ""}
                      selectedId={values.hrId ?? ""}
                      disabled={false}
                      listEndpoint={values.branch ? `${API.employees.hrList}?branch=${encodeURIComponent(values.branch)}` : API.employees.hrList}
                      onSelect={(uuid, name) =>
                        setValues(v => ({ ...v, hr: name ?? "", hrId: uuid ?? "" }))
                      }
                    />
                  );
                }
                const fileFieldConfig = Object.values(fieldConfig).flat().find(
                  c => c.field_key === key && c.is_custom && c.field_type === "file",
                );
                if (fileFieldConfig) {
                  return (
                    <CustomFieldFileUpload
                      fieldKey={fileFieldConfig.field_key}
                      label={fileFieldConfig.label}
                      required={fileFieldConfig.required}
                      allowMultiple={fileFieldConfig.allow_multiple}
                      value={customFileFields.filter(v => v.field_key === fileFieldConfig.field_key)}
                      uploading={uploadingFileKey === fileFieldConfig.field_key}
                      onUpload={onUploadCustomFile}
                      onDelete={disabled ? undefined : onDeleteCustomFile}
                      disabled={disabled}
                    />
                  );
                }
                return null;
              }}
              readOnly={!isEditing}
              onEdit={canEdit ? () => setIsEditing(true) : undefined}
              onFieldChange={onFieldChange}
              onRowsChange={onRowsChange}
              onSave={onSave}
              onCancel={onCancel}
            />
          </div>
        </div>
      ) : tab === "salary" ? (
        <SalaryTab employeeId={employeeUuid} employeeCode={id} />
      ) : tab === "payroll" ? (
        <PayrollTab employeeId={employeeUuid} />
      ) : tab === "leave" ? (
        <LeaveTab employeeId={id} />
      ) : tab === "attendance" ? (
        <AttendanceTab employeeId={id} />
      ) : tab === "approval" ? (
        <ApprovalMatrixTab
          employeeCode={id}
          branch={values.branch ?? ""}
          defaultManagerId={values.reportingManagerId ?? ""}
          defaultManagerName={values.reportingManager ?? ""}
          defaultManagerFromOrgChart={values.reportingManagerFromOrgChart === "true"}
          defaultHrId={values.hrId ?? ""}
          defaultHrName={values.hr ?? ""}
          onManagerChanged={(id, name) => setValues(v => ({ ...v, reportingManager: name, reportingManagerId: id }))}
          onHrChanged={(id, name) => setValues(v => ({ ...v, hr: name, hrId: id }))}
        />
      ) : tab === "promotion" ? (
        <PromotionTab
          employeeId={id}
          employeeName={employee.firstName + (employee.lastName ? " " + employee.lastName : "")}
          currentDesignation={values.designation ?? ""}
          currentRole={values.ssRole ?? "employee"}
          currentPositionId={currentPositionId}
          currentOrgUnitId={currentOrgUnitId}
          roleOptions={roleOptions}
          onPositionReassigned={onPositionReassigned}
        />
      ) : tab === "wishes" ? (
        <WishesTab
          employeeId={id}
          employeeName={employee.firstName + (employee.lastName ? " " + employee.lastName : "")}
          employeeEmail={employee.email}
          dateOfBirth={employee.dateOfBirth}
          dateOfJoining={employee.dateOfJoining}
        />
      ) : tab === "audit" ? (
        <AuditTrailTab employeeUuid={employeeUuid} />
      ) : (
        <TabPlaceholder icon={activeTab.icon} label={activeTab.label} />
      ))}
    </div>
  );
}

function TabPlaceholder({ icon, label }: { icon: string; label: string }) {
  return (
    <div className="bg-[var(--surface)] rounded-xl border border-[var(--outline-v)] p-14 text-center">
      <div className="w-14 h-14 rounded-2xl bg-[var(--bg-mid)] flex items-center justify-center mx-auto mb-4">
        <i className={`ti ${icon} text-[26px] text-[var(--primary)]`} />
      </div>
      <h3 className="text-[16px] font-semibold text-[var(--on-bg)] mb-1.5">{label}</h3>
      <p className="text-[13px] text-[var(--on-variant)] max-w-sm mx-auto">
        The {label} module will appear here. This tab is wired and ready for its content.
      </p>
    </div>
  );
}

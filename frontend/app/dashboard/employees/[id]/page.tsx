"use client";

import { use, useState, useEffect } from "react";
import Link from "next/link";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import {
  PROFILE_SECTIONS,
  PROFILE_TABS,
  type DetailValues,
  type DocEntry,
  type FieldOption,
  type TableRow,
  type Employee,
  type EmployeeStatus,
  type Gender,
} from "../_data";
import ProfileHeader from "./_components/ProfileHeader";
import ProfileTabBar from "./_components/ProfileTabBar";
import ProfileSidebar from "./_components/ProfileSidebar";
import ProfileForm from "./_components/ProfileForm";
import { EmployeePickerInline } from "./_components/ReportingManagerCard";
import { ApprovalMatrixTab } from "./_components/ApprovalMatrixTab";
import { WishesTab } from "./_components/WishesTab";
import { LeaveTab } from "./_components/LeaveTab";
import { AttendanceTab } from "./_components/AttendanceTab";

interface ApiProfile {
  date_of_birth?: string; gender?: string; marital_status?: string;
  father_name?: string; blood_group?: string;
  current_address?: string; permanent_address?: string;
  highest_qualification?: string; institution?: string;
  year_of_passing?: string | number; specialization?: string;
  total_experience_years?: string; previous_employer?: string;
  previous_designation?: string; leaving_reason?: string;
  account_number?: string; ifsc_code?: string; bank_name?: string;
  bank_branch_name?: string; account_holder_name?: string; account_type?: string;
  emergency_name?: string; emergency_relationship?: string;
  emergency_phone?: string; emergency_email?: string;
}

interface ApiDocument {
  id: number;
  document_type: string;
  document_type_display: string;
  file: string;
  file_name: string;
  file_size: number;
  uploaded_at: string;
}

interface ApiEmployee {
  id: string; employee_id: string;
  first_name: string; last_name: string; full_name: string;
  email: string; phone: string;
  department: string; designation: string; branch: string;
  role: string; role_display: string;
  date_of_joining: string; is_active: boolean; status: string;
  onboarding_status: string;
  reporting_manager: { id: string; name: string } | null;
  hr:                { id: string; name: string } | null;
  profile?: ApiProfile;
  documents?: ApiDocument[];
}

const DOC_MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function buildDocEntries(apiDocs: ApiDocument[]): DocEntry[] {
  // Use the static expected document types as the base list so the cards section
  // always shows all document slots — uploaded ones get their file info merged in.
  const docsSection = PROFILE_SECTIONS.find(s => s.id === "documents");
  const base: DocEntry[] = docsSection?.kind === "docs" ? [...docsSection.documents] : [];

  return base.map(expected => {
    const uploaded = apiDocs.find(d => d.document_type_display === expected.name);
    if (!uploaded) return expected;
    const dt = new Date(uploaded.uploaded_at);
    return {
      ...expected,
      status: "pending" as const,
      uploadedOn: `${DOC_MONTHS[dt.getMonth()]} ${dt.getDate()}, ${dt.getFullYear()}`,
      fileUrl: uploaded.file,
      fileName: uploaded.file_name,
      fileSize: uploaded.file_size,
    };
  });
}

function apiToEmployee(u: ApiEmployee): Employee {
  const p: ApiProfile = u.profile ?? {};
  return {
    id:            u.employee_id || u.id,
    code:          u.employee_id || u.id,
    firstName:     u.first_name,
    middleName:    "",
    lastName:      u.last_name,
    email:         u.email,
    phone:         u.phone || "",
    department:    u.department || "",
    designation:   u.designation || "",
    dateOfJoining: u.date_of_joining || "",
    dateOfBirth:   p.date_of_birth || "",
    location:      u.branch || "",
    gender:        (p.gender as Gender) || "male",
    status:        (u.status as EmployeeStatus) || (u.is_active ? "active" : "inactive"),
    details: {
      // Basic
      code:          u.employee_id,
      firstName:     u.first_name,
      middleName:    "",
      lastName:      u.last_name,
      gender:        p.gender || "",
      dateOfBirth:   p.date_of_birth || "",
      dateOfJoining: u.date_of_joining || "",
      department:    u.department || "",
      designation:   u.designation || "",
      branch:              u.branch || "",
      reportingManager:    u.reporting_manager?.name ?? "",
      reportingManagerId:  u.reporting_manager?.id   ?? "",
      hr:                  u.hr?.name ?? "",
      hrId:                u.hr?.id   ?? "",
      category:          "General",
      esiLocation:   "Corporate",
      metroTds:      "Metro",
      esiDispensary: "N/A",
      nationality:   "Indian",
      loginEmail:    u.email,
      personalEmail: u.email,
      ssRole:        u.role_display || "Employee",
      portalAccess:  "enabled",
      mobileNumber:  u.phone || "",
      // Personal (from onboarding profile)
      // Backend returns lowercase ("single"); options are Title Case ("Single").
      maritalStatus:    p.marital_status
        ? p.marital_status.charAt(0).toUpperCase() + p.marital_status.slice(1)
        : "",
      fatherName:       p.father_name || "",
      bloodGroup:       p.blood_group || "",
      currentAddress:   p.current_address || "",
      permanentAddress: p.permanent_address || "",
      // Education & experience (from onboarding profile)
      highestQualification: p.highest_qualification || "",
      specialization:       p.specialization || "",
      institution:          p.institution || "",
      yearOfPassing:        p.year_of_passing != null ? String(p.year_of_passing) : "",
      totalExperienceYears: p.total_experience_years || "",
      previousEmployer:     p.previous_employer || "",
      previousDesignation:  p.previous_designation || "",
      leavingReason:        p.leaving_reason || "",
      // Bank details
      accountHolderName: p.account_holder_name || "",
      accountType:       p.account_type || "",
      accountNumber:     p.account_number || "",
      ifscCode:          p.ifsc_code || "",
      bankName:          p.bank_name || "",
      bankBranch:        p.bank_branch_name || "",
      // Emergency contact
      emergencyName:         p.emergency_name || "",
      emergencyRelationship: p.emergency_relationship || "",
      emergencyPhone:        p.emergency_phone || "",
      emergencyEmail:        p.emergency_email || "",
    },
    tables: {},
    documents: buildDocEntries(u.documents ?? []),
  };
}

export default function EmployeeProfilePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const canEdit = usePermission("employees.edit");
  const [tab,       setTab]       = useState<string>("profile");
  const [sectionId, setSectionId] = useState<string>("personal");

  const [employee,          setEmployee]          = useState<Employee | null>(null);
  const [onboardingStatus,  setOnboardingStatus]  = useState<string>("");
  const [loading,           setLoading]           = useState(true);
  const [notFound,          setNotFound]          = useState(false);

  const [values,     setValues]     = useState<DetailValues>({});
  const [tables,     setTables]     = useState<Record<string, TableRow[]>>({});
  const [baseValues, setBaseValues] = useState<DetailValues>({});
  const [baseTables, setBaseTables] = useState<Record<string, TableRow[]>>({});
  const [justSaved,  setJustSaved]  = useState(false);
  const [saving,     setSaving]     = useState(false);
  const [saveError,  setSaveError]  = useState(false);
  const [isEditing,  setIsEditing]  = useState(false);

  const [deptOptions,     setDeptOptions]     = useState<FieldOption[]>([]);
  const [allDesigs,       setAllDesigs]       = useState<{ name: string; department_name: string }[]>([]);
  const [desigOptions,    setDesigOptions]    = useState<FieldOption[]>([]);
  const [roleOptions,     setRoleOptions]     = useState<FieldOption[]>([]);
  const [branchOptions,   setBranchOptions]   = useState<FieldOption[]>([]);

  // fetch dropdown lists once on mount
  useEffect(() => {
    Promise.all([
      clientApi.get<{ data: { results: { id: number; name: string }[] } }>(API.departments.list),
      clientApi.get<{ data: unknown }>(API.designations.list),
      clientApi.get<{ data: { results: { id: number; name: string; display_name: string }[] } }>(`${API.roles.list}?page_size=100`),
      clientApi.get<{ data: { results: { id: number; branch_name: string }[] } }>(API.branches.list),
    ]).then(([depts, desigs, roles, branches]) => {
      setDeptOptions(depts.data.data.results.map(d => ({ value: d.name, label: d.name })));
      const desigData = desigs.data.data as { results?: { name: string; department_name: string }[] } | { name: string; department_name: string }[];
      const desigArray = Array.isArray(desigData) ? desigData : (desigData.results ?? []);
      setAllDesigs(desigArray);
      setRoleOptions(
        roles.data.data.results
          .filter(r => r.name !== "system_admin")
          .map(r => ({ value: r.display_name, label: r.display_name }))
      );
      setBranchOptions(branches.data.data.results.map(b => ({ value: b.branch_name, label: b.branch_name })));
    }).catch(() => {});
  }, []);

  // filter designations whenever the selected department changes
  useEffect(() => {
    const dept = values.department;
    if (!dept) { setDesigOptions([]); return; }
    const filtered = allDesigs
      .filter(d => d.department_name === dept)
      .map(d => ({ value: d.name, label: d.name }));
    setDesigOptions(filtered);
  }, [values.department, allDesigs]);

  useEffect(() => {
    setLoading(true);
    setNotFound(false);
    clientApi
      .get<{ data: ApiEmployee }>(API.employees.detail(id))
      .then(({ data }) => {
        const raw = data.data;
        const emp = apiToEmployee(raw);
        setEmployee(emp);
        setOnboardingStatus(raw.onboarding_status ?? "");
        setValues({ ...emp.details });
        setBaseValues({ ...emp.details });
        setTables({});
        setBaseTables({});
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));
  }, [id]);

  const section = PROFILE_SECTIONS.find(s => s.id === sectionId)!;

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
      <div className="bg-white rounded-xl border border-[var(--outline-v)] p-12 text-center max-w-lg mx-auto mt-10">
        <i className="ti ti-user-question text-5xl text-[var(--outline)] block mb-4" />
        <h2 className="text-[17px] font-semibold text-[var(--on-bg)] mb-1.5">Employee not found</h2>
        <p className="text-[13px] text-[var(--on-variant)] mb-5">
          No employee exists with code <span className="font-semibold">{id}</span>.
        </p>
        <Link
          href="/dashboard/employees"
          className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-[13px] font-semibold bg-[var(--primary)] text-white hover:bg-[#163d72] transition-colors"
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
  const ROLE_SLUG: Record<string, string> = {
    "Employee": "employee", "HR Admin": "hr_admin", "Manager": "manager",
    "System Admin": "system_admin", "Finance Manager": "finance_manager",
  };

  async function onSave() {
    setSaving(true);
    setSaveError(false);
    setJustSaved(false);
    try {
      const employeePayload = {
        // Employment fields
        department:             values.department            || null,
        designation:            values.designation           || null,
        branch:                 values.branch                || null,
        role:                   ROLE_SLUG[values.ssRole]     || null,
        is_active:              employee?.status !== "inactive",
        reporting_manager_id:   values.reportingManagerId   || null,
        hr_id:                  values.hrId                  || null,
        // Personal fields
        date_of_birth:          values.dateOfBirth          || null,
        gender:                 values.gender               || null,
        marital_status:         values.maritalStatus?.toLowerCase() || null,
        father_name:            values.fatherName           || null,
        blood_group:            values.bloodGroup           || null,
        current_address:        values.currentAddress       || null,
        permanent_address:      values.permanentAddress     || null,
        // Education & experience
        highest_qualification:  values.highestQualification || null,
        institution:            values.institution          || null,
        year_of_passing:        values.yearOfPassing        || null,
        specialization:         values.specialization       || null,
        total_experience_years: values.totalExperienceYears || null,
        previous_employer:      values.previousEmployer     || null,
        previous_designation:   values.previousDesignation  || null,
        leaving_reason:         values.leavingReason        || null,
        // Bank details
        account_holder_name:    values.accountHolderName    || null,
        account_type:           values.accountType          || null,
        account_number:         values.accountNumber        || null,
        ifsc_code:              values.ifscCode             || null,
        bank_name:              values.bankName             || null,
        bank_branch_name:       values.bankBranch           || null,
        // Emergency contact
        emergency_name:         values.emergencyName        || null,
        emergency_relationship: values.emergencyRelationship || null,
        emergency_phone:        values.emergencyPhone       || null,
        emergency_email:        values.emergencyEmail       || null,
      };

      await clientApi.put(API.employees.detail(id), employeePayload);

      setBaseValues(values);
      setBaseTables(tables);
      setJustSaved(true);
      setIsEditing(false);
    } catch {
      setSaveError(true);
    } finally {
      setSaving(false);
    }
  }
  function onCancel() {
    setValues(baseValues);
    setTables(baseTables);
    setJustSaved(false);
    setIsEditing(false);
  }

  const activeTab = PROFILE_TABS.find(t => t.id === tab)!;
  const isPendingOnboarding = onboardingStatus === "pending" || onboardingStatus === "draft";

  return (
    <div>
      <ProfileHeader employee={employee} />

      {isPendingOnboarding ? (
        <div className="bg-white rounded-xl border border-[var(--outline-v)] p-14 text-center mt-4">
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
              Failed to save changes. Please try again.
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
              fieldOptions={{
                department:  [{ value: "", label: "Select department" }, ...deptOptions],
                designation: [
                  { value: "", label: desigOptions.length || values.designation ? "Select designation" : "Select a department first" },
                  ...(values.designation && !desigOptions.find(o => o.value === values.designation)
                    ? [{ value: values.designation, label: values.designation }]
                    : []),
                  ...desigOptions,
                ],
                ssRole:      [{ value: "", label: "Select role" }, ...roleOptions],
                branch:      [{ value: "", label: "Select branch" }, ...branchOptions],
              }}
              fieldSlot={(key, disabled) => {
                if (key === "reportingManager") {
                  return (
                    <EmployeePickerInline
                      label="Reporting Manager"
                      value={values.reportingManager ?? ""}
                      selectedId={values.reportingManagerId ?? ""}
                      disabled={disabled}
                      listEndpoint={values.branch ? `${API.employees.managerList}?branch=${encodeURIComponent(values.branch)}` : API.employees.managerList}
                      onSelect={(uuid, name) =>
                        setValues(v => ({ ...v, reportingManager: name ?? "", reportingManagerId: uuid ?? "" }))
                      }
                    />
                  );
                }
                if (key === "hr") {
                  return (
                    <EmployeePickerInline
                      label="Branch HR"
                      value={values.hr ?? ""}
                      selectedId={values.hrId ?? ""}
                      disabled={disabled}
                      listEndpoint={values.branch ? `${API.employees.hrList}?branch=${encodeURIComponent(values.branch)}` : API.employees.hrList}
                      onSelect={(uuid, name) =>
                        setValues(v => ({ ...v, hr: name ?? "", hrId: uuid ?? "" }))
                      }
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
      ) : tab === "leave" ? (
        <LeaveTab employeeId={id} />
      ) : tab === "attendance" ? (
        <AttendanceTab employeeId={id} />
      ) : tab === "approval" ? (
        <ApprovalMatrixTab
          employeeCode={id}
          branch={values.branch ?? ""}
          defaultManagerId={values.reportingManagerId ?? ""}
          defaultHrId={values.hrId ?? ""}
        />
      ) : tab === "wishes" ? (
        <WishesTab
          employeeId={id}
          employeeName={employee.firstName + (employee.lastName ? " " + employee.lastName : "")}
          employeeEmail={employee.email}
          dateOfBirth={employee.dateOfBirth}
          dateOfJoining={employee.dateOfJoining}
        />
      ) : (
        <TabPlaceholder icon={activeTab.icon} label={activeTab.label} />
      ))}
    </div>
  );
}

function TabPlaceholder({ icon, label }: { icon: string; label: string }) {
  return (
    <div className="bg-white rounded-xl border border-[var(--outline-v)] p-14 text-center">
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

// Pure API-response-to-Employee mapping for the Employee Profile page — no
// component state, safe to import from anywhere.

import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import { formatDate } from "@/lib/formatDate";
import {
  PROFILE_SECTIONS,
  applyDocumentTypeConfig,
  type ApiDocument,
  type DocEntry,
  type Employee,
  type EmployeeStatus,
  type Gender,
} from "../_data";

export interface ApiProfile {
  date_of_birth?: string; gender?: string; marital_status?: string;
  father_name?: string; blood_group?: string;
  current_address?: string; current_address_line2?: string;
  current_village?: string; current_district?: string; current_state?: string; current_pin_code?: string;
  permanent_address?: string; permanent_address_line2?: string;
  permanent_village?: string; permanent_district?: string; permanent_state?: string; permanent_pin_code?: string;
  permanent_same_as_current?: boolean;
  highest_qualification?: string; institution?: string;
  year_of_passing?: string | number; specialization?: string;
  total_experience_years?: string; previous_employer?: string;
  previous_designation?: string; leaving_reason?: string;
  account_number?: string; ifsc_code?: string; bank_name?: string;
  bank_branch_name?: string; account_holder_name?: string; account_type?: string;
  emergency_name?: string; emergency_relationship?: string;
  emergency_phone?: string; emergency_email?: string;
  uan_number?: string; name_as_per_aadhar?: string; esi_number?: string;
  custom_field_values?: Record<string, string>;
}

export interface ApiEmployee {
  id: string; uuid: string; employee_id: string;
  first_name: string; last_name: string; full_name: string;
  email: string; phone: string;
  department: string; designation: string; branch: string;
  position_id: string | null; org_unit_id: string | null;
  role: string; role_display: string;
  date_of_joining: string; is_active: boolean; status: string;
  onboarding_status: string;
  employment_status: string;
  confirmation_date: string | null;
  reporting_manager:  { id: string; uuid: string | null; name: string; from_org_chart: boolean } | null;
  reporting_approver: { id: string; uuid: string | null; name: string } | null;
  hr:                 { id: string; uuid: string | null; name: string } | null;
  profile?: ApiProfile;
  documents?: ApiDocument[];
  custom_file_fields?: { id: number; field_key: string; file: string; file_name: string; file_size: number; uploaded_at: string }[];
}

export function buildDocEntries(apiDocs: ApiDocument[], documentTypeConfig: DocumentTypeConfig[] = []): DocEntry[] {
  // Base list of expected document type "slots" so the cards section always
  // shows every configured type — uploaded ones get their file info merged
  // in. Config-driven when it's loaded (applyDocumentTypeConfig), falling
  // back to the static built-in list otherwise (same fallback
  // applyDocumentTypeConfig itself uses, so behavior matches exactly whether
  // called here or wherever else the section is rendered).
  const docsSection = PROFILE_SECTIONS.find(s => s.id === "documents");
  const configuredSection = docsSection ? applyDocumentTypeConfig(docsSection, documentTypeConfig) : undefined;
  const base: DocEntry[] = configuredSection?.kind === "docs" ? [...configuredSection.documents] : [];

  return base.map(expected => {
    const uploaded = apiDocs.find(d => d.document_type === expected.documentType);
    if (!uploaded) return expected;
    const dt = new Date(uploaded.uploaded_at);
    return {
      ...expected,
      status: "pending" as const,
      uploadedOn: formatDate(dt),
      fileUrl: uploaded.file,
      fileName: uploaded.file_name,
      fileSize: uploaded.file_size,
    };
  });
}

export function apiToEmployee(u: ApiEmployee, documentTypeConfig: DocumentTypeConfig[] = []): Employee {
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
    employmentStatus: u.employment_status || "probation",
    confirmationDate: u.confirmation_date,
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
      // .uuid, not .id — reporting_manager.id is the display employee code
      // (e.g. "RSS000183"), not a real primary key. Echoing that back as
      // reporting_manager_id on save fails UUID parsing on the backend and
      // returns "Reporting manager not found or is inactive." even when a
      // perfectly valid manager is already assigned. Same reasoning for hr
      // and reporting_approver below.
      reportingManagerId:  u.reporting_manager?.uuid ?? "",
      // "true"/"false" string, not boolean — DetailValues is a plain string
      // bag (see _data.ts), same convention every other field here follows.
      reportingManagerFromOrgChart: u.reporting_manager?.from_org_chart ? "true" : "false",
      reportingApprover:   u.reporting_approver?.name ?? "",
      reportingApproverId: u.reporting_approver?.uuid ?? "",
      hr:                  u.hr?.name ?? "",
      hrId:                u.hr?.uuid ?? "",
      category:          "General",
      esiLocation:   "Corporate",
      metroTds:      "Metro",
      esiDispensary: "N/A",
      nationality:   "Indian",
      loginEmail:    u.email,
      personalEmail: u.email,
      ssRole:        u.role || "employee",
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
      currentAddressLine2: p.current_address_line2 || "",
      currentVillage:   p.current_village || "",
      currentDistrict:  p.current_district || "",
      currentState:     p.current_state || "",
      currentPinCode:   p.current_pin_code || "",
      permanentAddress: p.permanent_address || "",
      permanentAddressLine2: p.permanent_address_line2 || "",
      permanentVillage:  p.permanent_village || "",
      permanentDistrict: p.permanent_district || "",
      permanentState:    p.permanent_state || "",
      permanentPinCode:  p.permanent_pin_code || "",
      permanentSameAsCurrent: p.permanent_same_as_current ? "true" : "false",
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
      // EPF / Statutory
      uanNumber:       p.uan_number          || "",
      nameAsPerAadhar: p.name_as_per_aadhar  || "",
      esiNumber:       p.esi_number          || "",
      // HR-created custom fields (Settings > Onboarding Fields) — keyed by
      // their own snake_case field_key, never collides with the camelCase
      // keys above.
      ...(p.custom_field_values ?? {}),
    },
    tables: {},
    documents: buildDocEntries(u.documents ?? [], documentTypeConfig),
  };
}


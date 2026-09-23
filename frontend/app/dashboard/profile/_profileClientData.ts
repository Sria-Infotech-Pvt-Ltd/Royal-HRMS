import { formatDate } from "@/lib/formatDate";
import type { Employee } from "@/app/dashboard/employees/_data";
import type { DocumentTypeConfig } from "@/types/documentTypeConfig";
import { PROFILE_SECTIONS, applyDocumentTypeConfig, type DocEntry } from "@/app/dashboard/employees/_data";

export interface AssignedPerson {
  id:   string | null;
  name: string | null;
}

export interface ProfileData {
  full_name:         string;
  email:             string;
  phone:             string | null;
  employee_id:       string;
  department:        string;
  designation:       string;
  branch:            string;
  role_display:      string;
  date_of_joining:   string | null;
  date_joined:       string | null;
  work_location:     string | null;
  reporting_manager:  AssignedPerson | null;
  reporting_approver: AssignedPerson | null;
  hr:                 AssignedPerson | null;
  profile:           {
    date_of_birth: string | null;
    current_address?: string | null;
    current_address_line2?: string | null;
    current_village?: string | null;
    current_district?: string | null;
    current_state?: string | null;
    current_pin_code?: string | null;
    permanent_address?: string | null;
    permanent_address_line2?: string | null;
    permanent_village?: string | null;
    permanent_district?: string | null;
    permanent_state?: string | null;
    permanent_pin_code?: string | null;
    permanent_same_as_current?: boolean;
    emergency_name?: string | null;
    emergency_relationship?: string | null;
    emergency_phone?: string | null;
    emergency_email?: string | null;
  } | null;
  profile_photo_url: string | null;
}

export interface DocumentItem {
  id:                    number;
  document_type:         string;
  document_type_display: string;
  file_url:              string;
  file_name:             string;
  file_size:             number;
  uploaded_at:           string;
}

export const DOC_ACCEPT = ".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png";

export function buildDocEntries(apiDocs: DocumentItem[], documentTypeConfig: DocumentTypeConfig[] = []): (DocEntry & { docId?: number })[] {
  const docsSection = PROFILE_SECTIONS.find(s => s.id === "documents");
  const configuredSection = docsSection ? applyDocumentTypeConfig(docsSection, documentTypeConfig) : undefined;
  const base = configuredSection?.kind === "docs" ? configuredSection.documents : [];
  return base.map(expected => {
    const uploaded = apiDocs.find(d => d.document_type === expected.documentType);
    if (!uploaded) return expected;
    return {
      ...expected,
      fileUrl:  uploaded.file_url,
      fileName: uploaded.file_name,
      fileSize: uploaded.file_size,
      docId:    uploaded.id,
    };
  });
}

export function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function initials(name: string) {
  return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return formatDate(d);
}

export function toDrawerEmployee(d: ProfileData): Employee {
  const [firstName, ...rest] = (d.full_name || "").split(" ");
  return {
    id: d.employee_id, code: d.employee_id,
    firstName: firstName || "", middleName: "", lastName: rest.join(" "),
    email: d.email, phone: d.phone ?? "",
    department: d.department, designation: d.designation,
    dateOfJoining: d.date_of_joining ?? d.date_joined ?? "", dateOfBirth: "",
    location: d.branch, gender: "male",
    status: "active", employmentStatus: "probation", confirmationDate: null,
    details: {}, tables: {},
  };
}

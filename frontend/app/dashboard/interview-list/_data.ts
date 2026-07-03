import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface CandidateDocument {
  id: number;
  document_type: string;
  document_type_display: string;
  file_url: string;
  file_name: string;
  file_size?: number;
}

export type CandidateStatus =
  | "pending"
  | "screening"
  | "interview_scheduled"
  | "interview_done"
  | "selected"
  | "offer_sent"
  | "rejected"
  | "converted";

export type InterviewMode = "in_person" | "video_call" | "phone";
export type LogType       = "success" | "error" | "info" | "warn";

export interface CandidateLog {
  id:          number;
  log_type:    LogType;
  title:       string;
  description: string;
  created_at:  string;
}

export interface Branch {
  id:          number;
  branch_name: string;
  branch_code: string;
  status:      string;
}

export type AssessmentStatus = "pending" | "complete";

export interface Candidate {
  id:                       number;
  name:                     string;
  email:                    string;
  phone:                    string;
  position_applied:         string;
  branch:                   number | null;
  branch_name:              string;
  interview_date:           string | null;
  interviewer:              number | null;
  interviewer_name:         string;
  interview_mode:           InterviewMode;
  notes:                    string;
  status:                   CandidateStatus;
  referral_by:              number | null;
  referral_by_name:         string;
  details_filled:           boolean;
  hr_approved:              boolean;
  portal_credentials_sent:  boolean;
  portal_user:              string | null;
  assessment_status:        AssessmentStatus | null;
  added_by_name:            string;
  created_at:               string;
  updated_at:               string;
  logs?:                    CandidateLog[];
  documents?:               CandidateDocument[];
}

export interface CandidateEmail {
  id:                 number;
  template_used:      string;
  subject:            string;
  to_email:           string;
  status:             "sent" | "failed";
  sent_by_name:       string;
  sent_at:            string;
  candidate:          number;
  candidate_name:     string;
  candidate_position: string;
}

export interface EmailTemplate {
  id:                  number;
  name:                string;
  display_name:        string;
  subject:             string;
  body:                string;
  available_variables: string[];
  is_active:           boolean;
}

export interface RecruitmentStats {
  total:          number;
  pending:        number;
  selected:       number;
  rejected:       number;
  pending_review: number;
}

export interface PaginatedCandidates {
  count:       number;
  page:        number;
  page_size:   number;
  total_pages: number;
  results:     Candidate[];
}

// ─── API helpers ──────────────────────────────────────────────────────────────

export const RECRUITMENT_API = {
  stats:       () =>
    clientApi.get<{ data: RecruitmentStats }>(API.recruitment.stats),
  list:        (params?: { status?: string; search?: string; branch?: number }) =>
    clientApi.get<{ data: PaginatedCandidates }>(API.recruitment.candidates, { params }),
  create:      (body: Partial<Candidate>) =>
    clientApi.post<{ data: Candidate }>(API.recruitment.candidates, body),
  detail:      (id: number) =>
    clientApi.get<{ data: Candidate }>(API.recruitment.detail(id)),
  getStatuses: () =>
    clientApi.get<{ data: { value: CandidateStatus; label: string }[] }>(API.recruitment.status),
  setStatus:   (id: number, body: { status: CandidateStatus; remarks?: string; template_name?: string }) =>
    clientApi.patch<{ data: Candidate }>(API.recruitment.candidateStatus(id), body),
  hrDecision:  (id: number, body: {
    decision:       "approve" | "reject";
    remarks?:       string;
    template_name?: string;
    extra_context?: Record<string, string>;
  }) =>
    clientApi.patch<{ data: Candidate }>(API.recruitment.hrDecision(id), body),
  reviewList:     () =>
    clientApi.get<{ data: PaginatedCandidates }>(API.recruitment.review),
  emailTemplates: () =>
    clientApi.get<{ data: { results: Record<string, EmailTemplate[]> } }>(API.settings.emailTemplates),
  emailLogs:      (params?: { search?: string }) =>
    clientApi.get<{ data: CandidateEmail[] }>(API.recruitment.emailLogs, { params }),
  sendPortalLogin: (id: number) =>
    clientApi.post<{ message: string }>(API.recruitment.sendPortalLogin(id)),
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

export const MODE_LABELS: Record<InterviewMode, string> = {
  in_person:  "In-Person",
  video_call: "Video Call",
  phone:      "Phone",
};

export function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export function initials(name: string): string {
  return name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);
}

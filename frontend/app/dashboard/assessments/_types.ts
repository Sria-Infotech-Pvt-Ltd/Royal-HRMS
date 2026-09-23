import { formatDate } from "@/lib/formatDate";

export interface AssessmentSettings {
  default_pass_percentage: number;
  max_attempts:            number;
  time_limit_mins:         number | null;
}

export interface AssessmentSection {
  id: string;
  title: string;
  order: number;
  score: number;
  item_count: number;
}

export interface AssessmentItem {
  id: string;
  item_type: "video" | "quiz";
  title: string;
  order: number;
  section: string | null;   // sent on POST/PUT
  section_id: string | null; // returned by GET
  video_url: string;
  duration_secs: number | null;
  question: string;
  option_a: string; option_b: string; option_c: string; option_d: string;
  correct_option: string;
  pass_score: number;
  created_at: string;
}

export interface SectionBreakdown {
  title: string;
  max_score: number;
  achieved_score: number;
  correct_answers: number;
  total_questions: number;
  percentage: string;
}

export interface AssessmentCandidate {
  id: string;
  assignee_type: string;
  assignee_id: number;
  assignee_name: string;
  assignee_email: string;
  status: "pending" | "in_progress" | "complete";
  attempt_count: number;
  score_percentage: string;
  pass_percentage: number;
  passed: boolean | null;
  sections_breakdown: SectionBreakdown[];
  completed_at: string | null;
  created_at: string;
}

export interface Assessment {
  id: string;
  title: string;
  description: string;
  is_active: boolean;
  is_default: boolean;
  item_count: number;
  assigned_count: number;
  pending_count: number;
  in_progress_count: number;
  completed_count: number;
  candidates: AssessmentCandidate[];
  items: AssessmentItem[];
  created_at: string;
  // per-assessment overrides (null = inherit global)
  pass_percentage:          number;
  max_attempts:             number | null;
  time_limit_mins:          number | null;
  effective_max_attempts:   number;
  effective_time_limit_mins: number | null;
}

export interface AssignEmployee { id: string; employee_id: string; full_name: string; email: string; department: string; }
export interface EmailTemplateOption { name: string; display_name: string; }

export interface AssessmentForm {
  title: string; description: string; is_active: boolean; is_default: boolean;
  pass_percentage: string;
  max_attempts: string;        // "" = inherit global (null), "0" = unlimited
  time_limit_mins: string;     // "" = no limit (null)
}
export const EMPTY: AssessmentForm = {
  title: "", description: "", is_active: true, is_default: false,
  pass_percentage: "70", max_attempts: "", time_limit_mins: "",
};

export function apiErr(e: unknown) {
  return (e as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Action failed.";
}

export function fmt(iso: string | null) {
  if (!iso) return "—";
  return formatDate(iso);
}

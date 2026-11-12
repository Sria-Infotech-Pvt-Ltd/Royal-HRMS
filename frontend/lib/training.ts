// Training & Learning — shared types and pure helpers. The backend
// (apps/training) validates and enforces everything; these give instant
// feedback and consistent labels.
import { API_BASE } from "./config";

export type TrainingStatus = "assigned" | "in_progress" | "completed" | "failed" | "overdue";
export type MaterialType = "video" | "document" | "external_video";
export type Provider = "" | "youtube" | "vimeo" | "direct";

export interface PersonRef { id: string; name: string; employee_id: string; branch: string; department: string }

export interface MaterialProgress {
  opened_at: string | null;
  watched_seconds: number;
  last_position_seconds: number;
  duration_seconds: number | null;
  completed_at: string | null;
  completion_method: "" | "tracked" | "read" | "confirmed";
}

export interface Material {
  id: string;
  title: string;
  description: string;
  material_type: MaterialType;
  order: number;
  is_required: boolean;
  file_format: string;
  file_size: number;
  original_name: string;
  provider: Provider;
  embed_id: string;
  external_url: string;
  duration_seconds: number | null;
  min_view_seconds: number;
  allow_manual_completion: boolean;
  is_tracked: boolean;
  is_archived: boolean;
  progress?: MaterialProgress | null;
}

export interface Course {
  id: string;
  title: string;
  description: string;
  category: string;
  owner: PersonRef | null;
  trainer_name: string;
  has_thumbnail: boolean;
  duration_minutes: number | null;
  is_mandatory: boolean;
  is_active: boolean;
  start_date: string | null;
  deadline: string | null;
  assessment: { id: string; title: string; pass_percentage: number } | null;
  /** Videos don't block the assessment; passing the assessment completes the course. */
  videos_optional?: boolean;
  auto_assign_new_joiners: boolean;
  new_joiner_deadline_days: number;
  new_joiner_branches: string[];
  new_joiner_departments: string[];
  archived: boolean;
  created_at: string;
  assigned_count?: number;
  completed_count?: number;
  material_count?: number;
  materials?: Material[];
}

export interface AssignmentRow {
  id: string;
  employee: PersonRef;
  course_id: string;
  course_title: string;
  status: TrainingStatus;
  source: string;
  due_date: string | null;
  assigned_at: string;
  started_at: string | null;
  completed_at: string | null;
  attempts_used: number;
  best_score_percent: number | null;
  assessment_passed: boolean | null;
  progress_percent?: number;
}

export interface AssessmentState {
  required: boolean;
  title?: string;
  pass_percentage?: number;
  max_attempts?: number;
  attempts_used?: number;
  attempts_left?: number | null;
  time_limit_mins?: number | null;
  unlocked?: boolean;
  can_attempt?: boolean;
  /** Passed, and may retake to improve the score (best score kept, course stays completed). */
  can_retake?: boolean;
  /** false: the assessment has no questions and can't be taken. */
  has_questions?: boolean;
  /** The course start date while it is still in the future. */
  starts_on?: string | null;
  passed?: boolean | null;
  best_score_percent?: number | null;
  last_result?: { percentage: number; passed: boolean; score: number; max_score: number; submitted_at: string } | null;
}

export interface MyTraining extends AssignmentRow {
  progress_percent: number;
  material_count: number;
  course: Course;
  materials?: Material[];
  assessment?: AssessmentState;
  /** The course start date while it is still in the future (nothing opens before it). */
  starts_on?: string | null;
}

export const STATUS_LABEL: Record<TrainingStatus, string> = {
  assigned: "Assigned", in_progress: "In Progress", completed: "Completed", failed: "Failed Assessment",
  overdue: "Overdue",
};

export const STATUS_BADGE: Record<TrainingStatus, string> = {
  assigned: "badge badge-info", in_progress: "badge badge-primary", completed: "badge badge-success",
  failed: "badge badge-error", overdue: "badge badge-warn",
};

export const MATERIAL_ICON: Record<MaterialType, string> = {
  video: "ti-video", document: "ti-file-text", external_video: "ti-brand-youtube",
};

export function materialKindLabel(m: Pick<Material, "material_type" | "file_format" | "provider">): string {
  if (m.material_type === "document") return (m.file_format || "document").toUpperCase();
  if (m.material_type === "video") return "Video";
  return m.provider === "youtube" ? "YouTube" : m.provider === "vimeo" ? "Vimeo" : "Video link";
}

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h}h ${m}m`;
  if (m) return sec ? `${m}m ${sec}s` : `${m}m`;
  return `${sec}s`;
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** What the employee still has to do for one material. */
export function materialHint(m: Material): string {
  const p = m.progress;
  if (p?.completed_at) return "Completed";
  if (m.material_type === "document") {
    if (!p?.opened_at) return "Open the document, then confirm you have read it";
    return m.min_view_seconds ? `Confirm after reading (minimum ${formatDuration(m.min_view_seconds)})` : "Confirm you have read it";
  }
  if (m.is_tracked) {
    const total = p?.duration_seconds || m.duration_seconds;
    const watched = p?.watched_seconds ?? 0;
    return total ? `Watched ${Math.min(100, Math.round((watched / total) * 100))}% — completes at 90%`
      : "Video length not set — ask HR";
  }
  return m.allow_manual_completion ? "Watch it, then confirm" : "Progress can't be tracked for this video — ask HR";
}

export function canConfirm(m: Material): boolean {
  if (m.progress?.completed_at || !m.progress?.opened_at) return false;
  if (m.material_type === "document") return true;
  return !m.is_tracked && m.allow_manual_completion;
}

export function secondsUntilConfirm(m: Material, now: number = Date.now()): number {
  if (m.material_type !== "document" || !m.progress?.opened_at || !m.min_view_seconds) return 0;
  const opened = Date.parse(m.progress.opened_at);
  return Math.max(0, Math.ceil(m.min_view_seconds - (now - opened) / 1000));
}

// ── External links (mirrors apps/training/validation.py; the server decides) ──

const YT_ID = /^[A-Za-z0-9_-]{11}$/;

export function parseVideoLink(raw: string): { provider: Provider; id: string } | { error: string } {
  const url = raw.trim();
  if (!url) return { error: "Paste the video link." };
  let u: URL;
  try { u = new URL(url); } catch { return { error: "That is not a valid link." }; }
  if (u.protocol !== "https:") return { error: "Only secure https:// links are allowed." };
  if (u.username || u.password) return { error: "Links with a user name or password are not allowed." };
  const host = u.hostname.toLowerCase();
  if (host === "localhost" || /^\d+\.\d+\.\d+\.\d+$/.test(host) || host.startsWith("[") || !host.includes("."))
    return { error: "The link must point to a public website." };
  if (host === "youtu.be" || /(^|\.)youtube(-nocookie)?\.com$/.test(host)) {
    let id = "";
    if (host === "youtu.be") id = u.pathname.split("/")[1] ?? "";
    else if (u.pathname === "/watch") id = u.searchParams.get("v") ?? "";
    else {
      const parts = u.pathname.split("/").filter(Boolean);
      if (["embed", "shorts", "live", "v"].includes(parts[0] ?? "")) id = parts[1] ?? "";
    }
    return YT_ID.test(id) ? { provider: "youtube", id } : { error: "That YouTube link has no valid video id." };
  }
  if (/(^|\.)vimeo\.com$/.test(host)) {
    const id = u.pathname.split("/").find(p => /^\d+$/.test(p)) ?? "";
    return id ? { provider: "vimeo", id } : { error: "That Vimeo link has no video id." };
  }
  if (/\.(mp4|webm|m4v)$/i.test(u.pathname)) return { provider: "direct", id: "" };
  return { error: "Supported links: YouTube, Vimeo, or a direct https link to an .mp4 / .webm file." };
}

export function embedUrl(m: Pick<Material, "provider" | "embed_id" | "external_url">, origin = ""): string {
  if (m.provider === "youtube")
    return `https://www.youtube-nocookie.com/embed/${m.embed_id}?enablejsapi=1&rel=0${origin ? `&origin=${encodeURIComponent(origin)}` : ""}`;
  if (m.provider === "vimeo") return `https://player.vimeo.com/video/${m.embed_id}`;
  return m.external_url;
}

/** Same-origin, cookie-authenticated file URL (the API checks access). */
export function fileUrl(materialId: string): string {
  return `${API_BASE}/training/materials/${materialId}/file/`;
}

// ── Upload limits (server enforces its own, configurable, limits) ──

export const DOC_EXTENSIONS = [".pdf", ".pptx", ".docx"];
export const VIDEO_EXTENSIONS = [".mp4", ".webm", ".m4v"];

export function uploadError(file: File | null, kind: "document" | "video", maxMb: number): string {
  if (!file) return kind === "video" ? "Choose a video." : "Choose a file.";
  const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  const allowed = kind === "video" ? VIDEO_EXTENSIONS : DOC_EXTENSIONS;
  if (!allowed.includes(ext))
    return kind === "video" ? "Upload an MP4 or WebM video." : "Upload a PDF, PowerPoint (.pptx) or Word (.docx) file.";
  if (file.size === 0) return "The file is empty.";
  if (file.size > maxMb * 1024 * 1024) return `The file must be ${maxMb} MB or smaller.`;
  return "";
}

// ── Video length (required for tracked videos; the browser's value is never trusted) ──

/** Videos whose playback is tracked need their length from HR. */
export function needsVideoLength(kind: MaterialType, provider: Provider | null): boolean {
  if (kind === "video") return true;
  return kind === "external_video" && (provider === "youtube" || provider === "direct");
}

/** Minutes + seconds fields → seconds (0 when empty or invalid). */
export function videoLengthSeconds(minutes: string, seconds: string): number {
  const m = Number(minutes || 0), s = Number(seconds || 0);
  if (!Number.isInteger(m) || !Number.isInteger(s) || m < 0 || s < 0 || s > 59) return 0;
  return m * 60 + s;
}

/** "12:30" or "12" (minutes) → seconds; null when invalid. */
export function parseVideoLength(text: string): number | null {
  const t = text.trim();
  const m = /^(\d{1,4})(?::([0-5]?\d))?$/.exec(t);
  if (!m) return null;
  const total = Number(m[1]) * 60 + Number(m[2] ?? 0);
  return total > 0 ? total : null;
}

/** ISO date (yyyy-mm-dd) → "05 Dec 2026". */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
}

/** Today as yyyy-mm-dd in local time. */
export function todayIso(now: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
}

export interface CourseForm {
  title: string; description: string; category: string; trainer_name: string;
  duration_minutes: string; is_mandatory: boolean; is_active: boolean;
  start_date: string; deadline: string; assessment: string; videos_optional: boolean;
  auto_assign_new_joiners: boolean; new_joiner_deadline_days: string;
  new_joiner_branches: string[]; new_joiner_departments: string[];
}

export function courseToForm(c?: Course | null): CourseForm {
  return {
    title: c?.title ?? "", description: c?.description ?? "", category: c?.category ?? "",
    trainer_name: c?.trainer_name ?? "", duration_minutes: c?.duration_minutes ? String(c.duration_minutes) : "",
    is_mandatory: c?.is_mandatory ?? false, is_active: c?.is_active ?? true,
    start_date: c?.start_date ?? "", deadline: c?.deadline ?? "", assessment: c?.assessment?.id ?? "",
    videos_optional: c?.videos_optional ?? false,
    auto_assign_new_joiners: c?.auto_assign_new_joiners ?? false,
    new_joiner_deadline_days: String(c?.new_joiner_deadline_days ?? 30),
    new_joiner_branches: c?.new_joiner_branches ?? [], new_joiner_departments: c?.new_joiner_departments ?? [],
  };
}

export function validateCourse(f: CourseForm): Record<string, string> {
  const e: Record<string, string> = {};
  if (!f.title.trim()) e.title = "Give the course a title.";
  if (f.duration_minutes && !/^\d+$/.test(f.duration_minutes)) e.duration_minutes = "Enter whole minutes.";
  if (f.start_date && f.deadline && f.deadline < f.start_date) e.deadline = "The deadline must be on or after the start date.";
  const days = Number(f.new_joiner_deadline_days);
  if (f.auto_assign_new_joiners && (!Number.isInteger(days) || days < 0 || days > 365))
    e.new_joiner_deadline_days = "Enter 0–365 days.";
  if (f.videos_optional && !f.assessment)
    e.videos_optional = "Link an assessment — employees complete the course by passing it.";
  return e;
}

export function courseFormPayload(f: CourseForm, canLinkAssessment: boolean): Record<string, unknown> {
  const out: Record<string, unknown> = {
    title: f.title.trim(), description: f.description, category: f.category, trainer_name: f.trainer_name,
    duration_minutes: f.duration_minutes || null, is_mandatory: f.is_mandatory, is_active: f.is_active,
    start_date: f.start_date || null, deadline: f.deadline || null,
    videos_optional: f.videos_optional,
    auto_assign_new_joiners: f.auto_assign_new_joiners,
    new_joiner_deadline_days: Number(f.new_joiner_deadline_days) || 0,
    new_joiner_branches: f.new_joiner_branches, new_joiner_departments: f.new_joiner_departments,
  };
  if (canLinkAssessment) out.assessment = f.assessment || null;
  return out;
}

export function apiError(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } } })?.response?.data?.message || fallback;
}

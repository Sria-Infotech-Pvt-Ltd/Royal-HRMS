// Pure types + helper functions for the self-service assessments page — no
// component state, safe to import from anywhere.

export type ItemType    = "video" | "quiz";
export type AssignStatus = "pending" | "in_progress" | "complete";

export interface AssignmentItem {
  id: string; item_type: ItemType; title: string; order: number;
  section_id: string | null; section_title: string | null;
  video_url: string; duration_secs: number | null;
  question: string; option_a: string; option_b: string; option_c: string; option_d: string;
  correct_option: string; pass_score: number; created_at: string;
}
export interface ItemResponse {
  item_id: string; item_type: ItemType; is_watched: boolean;
  selected_option: string; is_correct: boolean | null; score_awarded: number; responded_at: string;
}
export interface AttemptRecord {
  attempt_number: number; score: number; max_score: number; passed: boolean; completed_at: string;
}
export interface Assignment {
  id: string; assessment_title: string; status: AssignStatus;
  score: number; max_score: number; passed?: boolean;
  total_items: number; completed_items: number; completed_at: string | null;
  attempt_number: number; items: AssignmentItem[]; responses: ItemResponse[]; attempts: AttemptRecord[];
  attempt_count:          number;
  effective_max_attempts: number;   // 0 = unlimited
  attempts_remaining:     number | null;
  started_at:             string | null;
  time_limit_mins:        number | null;
  time_remaining_secs:    number | null;
}
export interface MyAssessmentsData { all_complete: boolean; assignments: Assignment[]; }
export interface RespondData {
  item_id: string; item_type: ItemType; is_correct: boolean | null;
  score_awarded: number; assignment_score: number;
}
export interface CompleteData { score: number; max_score: number; passed: boolean; }
export interface PanelState {
  item: AssignmentItem; assignmentId: string;
  itemIndex: number; totalItems: number; maxScore: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

export const OPTIONS: { key: "a" | "b" | "c" | "d"; field: keyof AssignmentItem }[] = [
  { key: "a", field: "option_a" }, { key: "b", field: "option_b" },
  { key: "c", field: "option_c" }, { key: "d", field: "option_d" },
];

export function isItemDone(item: AssignmentItem, responses: ItemResponse[]): boolean {
  const r = responses.find(x => x.item_id === item.id);
  if (!r) return false;
  return item.item_type === "video" ? r.is_watched : r.selected_option !== "";
}

export function toEmbedUrl(url: string): string | null {
  // Already an embed URL — pass through
  const already = url.match(/youtube\.com\/embed\/([^?&/]+)/);
  if (already) return `https://www.youtube.com/embed/${already[1]}`;
  const alreadyV = url.match(/player\.vimeo\.com\/video\/(\d+)/);
  if (alreadyV) return `https://player.vimeo.com/video/${alreadyV[1]}`;

  // youtu.be share link
  const short = url.match(/youtu\.be\/([^?&/]+)/);
  if (short) return `https://www.youtube.com/embed/${short[1]}`;

  // Standard watch URL
  const watch = url.match(/[?&]v=([^?&]+)/);
  if (watch) return `https://www.youtube.com/embed/${watch[1]}`;

  // Shorts and Live
  const shorts = url.match(/youtube\.com\/shorts\/([^?&/]+)/);
  if (shorts) return `https://www.youtube.com/embed/${shorts[1]}`;
  const live = url.match(/youtube\.com\/live\/([^?&/]+)/);
  if (live) return `https://www.youtube.com/embed/${live[1]}`;

  // Vimeo
  const vimeo = url.match(/vimeo\.com\/(\d+)/);
  if (vimeo) return `https://player.vimeo.com/video/${vimeo[1]}`;

  return null;
}

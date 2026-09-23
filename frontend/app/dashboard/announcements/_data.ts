// Pure types/constants/helpers for the Announcements page — no component
// state, safe to import from anywhere.

import { formatDate, formatDateTime } from "@/lib/formatDate";

export type Category      = "general" | "policy" | "event" | "celebration";
export type Visibility    = "all" | "department" | "branch";
// The Branch field is now its own always-present field in the form, separate
// from Visibility — so the form only ever chooses between these two; "branch"
// targeting is derived from the Branch field instead (see handleSave).
export type FormVisibility = "all" | "department";

export interface Announcement {
  id:                     number;
  title:                  string;
  body:                   string;
  category:               Category;
  visibility:             Visibility;
  target_org_unit:        string | null;
  target_org_unit_name:   string;
  target_branch:          number | null;
  target_branch_name:     string;
  is_pinned:              boolean;
  send_email:             boolean;
  posted_by:              string | null;
  posted_by_name:         string;
  posted_by_role:         string;
  views_count:            number;
  reactions_count:        number;
  has_reacted:            boolean;
  can_edit:               boolean;
  created_at:             string;
  updated_at:             string;
}

export interface PageMeta {
  count:           number;
  page:            number;
  page_size:       number;
  total_pages:     number;
  pinned_count:    number;
  total_reactions: number;
  total_views:     number;
  results:         Announcement[];
}

export interface Branch     { id: number; branch_name: string; branch_code: string }

export type FormState = {
  title:             string;
  body:              string;
  category:          Category | "";
  visibility:        FormVisibility;
  target_org_unit:   string;
  target_branch:     string;
  is_pinned:         boolean;
  send_email:        boolean;
};

export type FormErrors = Partial<Record<keyof FormState, string>>;

// ─── Constants ────────────────────────────────────────────────────────────────

export const CATEGORIES: { value: Category; label: string }[] = [
  { value: "general",     label: "General"     },
  { value: "policy",      label: "Policy"      },
  { value: "event",       label: "Event"       },
  { value: "celebration", label: "Celebration" },
];

export const VISIBILITY_OPTIONS: { value: FormVisibility; label: string }[] = [
  { value: "all",        label: "All Employees" },
  { value: "department", label: "By Department" },
];

export const FILTERS = [
  { value: "",            label: "All Posts"   },
  { value: "general",     label: "General"     },
  { value: "policy",      label: "Policy"      },
  { value: "event",       label: "Event"       },
  { value: "celebration", label: "Celebration" },
];

export const EMPTY_FORM: FormState = {
  title: "", body: "", category: "", visibility: "all",
  target_org_unit: "", target_branch: "",
  is_pinned: false, send_email: true,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

export function initials(name: string): string {
  return name.split(" ").filter(Boolean).slice(0, 2).map(w => w[0]?.toUpperCase() ?? "").join("");
}

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1)  return "Just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7)  return `${days}d ago`;
  return formatDate(iso);
}

export function fullDateTime(iso: string): string {
  return formatDateTime(iso);
}

export const CAT_BADGE: Record<Category, string> = {
  general:     "badge-info",
  policy:      "badge-warn",
  event:       "badge-success",
  celebration: "badge-primary",
};

export const CAT_LABEL: Record<Category, string> = {
  general:     "General",
  policy:      "Policy",
  event:       "Event",
  celebration: "Celebration",
};

const AVATAR_COLORS = [
  { bg: "rgba(124,58,237,0.15)",  color: "#7c3aed" },
  { bg: "rgba(37,99,235,0.15)", color: "#2563eb" },
  { bg: "rgba(23,144,90,0.15)", color: "#17905a" },
  { bg: "rgba(162,98,12,0.15)", color: "#a2620c" },
];
export function avatarColor(name: string) {
  return AVATAR_COLORS[name.charCodeAt(0) % AVATAR_COLORS.length];
}

export function viewKey(id: number) { return `ann_viewed_${id}`; }

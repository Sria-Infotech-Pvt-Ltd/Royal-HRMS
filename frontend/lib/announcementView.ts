// Dashboard "View" → full announcement modal. The post is always fetched from
// GET /announcements/<id>/, which applies the same audience rules as the
// Announcements list, so a post the user may not see comes back as 404.

export interface AnnouncementDetail {
  id: number;
  title: string;
  body: string;
  category: string;
  visibility: "all" | "department" | "branch" | string;
  target_department_name: string | null;
  target_branch_name: string | null;
  is_pinned: boolean;
  posted_by_name: string;
  posted_by_role: string;
  created_at: string;
  updated_at: string;
}

export type ViewState =
  | { kind: "loading" }
  | { kind: "unavailable" }
  | { kind: "error"; message: string }
  | { kind: "ready"; ann: AnnouncementDetail };

export function viewState(
  data: AnnouncementDetail | null, loading: boolean, error: string | null, status: number | null,
): ViewState {
  if (loading && !data) return { kind: "loading" };
  // 403/404: deleted, or not meant for this user — say so without revealing anything.
  if (status === 404 || status === 403) return { kind: "unavailable" };
  if (error) return { kind: "error", message: "Couldn't load this announcement. Please try again." };
  if (!data) return { kind: "loading" };
  return { kind: "ready", ann: data };
}

export function audienceLabel(a: Pick<AnnouncementDetail, "visibility" | "target_branch_name" | "target_department_name">): string {
  if (a.visibility === "branch") return a.target_branch_name ? `Branch: ${a.target_branch_name}` : "Branch";
  if (a.visibility === "department") return a.target_department_name ? `Department: ${a.target_department_name}` : "Department";
  return "All employees";
}

export function categoryLabel(category: string): string {
  return category ? category.charAt(0).toUpperCase() + category.slice(1) : "";
}

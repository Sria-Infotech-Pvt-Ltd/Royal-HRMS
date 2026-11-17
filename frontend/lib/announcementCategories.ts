// The announcement types, in one place: the Announcements page, the employee workspace tab, the cards and the dashboard all read this.
// The value is what the server stores and never changes once published; only the label people read can be renamed.
// Keep this list in step with Announcement.CATEGORY_CHOICES in backend/apps/announcements/models.py (a test checks that).

export type Category = "general" | "policy" | "event" | "celebration" | "holiday" | "payroll" | "urgent"

export interface CategoryOption { value: Category; label: string }

export const CATEGORIES: ReadonlyArray<CategoryOption> = [
  { value: "general",     label: "Company News"       },
  { value: "policy",      label: "Policy"             },
  { value: "event",       label: "Events"             },
  { value: "celebration", label: "Celebration"        },
  { value: "holiday",     label: "Holiday & Closures" },
  { value: "payroll",     label: "Payroll & Benefits" },
  { value: "urgent",      label: "Urgent"             },
]

/** The category pills: everything, then each type. */
export const FILTERS: ReadonlyArray<{ value: "" | Category; label: string }> = [
  { value: "", label: "All Posts" },
  ...CATEGORIES,
]

export const CAT_LABEL: Record<Category, string> = {
  general:     "Company News",
  policy:      "Policy",
  event:       "Events",
  celebration: "Celebration",
  holiday:     "Holiday & Closures",
  payroll:     "Payroll & Benefits",
  urgent:      "Urgent",
}

/** The badge colour for each type (see .badge-* in globals.css). Urgent is red so it stands out from routine posts. */
export const CAT_BADGE: Record<Category, string> = {
  general:     "badge-info",
  policy:      "badge-warn",
  event:       "badge-success",
  celebration: "badge-primary",
  holiday:     "badge-neutral",
  payroll:     "badge-teal",
  urgent:      "badge-error",
}

/** The label for a category word as it arrives from the server; an unknown word is shown as it is rather than hidden. */
export function categoryLabel(value: string): string {
  return CATEGORIES.find(option => option.value === value)?.label ?? value
}

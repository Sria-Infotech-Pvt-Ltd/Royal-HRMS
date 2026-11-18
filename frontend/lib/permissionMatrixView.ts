// The view logic of the advanced permission matrix, kept apart from the component so it can be tested: which modules a search and a
// filter leave on screen, and how much of a row or a column is switched on.

import type { PermissionCatalogueItem } from "@/types/orgStructure";

export type MatrixFilter = "all" | "on" | "partial" | "off" | "sensitive";
export type MatrixModule = [string, PermissionCatalogueItem[]];

export const COMMON_ACTIONS = ["view", "create", "edit", "delete", "export", "import", "approve"] as const;

export const labelOf = (text: string) => text.replace(/_/g, " ");

export interface Coverage { on: number; total: number }
export type CheckState = "none" | "some" | "all";

export function coverageOf(items: PermissionCatalogueItem[], granted: Set<string>): Coverage {
  return { on: items.filter(item => granted.has(item.codename)).length, total: items.length };
}

export function stateOf({ on, total }: Coverage): CheckState {
  if (total === 0 || on === 0) return "none";
  return on === total ? "all" : "some";
}

/** A module matches a search when the module's own name does (then every permission in it stays), or one of its permissions does. */
function searchModule([module, items]: MatrixModule, term: string): MatrixModule | null {
  if (!term) return [module, items];
  if (labelOf(module).toLowerCase().includes(term)) return [module, items];
  const hits = items.filter(item => `${item.action} ${item.codename} ${item.description ?? ""}`.toLowerCase().includes(term));
  return hits.length > 0 ? [module, hits] : null;
}

function passesFilter(items: PermissionCatalogueItem[], granted: Set<string>, filter: MatrixFilter): boolean {
  const state = stateOf(coverageOf(items, granted));
  if (filter === "on") return state === "all";
  if (filter === "partial") return state === "some";
  if (filter === "off") return state === "none";
  if (filter === "sensitive") return items.some(item => item.is_sensitive);
  return true;
}

export function visibleModules(modules: MatrixModule[], granted: Set<string>, query: string, filter: MatrixFilter): MatrixModule[] {
  const term = query.trim().toLowerCase();
  return modules
    .map(entry => searchModule(entry, term))
    .filter((entry): entry is MatrixModule => entry !== null)
    .filter(([, items]) => passesFilter(items, granted, filter));
}

/** How many modules are in each filter, for the numbers on the filter chips. */
export function filterCounts(modules: MatrixModule[], granted: Set<string>): Record<MatrixFilter, number> {
  const count = (filter: MatrixFilter) => modules.filter(([, items]) => passesFilter(items, granted, filter)).length;
  return { all: modules.length, on: count("on"), partial: count("partial"), off: count("off"), sensitive: count("sensitive") };
}

/** The permissions of one action (view, create, ...) across the modules on screen: what a column header switches. */
export function columnItems(modules: MatrixModule[], action: string): PermissionCatalogueItem[] {
  return modules.flatMap(([, items]) => items.filter(item => item.action === action));
}

/** Sensitive permissions that are switched on: the number worth a warning. */
export function sensitiveOn(modules: MatrixModule[], granted: Set<string>): number {
  return modules.reduce((total, [, items]) => total + items.filter(item => item.is_sensitive && granted.has(item.codename)).length, 0);
}

/** One line per action column, shown when the column header is hovered. */
export const ACTION_HINTS: Record<string, string> = {
  view: "Open and read records",
  create: "Add new records",
  edit: "Change existing records",
  delete: "Remove records",
  export: "Download data out of the system",
  import: "Upload data into the system",
  approve: "Approve or reject requests",
};

export type QuickPreset = "view_only" | "everything" | "nothing";

/** Reading actions: what "View only" keeps switched on. */
const READ_ACTIONS = ["view", "view_own"];

/**
 * What a quick preset would switch on and off across the modules on screen. Locked permissions are never touched, and only the
 * permissions that actually change are returned, so the call can be handed straight to the matrix's add / remove handlers.
 */
export function quickSetChanges(
  modules: MatrixModule[], granted: Set<string>, preset: QuickPreset, isLocked: (codename: string) => boolean,
): { add: string[]; remove: string[] } {
  const add: string[] = [];
  const remove: string[] = [];
  for (const [, items] of modules) {
    for (const item of items) {
      if (isLocked(item.codename)) continue;
      const shouldBeOn = preset === "everything" ? true : preset === "nothing" ? false : READ_ACTIONS.includes(item.action);
      const isOn = granted.has(item.codename);
      if (shouldBeOn && !isOn) add.push(item.codename);
      if (!shouldBeOn && isOn) remove.push(item.codename);
    }
  }
  return { add, remove };
}

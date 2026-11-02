// Shared by every screen that edits a PermissionMatrix selection
// (PositionPermissionsModal.tsx, PermissionTemplateEditor.tsx) — kept in one
// place so a future change to the search/count/select-all behavior doesn't
// need to be made twice and risk the two editors silently diverging.

import type { PermissionCatalogueItem } from "@/types/orgStructure";

/** Adds/removes a whole batch of codenames from a granted set in one update — the "select all in this module" action. */
export function toggleManyInSet(granted: Set<string>, codenames: string[], isOn: boolean): Set<string> {
  const next = new Set(granted);
  codenames.forEach(codename => { if (isOn) next.add(codename); else next.delete(codename); });
  return next;
}

/** Filters a permission catalogue by a search term (matches module name, action, codename, or description) and
 * returns it as the sorted [module, items][] tuple array PermissionMatrix expects, plus the total/granted counts
 * for the "X of Y enabled" summary line. */
export function filterCatalogueForMatrix(
  catalogue: Record<string, PermissionCatalogueItem[]>,
  search: string,
  granted: Set<string>,
) {
  const term = search.trim().toLowerCase();
  const modules = Object.entries(catalogue)
    .map(([module, items]) => [
      module,
      term
        ? items.filter(item => `${item.action} ${item.codename} ${item.description ?? ""}`.toLowerCase().includes(term))
        : items,
    ] as [string, PermissionCatalogueItem[]])
    .filter(([, items]) => items.length > 0)
    .sort(([a], [b]) => a.localeCompare(b));

  const permissionCount = modules.reduce((total, [, items]) => total + items.length, 0);
  const grantedCount = modules.reduce((total, [, items]) => total + items.filter(item => granted.has(item.codename)).length, 0);

  return { modules, permissionCount, grantedCount };
}

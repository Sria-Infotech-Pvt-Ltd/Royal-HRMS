// View logic of the Bulk apply (Templates) tab: what a template contains grouped by module, how templates are searched, filtered and
// sorted, and the numbers shown above the cards. Pure, so it can be tested without drawing anything.

import type { PermissionTemplate } from "@/components/settings/permissionTemplateTypes";
import type { PermissionCatalogueItem } from "@/types/orgStructure";

export type TemplateFilter = "all" | "team" | "branch" | "empty" | "unused";
export type TemplateSort = "name" | "permissions" | "positions" | "updated";
type Catalogue = Record<string, PermissionCatalogueItem[]>;

export interface ModuleShare { module: string; actions: string[] }

/** What a template grants, module by module, biggest module first. Codenames the catalogue no longer lists are ignored. */
export function modulesOfTemplate(template: PermissionTemplate, catalogue: Catalogue): ModuleShare[] {
  const held = new Set(template.permission_codenames);
  return Object.entries(catalogue)
    .map(([module, items]) => ({ module, actions: items.filter(item => held.has(item.codename)).map(item => item.action) }))
    .filter(entry => entry.actions.length > 0)
    .sort((first, second) => second.actions.length - first.actions.length || first.module.localeCompare(second.module));
}

export function sensitiveCount(template: PermissionTemplate, catalogue: Catalogue): number {
  const held = new Set(template.permission_codenames);
  return Object.values(catalogue).reduce((total, items) => total + items.filter(item => item.is_sensitive && held.has(item.codename)).length, 0);
}

export function totalPermissions(catalogue: Catalogue): number {
  return Object.values(catalogue).reduce((total, items) => total + items.length, 0);
}

function matchesFilter(template: PermissionTemplate, filter: TemplateFilter): boolean {
  if (filter === "team") return template.can_manage_team;
  if (filter === "branch") return template.can_manage_branch;
  if (filter === "empty") return template.permission_codenames.length === 0;
  if (filter === "unused") return template.position_count === 0;
  return true;
}

export function filterCounts(templates: PermissionTemplate[]): Record<TemplateFilter, number> {
  const count = (filter: TemplateFilter) => templates.filter(template => matchesFilter(template, filter)).length;
  return { all: templates.length, team: count("team"), branch: count("branch"), empty: count("empty"), unused: count("unused") };
}

export function visibleTemplates(templates: PermissionTemplate[], query: string, filter: TemplateFilter, sort: TemplateSort): PermissionTemplate[] {
  const term = query.trim().toLowerCase();
  const found = templates.filter(template => matchesFilter(template, filter) && (!term || `${template.name} ${template.description}`.toLowerCase().includes(term)));
  const byName = (first: PermissionTemplate, second: PermissionTemplate) => first.name.localeCompare(second.name);
  if (sort === "permissions") return [...found].sort((first, second) => second.permission_codenames.length - first.permission_codenames.length || byName(first, second));
  if (sort === "positions") return [...found].sort((first, second) => second.position_count - first.position_count || byName(first, second));
  if (sort === "updated") return [...found].sort((first, second) => second.updated_at.localeCompare(first.updated_at) || byName(first, second));
  return [...found].sort(byName);
}

export interface TemplateSummary { templates: number; applications: number; empty: number; sensitive: number }

export function summarise(templates: PermissionTemplate[], catalogue: Catalogue): TemplateSummary {
  return {
    templates: templates.length,
    applications: templates.reduce((total, template) => total + template.position_count, 0),
    empty: templates.filter(template => template.permission_codenames.length === 0).length,
    sensitive: templates.reduce((total, template) => total + sensitiveCount(template, catalogue), 0),
  };
}

/** A name for a copy that does not clash with an existing template: "Manager (copy)", "Manager (copy 2)", ... */
export function copyName(name: string, existing: string[]): string {
  const taken = new Set(existing.map(entry => entry.toLowerCase()));
  let candidate = `${name} (copy)`;
  for (let attempt = 2; taken.has(candidate.toLowerCase()); attempt += 1) candidate = `${name} (copy ${attempt})`;
  return candidate;
}

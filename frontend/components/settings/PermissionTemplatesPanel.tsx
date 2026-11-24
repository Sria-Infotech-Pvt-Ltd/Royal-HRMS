"use client";

// "Give the same access to many positions at once" — define a reusable
// template once (e.g. "Manager", "HR"), then apply it to any number of
// positions in one action, instead of opening each position's own access
// modal one at a time (Organization > a position > Permissions).

import { useMemo, useState } from "react";
import { useT } from "@/hooks/useI18n";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useToast } from "@/components/ToastProvider";
import ConfirmModal from "@/components/ConfirmModal";
import PermissionTemplateEditor from "./PermissionTemplateEditor";
import ApplyTemplateModal from "./ApplyTemplateModal";
import PermissionTemplateCard from "./PermissionTemplateCard";
import StatCardGrid from "./StatCardGrid";
import {
  copyName, filterCounts, summarise, visibleTemplates, type TemplateFilter, type TemplateSort,
} from "@/lib/permissionTemplatesView";
import type { PermissionTemplate } from "./permissionTemplateTypes";
import type { PermissionCatalogueItem } from "@/types/orgStructure";

const FILTERS: { value: TemplateFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "team", label: "Team manager" },
  { value: "branch", label: "Branch-wide" },
  { value: "empty", label: "Empty" },
  { value: "unused", label: "Not applied yet" },
];

interface Props {
  catalogue: Record<string, PermissionCatalogueItem[]>;
  canEdit:   boolean;
}

export default function PermissionTemplatesPanel({ catalogue, canEdit }: Props) {
  const t = useT();
  const { showToast } = useToast();
  const { data: templates, error: loadError, refetch } = useFetch<PermissionTemplate[]>(API.settings.permissionTemplates);
  const [editing, setEditing] = useState<PermissionTemplate | "new" | null>(null);
  const [applying, setApplying] = useState<PermissionTemplate | null>(null);
  const [deleting, setDeleting] = useState<PermissionTemplate | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<TemplateFilter>("all");
  const [sort, setSort] = useState<TemplateSort>("name");

  const all = useMemo(() => templates ?? [], [templates]);
  const shown = useMemo(() => visibleTemplates(all, query, filter, sort), [all, query, filter, sort]);
  const counts = useMemo(() => filterCounts(all), [all]);
  const summary = useMemo(() => summarise(all, catalogue), [all, catalogue]);

  async function duplicate(template: PermissionTemplate) {
    try {
      await clientApi.post(API.settings.permissionTemplates, {
        name: copyName(template.name, all.map(entry => entry.name)),
        description: template.description,
        can_manage_team: template.can_manage_team,
        can_manage_branch: template.can_manage_branch,
        codenames: template.permission_codenames,
      });
      refetch();
      showToast(t("Copied \"{name}\". Rename it with Edit.", { name: template.name }), "success");
    } catch (err: unknown) {
      showToast((err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? t("Could not copy this template."), "error");
    }
  }

  function onSaved() {
    setEditing(null);
    refetch();
    showToast(t("Template saved."), "success");
  }

  async function confirmDelete() {
    if (!deleting) return;
    setIsDeleting(true);
    try {
      await clientApi.delete(API.settings.permissionTemplateDetail(deleting.id));
      setDeleting(null);
      refetch();
      showToast(t("Template deleted."), "success");
    } catch (err: unknown) {
      showToast((err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? t("Could not delete this template."), "error");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-[var(--on-variant)]">
          {t("Define a permission bundle once, then apply it to any number of positions at a time — e.g. give every manager position the same access without editing each one.")}
        </p>
        {canEdit && (
          <button className="btn btn-filled" type="button" onClick={() => setEditing("new")}>
            <i className="ti ti-plus" /> {t("New template")}
          </button>
        )}
      </div>

      {loadError && <div className="alert alert-error" role="alert">{loadError}</div>}

      {!templates && !loadError ? (
        <p className="py-10 text-center text-sm text-[var(--on-variant)]"><i className="ti ti-loader-2 mr-2 animate-spin text-[var(--primary)]" />{t("Loading templates…")}</p>
      ) : templates && templates.length === 0 ? (
        <p className="py-10 text-center text-sm text-[var(--on-variant)]">{t("No templates yet. Create one to start applying bulk access.")}</p>
      ) : (
        <>
          <StatCardGrid
            cards={[
              { icon: "ti-stack-2", tone: "var(--primary)", label: t("Templates"), value: String(summary.templates), note: t("Reusable bundles") },
              { icon: "ti-briefcase", tone: "var(--success)", label: t("Positions using them"), value: String(summary.applications), note: t("Across all templates") },
              { icon: "ti-alert-circle", tone: "var(--warn)", label: t("Empty templates"), value: String(summary.empty), note: summary.empty === 0 ? t("None") : t("Grant nothing: fill or delete") },
              { icon: "ti-alert-triangle", tone: "var(--warn)", label: t("Sensitive permissions"), value: String(summary.sensitive), note: t("Counted across templates") },
            ]}
          />

          <div className="flex flex-wrap items-center gap-3">
            <div className="relative w-72 max-w-full">
              <i className="ti ti-search pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--on-variant)]" />
              <input className="finput w-full !pl-9" type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder={t("Search templates")} aria-label={t("Search templates")} />
            </div>
            <div className="flex flex-wrap gap-1.5" role="group" aria-label={t("Filter templates")}>
              {FILTERS.map(option => (
                <button
                  key={option.value} type="button" aria-pressed={filter === option.value} onClick={() => setFilter(option.value)}
                  className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold"
                  style={filter === option.value
                    ? { background: "var(--primary)", borderColor: "var(--primary)", color: "#fff" }
                    : { background: "var(--surface)", borderColor: "var(--outline-v)", color: "var(--on-variant)" }}
                >
                  {t(option.label)}
                  <span className="rounded-full px-1.5 text-[10px]" style={{ background: filter === option.value ? "rgba(255,255,255,.25)" : "var(--bg-low)" }}>{counts[option.value]}</span>
                </button>
              ))}
            </div>
            <label className="ml-auto flex items-center gap-2 text-xs text-[var(--on-variant)]">
              {t("Sort by")}
              <select className="finput w-44" value={sort} onChange={event => setSort(event.target.value as TemplateSort)} aria-label={t("Sort templates")}>
                <option value="name">{t("Name")}</option>
                <option value="permissions">{t("Most permissions")}</option>
                <option value="positions">{t("Most positions")}</option>
                <option value="updated">{t("Recently updated")}</option>
              </select>
            </label>
          </div>

          {shown.length === 0 ? (
            <p className="py-10 text-center text-sm text-[var(--on-variant)]">{t("No template matches. Clear the search or choose “All”.")}</p>
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              {shown.map(template => (
                <PermissionTemplateCard
                  key={template.id} template={template} catalogue={catalogue} canEdit={canEdit}
                  onApply={() => setApplying(template)} onEdit={() => setEditing(template)}
                  onDuplicate={() => duplicate(template)} onDelete={() => setDeleting(template)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {editing && (
        <PermissionTemplateEditor
          catalogue={catalogue}
          template={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onSaved={onSaved}
        />
      )}

      {applying && (
        <ApplyTemplateModal
          template={applying}
          onClose={() => setApplying(null)}
          onApplied={count => {
            setApplying(null);
            showToast(count === 1 ? t("Applied to {count} position.", { count }) : t("Applied to {count} positions.", { count }), "success");
          }}
        />
      )}

      {deleting && (
        <ConfirmModal
          title={t("Delete this template?")}
          body={t("This permanently deletes \"{name}\". Positions it was already applied to keep their current access — this only removes the reusable template, not anything already granted.", { name: deleting.name })}
          confirmLabel={t("Delete template")}
          danger
          saving={isDeleting}
          onConfirm={confirmDelete}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  );
}

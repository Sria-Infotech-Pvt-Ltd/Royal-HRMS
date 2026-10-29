"use client";

// "Give the same access to many positions at once" — define a reusable
// template once (e.g. "Manager", "HR"), then apply it to any number of
// positions in one action, instead of opening each position's own access
// modal one at a time (Organization > a position > Permissions).

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import ConfirmModal from "@/components/ConfirmModal";
import PermissionTemplateEditor from "./PermissionTemplateEditor";
import ApplyTemplateModal from "./ApplyTemplateModal";
import type { PermissionTemplate } from "./permissionTemplateTypes";
import type { PermissionCatalogueItem } from "@/types/orgStructure";

interface Props {
  catalogue: Record<string, PermissionCatalogueItem[]>;
  canEdit:   boolean;
}

export default function PermissionTemplatesPanel({ catalogue, canEdit }: Props) {
  const { showToast } = useToast();
  const [templates, setTemplates] = useState<PermissionTemplate[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [editing, setEditing] = useState<PermissionTemplate | "new" | null>(null);
  const [applying, setApplying] = useState<PermissionTemplate | null>(null);
  const [deleting, setDeleting] = useState<PermissionTemplate | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  function load() {
    clientApi.get<{ data: PermissionTemplate[] }>(API.settings.permissionTemplates)
      .then(({ data }) => setTemplates(data.data ?? []))
      .catch(() => setLoadError("Could not load permission templates."));
  }

  useEffect(load, []);

  function onSaved() {
    setEditing(null);
    load();
    showToast("Template saved.", "success");
  }

  async function confirmDelete() {
    if (!deleting) return;
    setIsDeleting(true);
    try {
      await clientApi.delete(API.settings.permissionTemplateDetail(deleting.id));
      setDeleting(null);
      load();
      showToast("Template deleted.", "success");
    } catch (err: unknown) {
      showToast((err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Could not delete this template.", "error");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-2xl text-sm text-[var(--on-variant)]">
          Define a permission bundle once, then apply it to any number of positions at a time —
          e.g. give every manager position the same access without editing each one.
        </p>
        {canEdit && (
          <button className="btn btn-filled" type="button" onClick={() => setEditing("new")}>
            <i className="ti ti-plus" /> New template
          </button>
        )}
      </div>

      {loadError && <div className="alert alert-error" role="alert">{loadError}</div>}

      {!templates && !loadError ? (
        <p className="py-10 text-center text-sm text-[var(--on-variant)]"><i className="ti ti-loader-2 mr-2 animate-spin text-[var(--primary)]" />Loading templates…</p>
      ) : templates && templates.length === 0 ? (
        <p className="py-10 text-center text-sm text-[var(--on-variant)]">No templates yet. Create one to start applying bulk access.</p>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {templates?.map(template => (
            <div key={template.id} className="rounded-2xl border border-[var(--outline-v)] bg-[var(--surface)] p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="truncate text-sm font-bold text-[var(--on-bg)]">{template.name}</h3>
                  {template.description && <p className="mt-0.5 text-xs text-[var(--on-variant)]">{template.description}</p>}
                </div>
                <span className="shrink-0 rounded-full border border-[var(--primary-c)] bg-[var(--sec-c)] px-2.5 py-1 text-[11px] font-semibold text-[var(--primary)]">
                  {template.permission_codenames.length} permission{template.permission_codenames.length === 1 ? "" : "s"}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-[var(--on-variant)]">
                {template.can_manage_team && <span className="rounded-full bg-[var(--bg-low)] px-2 py-0.5">Team manager</span>}
                {template.can_manage_branch && <span className="rounded-full bg-[var(--bg-low)] px-2 py-0.5">Branch-wide access</span>}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="btn btn-filled btn-sm" type="button" onClick={() => setApplying(template)} disabled={!canEdit}>
                  <i className="ti ti-users" /> Apply to positions
                </button>
                {canEdit && (
                  <>
                    <button className="btn btn-ghost btn-sm" type="button" onClick={() => setEditing(template)}>
                      <i className="ti ti-edit" /> Edit
                    </button>
                    <button className="btn btn-ghost btn-sm" type="button" style={{ color: "var(--error)" }} onClick={() => setDeleting(template)}>
                      <i className="ti ti-trash" /> Delete
                    </button>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
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
            showToast(`Applied to ${count} position${count === 1 ? "" : "s"}.`, "success");
          }}
        />
      )}

      {deleting && (
        <ConfirmModal
          title="Delete this template?"
          body={`This permanently deletes "${deleting.name}". Positions it was already applied to keep their current access — this only removes the reusable template, not anything already granted.`}
          confirmLabel="Delete template"
          danger
          saving={isDeleting}
          onConfirm={confirmDelete}
          onCancel={() => setDeleting(null)}
        />
      )}
    </div>
  );
}

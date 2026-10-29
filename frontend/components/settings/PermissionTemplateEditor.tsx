"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import ToggleSwitch from "@/components/ToggleSwitch";
import PermissionMatrix from "@/components/PermissionMatrix";
import type { PermissionCatalogueItem } from "@/types/orgStructure";
import type { PermissionTemplate } from "./permissionTemplateTypes";

interface Props {
  catalogue: Record<string, PermissionCatalogueItem[]>;
  template:  PermissionTemplate | null; // null = creating a new one
  onClose:   () => void;
  onSaved:   () => void;
}

export default function PermissionTemplateEditor({ catalogue, template, onClose, onSaved }: Props) {
  const [name, setName] = useState(template?.name ?? "");
  const [description, setDescription] = useState(template?.description ?? "");
  const [canManageTeam, setCanManageTeam] = useState(template?.can_manage_team ?? false);
  const [canManageBranch, setCanManageBranch] = useState(template?.can_manage_branch ?? false);
  const [granted, setGranted] = useState<Set<string>>(new Set(template?.permission_codenames ?? []));
  const [search, setSearch] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function toggle(codename: string) {
    setGranted(previous => {
      const next = new Set(previous);
      if (next.has(codename)) next.delete(codename); else next.add(codename);
      return next;
    });
  }

  function toggleMany(codenames: string[], isOn: boolean) {
    setGranted(previous => {
      const next = new Set(previous);
      codenames.forEach(codename => { if (isOn) next.add(codename); else next.delete(codename); });
      return next;
    });
  }

  async function save() {
    if (!name.trim()) { setError("Name is required."); return; }
    setIsSaving(true);
    setError(null);
    const payload = {
      name: name.trim(),
      description: description.trim(),
      can_manage_team: canManageTeam,
      can_manage_branch: canManageBranch,
      codenames: [...granted],
    };
    try {
      if (template) await clientApi.put(API.settings.permissionTemplateDetail(template.id), payload);
      else await clientApi.post(API.settings.permissionTemplates, payload);
      onSaved();
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { message?: string } }; message?: string })?.response?.data?.message
          ?? (err as { message?: string })?.message
          ?? "Could not save this template.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  const term = search.trim().toLowerCase();
  const modules = Object.entries(catalogue)
    .map(([module, items]) => [
      module,
      term ? items.filter(item => `${item.action} ${item.codename} ${item.description ?? ""}`.toLowerCase().includes(term)) : items,
    ] as [string, PermissionCatalogueItem[]])
    .filter(([, items]) => items.length > 0)
    .sort(([a], [b]) => a.localeCompare(b));
  const permissionCount = modules.reduce((total, [, items]) => total + items.length, 0);
  const grantedCount = modules.reduce((total, [, items]) => total + items.filter(item => granted.has(item.codename)).length, 0);

  return (
    <Modal
      title={template ? <>Edit <span style={{ color: "var(--primary)", fontStyle: "italic" }}>{template.name}</span></> : "New permission template"}
      onClose={onClose}
      maxWidth={1040}
      scrollBody
      footer={
        <>
          <span className="mr-auto text-xs text-[var(--on-variant)]">{granted.size} permission{granted.size === 1 ? "" : "s"} selected</span>
          <button className="btn btn-ghost" type="button" onClick={onClose} disabled={isSaving}>Cancel</button>
          <button className="btn btn-filled" type="button" onClick={save} disabled={isSaving}>
            <i className={`ti ${isSaving ? "ti-loader-2 animate-spin" : "ti-device-floppy"}`} />
            {isSaving ? "Saving…" : "Save template"}
          </button>
        </>
      }
    >
      <div className="space-y-5">
        {error && <div className="alert alert-error" role="alert"><i className="ti ti-alert-circle" />{error}</div>}

        <div className="grid gap-3 md:grid-cols-2">
          <div className="field-group">
            <label className="field-label">Template name <span style={{ color: "var(--error)" }}>*</span></label>
            <input className="field-input" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Manager" maxLength={100} />
          </div>
          <div className="field-group">
            <label className="field-label">Description <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>optional</span></label>
            <input className="field-input" value={description} onChange={e => setDescription(e.target.value)} placeholder="What this template is for" maxLength={255} />
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex min-h-20 items-center justify-between gap-4 rounded-xl border border-[var(--outline-v)] bg-[var(--surface)] p-4">
            <span>
              <span className="block text-sm font-semibold text-[var(--on-bg)]">Team manager</span>
              <span className="mt-1 block text-xs leading-5 text-[var(--on-variant)]">Applied positions are marked as team managers.</span>
            </span>
            <ToggleSwitch checked={canManageTeam} onChange={setCanManageTeam} />
          </label>
          <label className="flex min-h-20 items-center justify-between gap-4 rounded-xl border border-[var(--outline-v)] bg-[var(--surface)] p-4">
            <span>
              <span className="block text-sm font-semibold text-[var(--on-bg)]">Branch-wide access</span>
              <span className="mt-1 block text-xs leading-5 text-[var(--on-variant)]">Applied positions get branch scope where the module supports it.</span>
            </span>
            <ToggleSwitch checked={canManageBranch} onChange={setCanManageBranch} />
          </label>
        </div>

        <section aria-label="Template permissions">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-[var(--on-bg)]">Module permissions</h3>
              <p className="mt-1 text-xs text-[var(--on-variant)]">
                <strong className="text-[var(--on-bg)]">{grantedCount} of {permissionCount}</strong> enabled.
              </p>
            </div>
            <label className="relative w-full sm:w-64">
              <i className="ti ti-search pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--on-variant)]" />
              <input
                className="finput w-full pl-9"
                type="search"
                value={search}
                onChange={event => setSearch(event.target.value)}
                placeholder="Search modules or actions"
                aria-label="Search permissions"
              />
            </label>
          </div>
          {modules.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--outline)] px-4 py-10 text-center text-sm text-[var(--on-variant)]">
              No permissions match that search.
            </div>
          ) : (
            <PermissionMatrix modules={modules} granted={granted} onToggle={toggle} onToggleMany={toggleMany} />
          )}
        </section>
      </div>
    </Modal>
  );
}

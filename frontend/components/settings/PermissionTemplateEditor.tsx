"use client";

import { useState } from "react";
import { useT } from "@/hooks/useI18n";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import ToggleSwitch from "@/components/ToggleSwitch";
import PermissionMatrix from "@/components/PermissionMatrix";
import { filterCatalogueForMatrix, toggleManyInSet } from "@/lib/permissionMatrixHelpers";
import type { PermissionCatalogueItem } from "@/types/orgStructure";
import type { PermissionTemplate } from "./permissionTemplateTypes";

interface Props {
  catalogue: Record<string, PermissionCatalogueItem[]>;
  template:  PermissionTemplate | null; // null = creating a new one
  onClose:   () => void;
  onSaved:   () => void;
}

export default function PermissionTemplateEditor({ catalogue, template, onClose, onSaved }: Props) {
  const t = useT();
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
    setGranted(previous => toggleManyInSet(previous, codenames, isOn));
  }

  async function save() {
    if (!name.trim()) { setError(t("Name is required.")); return; }
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
          ?? t("Could not save this template."),
      );
    } finally {
      setIsSaving(false);
    }
  }

  const { modules, permissionCount, grantedCount } = filterCatalogueForMatrix(catalogue, search, granted);

  return (
    <Modal
      title={template ? <>{t("Edit")} <span style={{ color: "var(--primary)", fontStyle: "italic" }}>{template.name}</span></> : t("New permission template")}
      onClose={onClose}
      maxWidth={1040}
      scrollBody
      footer={
        <>
          <span className="mr-auto text-xs text-[var(--on-variant)]">{granted.size === 1 ? t("{count} permission selected", { count: granted.size }) : t("{count} permissions selected", { count: granted.size })}</span>
          <button className="btn btn-ghost" type="button" onClick={onClose} disabled={isSaving}>{t("Cancel")}</button>
          <button className="btn btn-filled" type="button" onClick={save} disabled={isSaving}>
            <i className={`ti ${isSaving ? "ti-loader-2 animate-spin" : "ti-device-floppy"}`} />
            {isSaving ? t("Saving…") : t("Save template")}
          </button>
        </>
      }
    >
      <div className="space-y-5">
        {error && <div className="alert alert-error" role="alert"><i className="ti ti-alert-circle" />{error}</div>}

        <div className="grid gap-3 md:grid-cols-2">
          <div className="field-group">
            <label className="field-label">{t("Template name")} <span style={{ color: "var(--error)" }}>*</span></label>
            <input className="field-input" value={name} onChange={e => setName(e.target.value)} placeholder={t("e.g. Manager")} maxLength={100} />
          </div>
          <div className="field-group">
            <label className="field-label">{t("Description")} <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>{t("optional")}</span></label>
            <input className="field-input" value={description} onChange={e => setDescription(e.target.value)} placeholder={t("What this template is for")} maxLength={255} />
          </div>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex min-h-20 items-center justify-between gap-4 rounded-xl border border-[var(--outline-v)] bg-[var(--surface)] p-4">
            <span>
              <span className="block text-sm font-semibold text-[var(--on-bg)]">{t("Team manager")}</span>
              <span className="mt-1 block text-xs leading-5 text-[var(--on-variant)]">{t("Applied positions are marked as team managers.")}</span>
            </span>
            <ToggleSwitch checked={canManageTeam} onChange={setCanManageTeam} />
          </label>
          <label className="flex min-h-20 items-center justify-between gap-4 rounded-xl border border-[var(--outline-v)] bg-[var(--surface)] p-4">
            <span>
              <span className="block text-sm font-semibold text-[var(--on-bg)]">{t("Branch-wide access")}</span>
              <span className="mt-1 block text-xs leading-5 text-[var(--on-variant)]">{t("Applied positions get branch scope where the module supports it.")}</span>
            </span>
            <ToggleSwitch checked={canManageBranch} onChange={setCanManageBranch} />
          </label>
        </div>

        <section aria-label={t("Template permissions")}>
          <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-[var(--on-bg)]">{t("Module permissions")}</h3>
              <p className="mt-1 text-xs text-[var(--on-variant)]">
                <strong className="text-[var(--on-bg)]">{t("{granted} of {total}", { granted: grantedCount, total: permissionCount })}</strong> {t("enabled.")}
              </p>
            </div>
            <label className="relative w-full sm:w-64">
              <i className="ti ti-search pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--on-variant)]" />
              <input
                className="finput w-full pl-9"
                type="search"
                value={search}
                onChange={event => setSearch(event.target.value)}
                placeholder={t("Search modules or actions")}
                aria-label={t("Search permissions")}
              />
            </label>
          </div>
          {modules.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--outline)] px-4 py-10 text-center text-sm text-[var(--on-variant)]">
              {t("No permissions match that search.")}
            </div>
          ) : (
            <PermissionMatrix modules={modules} granted={granted} onToggle={toggle} onToggleMany={toggleMany} />
          )}
        </section>
      </div>
    </Modal>
  );
}

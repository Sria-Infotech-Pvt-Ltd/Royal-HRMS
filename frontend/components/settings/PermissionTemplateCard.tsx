"use client";

import { useState } from "react";
import { hueOf, initialsOf } from "@/lib/accessListView";
import { formatDate } from "@/lib/formatDate";
import { modulesOfTemplate, sensitiveCount, totalPermissions } from "@/lib/permissionTemplatesView";
import type { PermissionCatalogueItem } from "@/types/orgStructure";
import type { PermissionTemplate } from "./permissionTemplateTypes";

interface Props {
  template: PermissionTemplate;
  catalogue: Record<string, PermissionCatalogueItem[]>;
  canEdit: boolean;
  onApply: () => void;
  onEdit: () => void;
  onDuplicate: () => void;
  onDelete: () => void;
}

const MODULES_SHOWN = 4;
const labelOf = (text: string) => text.replace(/_/g, " ");

function Pill({ icon, tone, children }: { icon?: string; tone: string; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ background: `color-mix(in srgb, ${tone} 14%, transparent)`, color: tone }}>
      {icon && <i className={`ti ${icon}`} />}{children}
    </span>
  );
}

function ActionButton({ icon, label, onClick, tone }: { icon: string; label: string; onClick: () => void; tone?: string }) {
  return (
    <button
      type="button" onClick={onClick} className="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold"
      style={{ background: "var(--surface)", borderColor: "var(--outline-v)", color: tone ?? "var(--on-bg)" }}
    >
      <i className={`ti ${icon}`} /> {label}
    </button>
  );
}

/** One template: what it grants (a meter, the biggest modules, a warning for sensitive access), where it is used, and its actions. */
export default function PermissionTemplateCard({ template, catalogue, canEdit, onApply, onEdit, onDuplicate, onDelete }: Props) {
  const [isOpen, setIsOpen] = useState(false);
  const count = template.permission_codenames.length;
  const total = totalPermissions(catalogue);
  const percent = total === 0 ? 0 : Math.min(100, Math.round((count / total) * 100));
  const modules = modulesOfTemplate(template, catalogue);
  const sensitive = sensitiveCount(template, catalogue);
  const hue = hueOf(template.name);

  return (
    <article className="flex flex-col gap-3 rounded-2xl border border-[var(--outline-v)] p-4" style={{ background: "var(--surface)" }}>
      <div className="flex items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-sm font-bold" aria-hidden="true"
          style={{ background: `hsl(${hue} 70% 90%)`, color: `hsl(${hue} 45% 32%)` }}>
          {initialsOf(template.name)}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-bold text-[var(--on-bg)]">{template.name}</h3>
          <p className="mt-0.5 line-clamp-2 text-xs text-[var(--on-variant)]">{template.description || "No description"}</p>
        </div>
        <span className="shrink-0 whitespace-nowrap text-right text-xs text-[var(--on-variant)]">
          <strong className="block text-base text-[var(--on-bg)]">{count}</strong>permission{count === 1 ? "" : "s"}
        </span>
      </div>

      <div>
        <div className="h-1.5 overflow-hidden rounded-full" style={{ background: "var(--outline-v)" }} role="img" aria-label={`${count} of ${total} permissions`}>
          <div className="h-full rounded-full" style={{ width: `${percent}%`, background: count === 0 ? "var(--outline-v)" : "var(--primary)" }} />
        </div>
        <div className="mt-1 text-[11px] text-[var(--on-variant)]">{percent}% of all {total} permissions</div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {template.can_manage_team && <Pill icon="ti-users" tone="var(--primary)">Team manager</Pill>}
        {template.can_manage_branch && <Pill icon="ti-building" tone="var(--primary)">Branch-wide access</Pill>}
        {count === 0 && <Pill icon="ti-alert-circle" tone="var(--warn)">Empty: grants nothing</Pill>}
        {sensitive > 0 && <Pill icon="ti-alert-triangle" tone="var(--warn)">{sensitive} sensitive</Pill>}
        <Pill icon="ti-briefcase" tone={template.position_count > 0 ? "var(--success)" : "var(--on-variant)"}>
          {template.position_count === 0 ? "Not applied yet" : `Applied to ${template.position_count} position${template.position_count === 1 ? "" : "s"}`}
        </Pill>
      </div>

      {modules.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
          {modules.slice(0, MODULES_SHOWN).map(entry => (
            <span key={entry.module} className="rounded-md border px-1.5 py-0.5 capitalize" style={{ borderColor: "var(--outline-v)", color: "var(--on-variant)" }}>
              {labelOf(entry.module)} <strong className="text-[var(--on-bg)]">{entry.actions.length}</strong>
            </span>
          ))}
          {modules.length > MODULES_SHOWN && <span className="text-[var(--on-variant)]">+{modules.length - MODULES_SHOWN} more</span>}
          <button type="button" className="ml-auto text-[11px] font-semibold hover:underline" style={{ color: "var(--primary)" }} aria-expanded={isOpen} onClick={() => setIsOpen(open => !open)}>
            {isOpen ? "Hide details" : "Show details"}
          </button>
        </div>
      )}

      {isOpen && (
        <ul className="max-h-48 space-y-1.5 overflow-auto rounded-xl border p-3 text-xs" style={{ borderColor: "var(--outline-v)", background: "var(--bg-low)" }}>
          {modules.map(entry => (
            <li key={entry.module} className="flex flex-wrap items-center gap-1.5">
              <strong className="w-32 shrink-0 capitalize text-[var(--on-bg)]">{labelOf(entry.module)}</strong>
              {entry.actions.map(action => <Pill key={action} tone="var(--primary)">{labelOf(action)}</Pill>)}
            </li>
          ))}
        </ul>
      )}

      <div className="mt-auto flex flex-wrap items-center gap-2 border-t pt-3" style={{ borderColor: "var(--outline-v)" }}>
        <button type="button" className="btn btn-filled btn-sm" onClick={onApply} disabled={!canEdit}>
          <i className="ti ti-users" /> Apply to positions
        </button>
        {canEdit && (
          <>
            <ActionButton icon="ti-edit" label="Edit" onClick={onEdit} />
            <ActionButton icon="ti-copy" label="Duplicate" onClick={onDuplicate} />
            <ActionButton icon="ti-trash" label="Delete" onClick={onDelete} tone="var(--error)" />
          </>
        )}
        <span className="ml-auto text-[11px] text-[var(--on-variant)]">Updated {formatDate(template.updated_at) || "—"}</span>
      </div>
    </article>
  );
}

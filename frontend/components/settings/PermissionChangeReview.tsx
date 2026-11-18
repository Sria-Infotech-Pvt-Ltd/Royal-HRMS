"use client";

import { labelOf, type MatrixModule } from "@/lib/permissionMatrixView";

interface Props {
  modules: MatrixModule[];
  granted: Set<string>;
  saved: Set<string>;
}

interface ModuleChanges { module: string; added: string[]; removed: string[] }

/** What saving would change, module by module: permissions being switched on, and permissions being switched off. */
export function changesByModule(modules: MatrixModule[], granted: Set<string>, saved: Set<string>): ModuleChanges[] {
  return modules
    .map(([module, items]) => ({
      module,
      added: items.filter(item => granted.has(item.codename) && !saved.has(item.codename)).map(item => labelOf(item.action)),
      removed: items.filter(item => !granted.has(item.codename) && saved.has(item.codename)).map(item => labelOf(item.action)),
    }))
    .filter(entry => entry.added.length > 0 || entry.removed.length > 0);
}

function Pills({ actions, sign, color }: { actions: string[]; sign: "+" | "−"; color: string }) {
  return (
    <>
      {actions.map(action => (
        <span key={`${sign}${action}`} className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold capitalize"
          style={{ background: `color-mix(in srgb, ${color} 14%, transparent)`, color }}>
          {sign} {action}
        </span>
      ))}
    </>
  );
}

export default function PermissionChangeReview({ modules, granted, saved }: Props) {
  const changes = changesByModule(modules, granted, saved);
  return (
    <div className="max-h-40 overflow-auto rounded-xl border p-3" style={{ borderColor: "var(--outline-v)", background: "var(--bg-low)" }} aria-label="Changes waiting to be saved">
      <ul className="space-y-2">
        {changes.map(entry => (
          <li key={entry.module} className="flex flex-wrap items-center gap-2 text-sm">
            <strong className="w-36 shrink-0 capitalize text-[var(--on-bg)]">{labelOf(entry.module)}</strong>
            <Pills actions={entry.added} sign="+" color="var(--success)" />
            <Pills actions={entry.removed} sign="−" color="var(--error)" />
          </li>
        ))}
      </ul>
    </div>
  );
}

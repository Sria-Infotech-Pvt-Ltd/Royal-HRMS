"use client";

// Permissions as a matrix: one row per module, one column per common action, a plain checkbox in each cell.
// Actions outside the common columns (view_own, edit_own_profile, ...) are listed in the "Other" column.

import type { PermissionCatalogueItem } from "@/types/orgStructure";

const COMMON_ACTIONS = ["view", "create", "edit", "delete", "export", "import", "approve"] as const;

interface Props {
  modules: [string, PermissionCatalogueItem[]][];
  granted: Set<string>;
  onToggle: (codename: string) => void;
  onToggleMany: (codenames: string[], isOn: boolean) => void;
  /** Codenames that are shown but cannot be changed. */
  lockedCodenames?: readonly string[];
  isReadOnly?: boolean;
}

const labelOf = (action: string) => action.replace(/_/g, " ");

export default function PermissionMatrix({ modules, granted, onToggle, onToggleMany, lockedCodenames = [], isReadOnly = false }: Props) {
  const isLocked = (codename: string) => isReadOnly || lockedCodenames.includes(codename);

  return (
    <div className="overflow-x-auto rounded-2xl border border-[var(--outline-v)] bg-[var(--surface)]">
      <table className="w-full min-w-[860px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-[var(--outline-v)] bg-[var(--bg-low)] text-left text-[11px] font-bold uppercase tracking-[0.06em] text-[var(--on-variant)]">
            <th className="sticky left-0 bg-[var(--bg-low)] px-4 py-3">Module</th>
            {COMMON_ACTIONS.map(action => <th key={action} className="px-2 py-3 text-center">{action}</th>)}
            <th className="px-4 py-3">Other</th>
            <th className="px-3 py-3 text-center">All</th>
          </tr>
        </thead>
        <tbody>
          {modules.map(([module, items]) => {
            const byAction = new Map(items.map(item => [item.action, item]));
            const others = items.filter(item => !(COMMON_ACTIONS as readonly string[]).includes(item.action));
            const changeable = items.filter(item => !isLocked(item.codename)).map(item => item.codename);
            const isAllOn = changeable.length > 0 && changeable.every(codename => granted.has(codename));
            return (
              <tr key={module} className="border-b border-[var(--outline-v)] last:border-b-0 hover:bg-[var(--bg-low)]">
                <th scope="row" className="sticky left-0 bg-[var(--surface)] px-4 py-2.5 text-left font-semibold capitalize text-[var(--on-bg)]">
                  {labelOf(module)}
                  <span className="ml-2 text-[11px] font-normal text-[var(--on-variant)]">
                    {items.filter(item => granted.has(item.codename)).length}/{items.length}
                  </span>
                </th>
                {COMMON_ACTIONS.map(action => {
                  const item = byAction.get(action);
                  return (
                    <td key={action} className="px-2 py-2.5 text-center">
                      {item ? (
                        <input
                          type="checkbox"
                          className="h-4 w-4 accent-[var(--primary)]"
                          checked={granted.has(item.codename)}
                          disabled={isLocked(item.codename)}
                          onChange={() => onToggle(item.codename)}
                          title={item.description || item.codename}
                          aria-label={`${labelOf(module)} ${labelOf(action)}`}
                        />
                      ) : <span className="text-[var(--outline-v)]">–</span>}
                    </td>
                  );
                })}
                <td className="px-4 py-2.5">
                  <div className="flex flex-wrap gap-x-4 gap-y-1">
                    {others.map(item => (
                      <label key={item.codename} className="flex items-center gap-1.5 text-xs capitalize text-[var(--on-variant)]" title={item.description || item.codename}>
                        <input
                          type="checkbox"
                          className="h-4 w-4 accent-[var(--primary)]"
                          checked={granted.has(item.codename)}
                          disabled={isLocked(item.codename)}
                          onChange={() => onToggle(item.codename)}
                        />
                        {labelOf(item.action)}
                        {item.is_sensitive && <i className="ti ti-alert-triangle text-[var(--warn)]" aria-label="Sensitive permission" />}
                      </label>
                    ))}
                  </div>
                </td>
                <td className="px-3 py-2.5 text-center">
                  <input
                    type="checkbox"
                    className="h-4 w-4 accent-[var(--primary)]"
                    checked={isAllOn}
                    disabled={changeable.length === 0}
                    onChange={() => onToggleMany(changeable, !isAllOn)}
                    aria-label={`Select all ${labelOf(module)} permissions`}
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

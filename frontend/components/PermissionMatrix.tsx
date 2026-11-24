"use client";

// Permissions as a matrix: one row per module, one column per common action, a checkbox in each cell. Actions outside the common
// columns (view_own, edit_own_profile, ...) are listed in the "Other" column.
//
// `isAdvanced` (the Permissions settings page) adds: search and filter chips, a switch-all checkbox at the top of every action column
// and on every row (both show the "some are on" dash), a coverage bar per module, "Other" permissions as toggle chips, a sticky
// header, and a legend. Without it the matrix is the plain table the position and template editors have always used.

import { useMemo, useState } from "react";
import type { PermissionCatalogueItem } from "@/types/orgStructure";
import {
  ACTION_HINTS, COMMON_ACTIONS, columnItems, coverageOf, filterCounts, labelOf, quickSetChanges, stateOf, visibleModules, type MatrixFilter,
  type QuickPreset,
} from "@/lib/permissionMatrixView";
import TriStateCheckbox from "@/components/TriStateCheckbox";
import PermissionMatrixToolbar from "@/components/PermissionMatrixToolbar";
import PermissionChip from "@/components/PermissionChip";
import { useT } from "@/hooks/useI18n";

interface Props {
  modules: [string, PermissionCatalogueItem[]][];
  granted: Set<string>;
  onToggle: (codename: string) => void;
  onToggleMany: (codenames: string[], isOn: boolean) => void;
  /** Codenames that are shown but cannot be changed. */
  lockedCodenames?: readonly string[];
  isReadOnly?: boolean;
  isAdvanced?: boolean;
}

function CoverageBar({ on, total }: { on: number; total: number }) {
  const percent = total === 0 ? 0 : Math.round((on / total) * 100);
  const color = on === total && total > 0 ? "var(--success)" : on === 0 ? "var(--outline-v)" : "var(--primary)";
  return (
    <span className="flex shrink-0 items-center gap-2" aria-hidden="true">
      <span className="h-1.5 w-20 overflow-hidden rounded-full bg-[var(--outline-v)]">
        <span className="block h-full rounded-full transition-all" style={{ width: `${percent}%`, background: color }} />
      </span>
      <span className="text-[10.5px] font-medium text-[var(--on-variant)]">{on}/{total}</span>
    </span>
  );
}

export default function PermissionMatrix({ modules, granted, onToggle, onToggleMany, lockedCodenames = [], isReadOnly = false, isAdvanced = false }: Props) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<MatrixFilter>("all");
  const [isCompact, setIsCompact] = useState(false);
  const rowPad = isCompact ? "py-1" : "py-2.5";
  const isLocked = (codename: string) => isReadOnly || lockedCodenames.includes(codename);

  const shown = useMemo(() => (isAdvanced ? visibleModules(modules, granted, query, filter) : modules), [isAdvanced, modules, granted, query, filter]);
  const counts = useMemo(() => filterCounts(modules, granted), [modules, granted]);

  function quickSet(preset: QuickPreset) {
    const { add, remove } = quickSetChanges(shown, granted, preset, isLocked);
    // Giving everything is the one preset that can quietly hand out delete, export and approve: ask first.
    if (preset === "everything" && add.length > 0 && !window.confirm(`${add.length === 1 ? t("Switch ON {count} more permission", { count: add.length }) : t("Switch ON {count} more permissions", { count: add.length })} ${shown.length === 1 ? t("in the {count} module shown?", { count: shown.length }) : t("in the {count} modules shown?", { count: shown.length })} ${t("This includes delete, export and approve rights.")}`)) return;
    if (add.length > 0) onToggleMany(add, true);
    if (remove.length > 0) onToggleMany(remove, false);
  }

  function switchColumn(action: string) {
    const items = columnItems(shown, action).filter(item => !isLocked(item.codename));
    const isAllOn = items.length > 0 && items.every(item => granted.has(item.codename));
    onToggleMany(items.map(item => item.codename), !isAllOn);
  }

  return (
    <div className="space-y-3">
      {isAdvanced && (
        <PermissionMatrixToolbar query={query} onQueryChange={setQuery} filter={filter} onFilterChange={setFilter} counts={counts} shownCount={shown.length} isCompact={isCompact} onCompactChange={setIsCompact} onQuickSet={isReadOnly ? undefined : quickSet} />
      )}
      <div className={`rounded-2xl border border-[var(--outline-v)] ${isAdvanced ? "max-h-[68vh] overflow-auto" : "overflow-x-auto"}`} style={{ background: "var(--surface)" }}>
        <table className="w-full min-w-[900px] border-collapse text-sm">
          <thead className={isAdvanced ? "sticky top-0 z-20" : undefined}>
            <tr className="border-b border-[var(--outline-v)] text-left text-[11px] font-bold uppercase tracking-[0.06em] text-[var(--on-variant)]" style={{ background: "var(--bg-low)" }}>
              <th className="sticky left-0 z-10 px-4 py-3" style={{ background: "var(--bg-low)" }}>{t("Module")}</th>
              {COMMON_ACTIONS.map(action => {
                const items = columnItems(shown, action);
                const changeable = items.filter(item => !isLocked(item.codename));
                const columnCoverage = coverageOf(items, granted);
                const columnState = stateOf(columnCoverage);
                return (
                  <th key={action} className="px-2 py-2 text-center" title={isAdvanced ? `${labelOf(action)}: ${ACTION_HINTS[action]}. ${t("{on} of {total} on.", { on: columnCoverage.on, total: columnCoverage.total })}` : undefined}>
                    <div className="flex flex-col items-center gap-1">
                      <span className={isAdvanced ? "text-[12px] tracking-normal" : undefined}>{action}</span>
                      {isAdvanced && (
                        <>
                          <TriStateCheckbox
                            state={columnState}
                            onChange={() => switchColumn(action)}
                            isDisabled={changeable.length === 0}
                            label={t("Switch every {action} permission on or off for the modules shown", { action })}
                          />
                          <span className="text-[10.5px] font-semibold normal-case tracking-normal" style={{ color: columnState === "all" ? "var(--success)" : "var(--on-variant)" }}>
                            {columnCoverage.on}/{columnCoverage.total}
                          </span>
                        </>
                      )}
                    </div>
                  </th>
                );
              })}
              <th className="px-4 py-3">{t("Other")}</th>
              <th className="px-3 py-3 text-center">{t("All")}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(([module, items]) => {
              const byAction = new Map(items.map(item => [item.action, item]));
              const others = items.filter(item => !(COMMON_ACTIONS as readonly string[]).includes(item.action));
              const changeable = items.filter(item => !isLocked(item.codename)).map(item => item.codename);
              const coverage = coverageOf(items, granted);
              const rowState = stateOf(coverageOf(items.filter(item => !isLocked(item.codename)), granted));
              return (
                <tr key={module} className="group border-b border-[var(--outline-v)] last:border-b-0 hover:bg-[var(--bg-low)]">
                  <th scope="row" className={`sticky left-0 z-10 px-4 ${rowPad} text-left font-semibold capitalize text-[var(--on-bg)]`} style={{ background: "var(--surface)" }}>
                    {isAdvanced ? (
                      <span className="flex items-center justify-between gap-3">
                        {labelOf(module)}
                        <CoverageBar on={coverage.on} total={coverage.total} />
                      </span>
                    ) : (<>
                      {labelOf(module)}
                      <span className="ml-2 text-[11px] font-normal text-[var(--on-variant)]">{coverage.on}/{coverage.total}</span>
                    </>)}
                  </th>
                  {COMMON_ACTIONS.map(action => {
                    const item = byAction.get(action);
                    const isOn = item ? granted.has(item.codename) : false;
                    return (
                      <td key={action} className={`px-2 ${rowPad} text-center`} style={isAdvanced && isOn ? { background: "color-mix(in srgb, var(--primary) 8%, transparent)" } : undefined}>
                        {item ? (
                          <input
                            type="checkbox"
                            className="h-4 w-4 cursor-pointer accent-[var(--primary)] disabled:cursor-not-allowed"
                            checked={isOn}
                            disabled={isLocked(item.codename)}
                            onChange={() => onToggle(item.codename)}
                            title={item.description || item.codename}
                            aria-label={`${labelOf(module)} ${labelOf(action)}`}
                          />
                        ) : <span className="text-[var(--outline-v)]">–</span>}
                      </td>
                    );
                  })}
                  <td className={`px-4 ${rowPad}`}>
                    <div className="flex flex-wrap gap-x-4 gap-y-1.5">
                      {others.map(item => isAdvanced ? (
                        <PermissionChip key={item.codename} label={labelOf(item.action)} isOn={granted.has(item.codename)} isDisabled={isLocked(item.codename)} isSensitive={item.is_sensitive} title={item.description || item.codename} onToggle={() => onToggle(item.codename)} />
                      ) : (
                        <label key={item.codename} className="flex items-center gap-1.5 text-xs capitalize text-[var(--on-variant)]" title={item.description || item.codename}>
                          <input
                            type="checkbox"
                            className="h-4 w-4 accent-[var(--primary)]"
                            checked={granted.has(item.codename)}
                            disabled={isLocked(item.codename)}
                            onChange={() => onToggle(item.codename)}
                          />
                          {labelOf(item.action)}
                          {item.is_sensitive && <i className="ti ti-alert-triangle text-[var(--warn)]" aria-label={t("Sensitive permission")} />}
                        </label>
                      ))}
                    </div>
                  </td>
                  <td className={`px-3 ${rowPad} text-center`}>
                    <TriStateCheckbox
                      state={rowState}
                      onChange={() => onToggleMany(changeable, rowState !== "all")}
                      isDisabled={changeable.length === 0}
                      label={t("Select all {module} permissions", { module: labelOf(module) })}
                    />
                  </td>
                </tr>
              );
            })}
            {shown.length === 0 && (
              <tr>
                <td colSpan={COMMON_ACTIONS.length + 3} className="px-4 py-10 text-center text-sm text-[var(--on-variant)]">
                  {t("No module matches. Clear the search or choose “All modules”.")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {isAdvanced && (
        <p className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[11.5px] text-[var(--on-variant)]">
          <span><i className="ti ti-alert-triangle text-[var(--warn)]" /> {t("Sensitive permission: handle with care")}</span>
          <span>{t("A dash in a box means some, not all, are on")}</span>
          <span>{t("The checkbox at the top of a column switches that action for every module shown")}</span>
        </p>
      )}
    </div>
  );
}

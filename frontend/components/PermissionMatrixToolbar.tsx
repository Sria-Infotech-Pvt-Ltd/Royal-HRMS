"use client";

import type { MatrixFilter, QuickPreset } from "@/lib/permissionMatrixView";

interface Props {
  query: string;
  onQueryChange: (query: string) => void;
  filter: MatrixFilter;
  onFilterChange: (filter: MatrixFilter) => void;
  counts: Record<MatrixFilter, number>;
  shownCount: number;
  isCompact: boolean;
  onCompactChange: (isCompact: boolean) => void;
  /** Absent when the matrix is read only. */
  onQuickSet?: (preset: QuickPreset) => void;
}

const FILTERS: { value: MatrixFilter; label: string; icon: string }[] = [
  { value: "all", label: "All modules", icon: "ti-layout-grid" },
  { value: "on", label: "Fully on", icon: "ti-circle-check" },
  { value: "partial", label: "Partly on", icon: "ti-circle-half-2" },
  { value: "off", label: "Off", icon: "ti-circle" },
  { value: "sensitive", label: "Sensitive", icon: "ti-alert-triangle" },
];

const QUICK_PRESETS: { value: QuickPreset; label: string; icon: string; hint: string }[] = [
  { value: "view_only", label: "View only", icon: "ti-eye", hint: "Switch on reading and switch everything else off" },
  { value: "everything", label: "Everything", icon: "ti-checks", hint: "Switch every permission on" },
  { value: "nothing", label: "Nothing", icon: "ti-square-off", hint: "Switch every permission off" },
];

/** Search box and filter chips above the matrix. The chips carry how many modules each one would show. */
export default function PermissionMatrixToolbar({ query, onQueryChange, filter, onFilterChange, counts, shownCount, isCompact, onCompactChange, onQuickSet }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="relative min-w-[240px] flex-1 sm:max-w-sm">
        <i className="ti ti-search pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--on-variant)]" />
        <input
          type="search"
          value={query}
          onChange={event => onQueryChange(event.target.value)}
          placeholder="Search a module or a permission…"
          aria-label="Search permissions"
          className="field-input w-full !pl-9"
        />
      </div>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter modules">
        {FILTERS.map(option => {
          const isActive = filter === option.value;
          return (
            <button
              key={option.value}
              type="button"
              aria-pressed={isActive}
              onClick={() => onFilterChange(option.value)}
              className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors"
              style={isActive
                ? { background: "var(--primary)", borderColor: "var(--primary)", color: "#fff" }
                : { background: "var(--surface)", borderColor: "var(--outline-v)", color: "var(--on-variant)" }}
            >
              <i className={`ti ${option.icon}`} />
              {option.label}
              <span className="rounded-full px-1.5 text-[10px]" style={{ background: isActive ? "rgba(255,255,255,.25)" : "var(--bg-low)" }}>{counts[option.value]}</span>
            </button>
          );
        })}
      </div>
      <div className="ml-auto flex items-center gap-3">
        <span className="text-xs text-[var(--on-variant)]" aria-live="polite">Showing {shownCount} of {counts.all} modules</span>
        <div className="inline-flex overflow-hidden rounded-lg border" style={{ borderColor: "var(--outline-v)" }} role="group" aria-label="Row density">
          {([false, true] as const).map(compact => (
            <button
              key={String(compact)} type="button" aria-pressed={isCompact === compact} onClick={() => onCompactChange(compact)}
              className="px-2.5 py-1.5 text-xs font-semibold"
              style={isCompact === compact ? { background: "var(--primary)", color: "#fff" } : { background: "var(--surface)", color: "var(--on-variant)" }}
              title={compact ? "Compact rows: more modules on screen" : "Comfortable rows"}
            >
              <i className={`ti ${compact ? "ti-layout-list" : "ti-layout-rows"}`} /> {compact ? "Compact" : "Comfortable"}
            </button>
          ))}
        </div>
      </div>
      {onQuickSet && (
        <div className="flex basis-full flex-wrap items-center gap-2">
          <span className="text-[11px] font-bold uppercase tracking-[0.06em] text-[var(--on-variant)]">Quick set for the modules shown</span>
          {QUICK_PRESETS.map(preset => (
            <button
              key={preset.value} type="button" onClick={() => onQuickSet(preset.value)} title={preset.hint}
              className="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold"
              style={{ background: "var(--surface)", borderColor: "var(--outline-v)", color: "var(--on-bg)" }}
            >
              <i className={`ti ${preset.icon}`} style={{ color: "var(--primary)" }} /> {preset.label}
            </button>
          ))}
          <span className="text-[11px] text-[var(--on-variant)]">Nothing is saved until you press Save baseline.</span>
        </div>
      )}
    </div>
  );
}

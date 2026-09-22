"use client";

import { useRef } from "react";
import {
  moduleDisplayName, PERMISSION_PRESETS,
  type PermissionsMap, type RoleForm, type RoleFormErrors,
} from "../_data";

interface Props {
  form: RoleForm;
  errors: RoleFormErrors;
  permissionsMap: PermissionsMap;
  onChange: (patch: Partial<RoleForm>) => void;
  onClearError: (key: keyof RoleForm) => void;
}

export default function RoleFormFields({ form, errors, permissionsMap, onChange, onClearError }: Props) {
  const modules      = Object.keys(permissionsMap);
  const allCodenames = modules.flatMap(m => (permissionsMap[m] ?? []).map(p => p.codename));

  // ─── Preset helpers ────────────────────────────────────────────────────────

  function applyPreset(matchFn: (c: string) => boolean) {
    onChange({ permission_codenames: allCodenames.filter(matchFn) });
    onClearError("permission_codenames");
  }

  /** Returns true when the current selection exactly matches a preset's output */
  function isPresetActive(matchFn: (c: string) => boolean): boolean {
    const expected = allCodenames.filter(matchFn);
    if (expected.length !== form.permission_codenames.length) return false;
    const current = new Set(form.permission_codenames);
    return expected.every(c => current.has(c));
  }

  // ─── Manual helpers ────────────────────────────────────────────────────────

  function toggleCodename(codename: string) {
    const next = form.permission_codenames.includes(codename)
      ? form.permission_codenames.filter(c => c !== codename)
      : [...form.permission_codenames, codename];
    onChange({ permission_codenames: next });
    onClearError("permission_codenames");
  }

  function toggleModule(module: string, checked: boolean) {
    const moduleCodenames = (permissionsMap[module] ?? []).map(p => p.codename);
    const without = form.permission_codenames.filter(c => !moduleCodenames.includes(c));
    onChange({ permission_codenames: checked ? [...without, ...moduleCodenames] : without });
    onClearError("permission_codenames");
  }

  function selectAll() {
    onChange({ permission_codenames: allCodenames });
    onClearError("permission_codenames");
  }

  function clearAll() {
    onChange({ permission_codenames: [] });
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  return (
    <>
      {/* Display name */}
      <div className="field-group mb-16">
        <label className="field-label">
          Role Name <span style={{ color: "var(--error)" }}>*</span>
        </label>
        <input
          className="field-input"
          placeholder="e.g. Finance Manager"
          value={form.display_name}
          onChange={e => {
            onChange({ display_name: e.target.value });
            onClearError("display_name");
          }}
        />
        {errors.display_name && <span className="field-error">{errors.display_name}</span>}
      </div>

      {/* Can manage team */}
      <div className="field-group mb-16">
        <label style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={form.can_manage_team}
            style={{ accentColor: "var(--primary)", marginTop: 2, flexShrink: 0 }}
            onChange={e => onChange({ can_manage_team: e.target.checked })}
          />
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
              Can manage team
            </div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
              Users with this role appear in manager dropdowns, can access the team dashboard, and bypass the employee onboarding gate.
            </div>
          </div>
        </label>
      </div>

      {/* Can manage branch */}
      <div className="field-group mb-16">
        <label style={{ display: "flex", alignItems: "flex-start", gap: 10, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={form.can_manage_branch}
            style={{ accentColor: "var(--primary)", marginTop: 2, flexShrink: 0 }}
            onChange={e => onChange({ can_manage_branch: e.target.checked })}
          />
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
              Can manage branch
            </div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 2 }}>
              Users with this role have unconditional access to every employee, request, and record within their own branch — not limited to employees specifically assigned to them (unlike HR) or their direct reports (unlike a manager).
            </div>
          </div>
        </label>
      </div>

      {/* Permissions section */}
      <div className="field-group">

        {/* Header row */}
        <div className="flex-between mb-8">
          <label className="field-label">
            Permissions <span style={{ color: "var(--error)" }}>*</span>
          </label>
          <div className="flex-row gap-8">
            <button type="button" className="btn btn-ghost btn-sm" onClick={selectAll}>Select all</button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={clearAll}>Clear</button>
          </div>
        </div>

        {/* ── Quick presets ──────────────────────────────────────────────── */}
        {modules.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--outline)", letterSpacing: "0.06em", textTransform: "uppercase", marginBottom: 8 }}>
              Quick Presets
            </div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {PERMISSION_PRESETS.map(preset => {
                const active = isPresetActive(preset.match);
                return (
                  <button
                    key={preset.key}
                    type="button"
                    title={preset.description}
                    onClick={() => applyPreset(preset.match)}
                    style={{
                      display:        "inline-flex",
                      alignItems:     "center",
                      gap:            6,
                      padding:        "6px 12px",
                      borderRadius:   "var(--radius)",
                      fontSize:       12,
                      fontWeight:     500,
                      cursor:         "pointer",
                      transition:     "all 0.15s",
                      border:         active ? "1.5px solid var(--primary)" : "1.5px solid var(--outline-v)",
                      background:     active ? "rgba(124,58,237,0.10)"       : "transparent",
                      color:          active ? "var(--primary)"              : "var(--on-variant)",
                    }}
                  >
                    <i className={`ti ${preset.icon}`} style={{ fontSize: 14 }} />
                    {preset.label}
                    {active && (
                      <i className="ti ti-check" style={{ fontSize: 12, marginLeft: 2 }} />
                    )}
                  </button>
                );
              })}
            </div>
            {/* Count hint */}
            <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 6 }}>
              {form.permission_codenames.length} of {allCodenames.length} permissions selected
            </div>
          </div>
        )}

        {/* ── Module accordion tree ──────────────────────────────────────── */}
        {modules.length === 0 ? (
          <div style={{ padding: "16px", textAlign: "center", color: "var(--on-variant)", fontSize: 13 }}>
            Loading permissions…
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {modules.map(module => {
              const perms           = permissionsMap[module] ?? [];
              const moduleCodenames = perms.map(p => p.codename);
              const checkedCount    = moduleCodenames.filter(c => form.permission_codenames.includes(c)).length;
              const allChecked      = checkedCount === moduleCodenames.length;
              const someChecked     = checkedCount > 0 && !allChecked;

              return (
                <ModuleBlock
                  key={module}
                  module={module}
                  perms={perms}
                  moduleCodenames={moduleCodenames}
                  checkedCount={checkedCount}
                  allChecked={allChecked}
                  someChecked={someChecked}
                  selectedCodenames={form.permission_codenames}
                  onToggleModule={toggleModule}
                  onToggleCodename={toggleCodename}
                />
              );
            })}
          </div>
        )}

        {errors.permission_codenames && (
          <span className="field-error" style={{ marginTop: 8 }}>{errors.permission_codenames}</span>
        )}
      </div>
    </>
  );
}

/* ─── Module accordion block ─────────────────────────────────────────────── */

interface ModuleBlockProps {
  module: string;
  perms: { codename: string; action: string }[];
  moduleCodenames: string[];
  checkedCount: number;
  allChecked: boolean;
  someChecked: boolean;
  selectedCodenames: string[];
  onToggleModule: (module: string, checked: boolean) => void;
  onToggleCodename: (codename: string) => void;
}

function ModuleBlock({
  module, perms, moduleCodenames, checkedCount, allChecked, someChecked,
  selectedCodenames, onToggleModule, onToggleCodename,
}: ModuleBlockProps) {
  const checkboxRef = useRef<HTMLInputElement>(null);

  return (
    <div style={{ border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", overflow: "hidden" }}>
      {/* Module header — click to select/deselect entire module */}
      <label style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 14px", background: "var(--bg-low)", cursor: "pointer", fontWeight: 500, fontSize: 13 }}>
        <input
          ref={el => {
            if (el) el.indeterminate = someChecked;
            (checkboxRef as React.MutableRefObject<HTMLInputElement | null>).current = el;
          }}
          type="checkbox"
          checked={allChecked}
          style={{ accentColor: "var(--primary)" }}
          onChange={e => onToggleModule(module, e.target.checked)}
        />
        {moduleDisplayName(module)}
        <span style={{ marginLeft: "auto", fontSize: 11, color: checkedCount > 0 ? "var(--primary)" : "var(--on-variant)", fontWeight: checkedCount > 0 ? 600 : 400 }}>
          {checkedCount}/{moduleCodenames.length}
        </span>
      </label>

      {/* Individual action checkboxes */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "6px 12px", padding: "10px 14px", background: "var(--surface)" }}>
        {perms.map(perm => (
          <label key={perm.codename} className="module-check">
            <input
              type="checkbox"
              checked={selectedCodenames.includes(perm.codename)}
              onChange={() => onToggleCodename(perm.codename)}
            />
            {perm.action.charAt(0).toUpperCase() + perm.action.slice(1)}
          </label>
        ))}
      </div>
    </div>
  );
}

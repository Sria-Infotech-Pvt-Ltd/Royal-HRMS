"use client";

// Give one person extra access. They keep everything the company baseline and their seat give them; whatever is
// added here is on top, follows the person (not the seat), and takes effect the next time they sign in.

import { useEffect, useMemo, useState } from "react";
import EmployeeAccessList from "@/components/EmployeeAccessList";
import PermissionChip from "@/components/PermissionChip";
import { usePersonAccess, type PersonSearchResult } from "@/hooks/usePersonAccess";
import { hueOf, initialsOf } from "@/lib/accessListView";
import type { EmployeeAccessRow, PermissionCatalogueItem } from "@/types/orgStructure";

interface Props {
  catalogue: Record<string, PermissionCatalogueItem[]>;
  canEdit: boolean;
}

type View = "all" | "selected" | "addable";

const labelOf = (text: string) => text.replace(/_/g, " ");
// Full access is a seat decision, never a per-person tick.
const NOT_GRANTABLE = "settings.edit";
const VIEWS: { value: View; label: string; icon: string }[] = [
  { value: "all", label: "All modules", icon: "ti-layout-grid" },
  { value: "selected", label: "Extra selected", icon: "ti-user-plus" },
  { value: "addable", label: "Can still add", icon: "ti-plus" },
];

function Tile({ icon, tone, label, value, note }: { icon: string; tone: string; label: string; value: string; note: string }) {
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-[var(--outline-v)] p-3" style={{ background: "var(--surface)" }}>
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-base" style={{ background: `color-mix(in srgb, ${tone} 14%, transparent)`, color: tone }}>
        <i className={`ti ${icon}`} />
      </span>
      <div className="min-w-0">
        <div className="text-[10.5px] font-bold uppercase tracking-[0.06em] text-[var(--on-variant)]">{label}</div>
        <div className="text-lg font-bold leading-tight text-[var(--on-bg)]">{value}</div>
        <div className="truncate text-[11px] text-[var(--on-variant)]">{note}</div>
      </div>
    </div>
  );
}

export default function PersonAccessPanel({ catalogue, canEdit }: Props) {
  const [person, setPerson] = useState<PersonSearchResult | null>(null);
  const [extra, setExtra] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
  const [view, setView] = useState<View>("all");
  const [message, setMessage] = useState<{ text: string; isError: boolean } | null>(null);
  const { access: fetchedAccess, loading, error, isSaving, saveError, saveExtra } = usePersonAccess(person?.uuid ?? null);
  // Ignore a previous person's access while the newly chosen person's is still loading.
  const access = fetchedAccess && fetchedAccess.employee === person?.uuid ? fetchedAccess : null;

  useEffect(() => { if (access) setExtra(access.extra); }, [access]);

  // Where a permission the person already has comes from, so it can be shown ticked and locked.
  const sourceOf = (codename: string): string | null => {
    if (access?.baseline.includes(codename)) return "everyone";
    if (access?.seat?.codenames.includes(codename)) return "their seat";
    return null;
  };
  const searchTerm = filter.trim().toLowerCase();
  const modules = useMemo(() => Object.entries(catalogue)
    .sort(([first], [second]) => first.localeCompare(second))
    .map(([module, items]) => [module, items.filter(item => item.codename !== NOT_GRANTABLE
      && (!searchTerm || `${module} ${item.action} ${item.codename}`.toLowerCase().includes(searchTerm)))] as const)
    .filter(([, items]) => items.length > 0), [catalogue, searchTerm]);
  const addableIn = (items: readonly PermissionCatalogueItem[]) => items.filter(item => !sourceOf(item.codename)).map(item => item.codename);
  const shownModules = modules.filter(([, items]) => {
    if (view === "selected") return items.some(item => extra.includes(item.codename));
    if (view === "addable") return addableIn(items).length > 0;
    return true;
  });

  const saved = access?.extra ?? [];
  const addedCount = extra.filter(codename => !saved.includes(codename)).length;
  const removedCount = saved.filter(codename => !extra.includes(codename)).length;
  const changedCount = addedCount + removedCount;
  const effectiveTotal = access ? new Set([...access.baseline, ...(access.seat?.codenames ?? []), ...extra]).size : 0;

  function toggleExtra(codename: string) {
    setExtra(current => (current.includes(codename) ? current.filter(value => value !== codename) : [...current, codename]));
  }

  function switchModule(items: readonly PermissionCatalogueItem[]) {
    const addable = addableIn(items);
    const isAllOn = addable.length > 0 && addable.every(codename => extra.includes(codename));
    setExtra(current => (isAllOn ? current.filter(codename => !addable.includes(codename)) : [...new Set([...current, ...addable])]));
  }

  function choose(result: EmployeeAccessRow) {
    setPerson(result);
    setMessage(null);
    setView("all");
    setFilter("");
  }

  async function save() {
    const isSaved = await saveExtra(extra);
    setMessage(isSaved ? { text: "Saved. They get the new access the next time they sign in.", isError: false } : null);
  }

  return (
    <div className="space-y-5">
      {!person ? (
        <EmployeeAccessList onSelect={choose} />
      ) : (
        <>
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--outline-v)] p-4" style={{ background: "var(--surface)" }}>
            <div className="flex items-center gap-3">
              <span
                className="flex h-12 w-12 items-center justify-center rounded-full text-sm font-bold"
                style={{ background: `hsl(${hueOf(person.full_name)} 70% 90%)`, color: `hsl(${hueOf(person.full_name)} 45% 32%)` }}
                aria-hidden="true"
              >
                {initialsOf(person.full_name)}
              </span>
              <div>
                <h2 className="text-lg font-bold text-[var(--on-bg)]">{person.full_name}</h2>
                <p className="text-xs text-[var(--on-variant)]">{person.employee_id}{access?.seat ? ` · ${access.seat.title}` : ""}</p>
              </div>
            </div>
            <button type="button" className="btn btn-ghost" onClick={() => { setPerson(null); setMessage(null); }}>
              <i className="ti ti-arrow-left" /> Choose someone else
            </button>
          </div>

          {loading && <p className="text-sm text-[var(--on-variant)]">Loading access…</p>}
          {(error || saveError) && <div className="alert alert-error" role="alert">{error || saveError}</div>}
          {message && <div className={`alert ${message.isError ? "alert-error" : "alert-success"}`} role="status">{message.text}</div>}

          {access && (
            <>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Tile icon="ti-users" tone="var(--on-variant)" label="From everyone" value={String(access.baseline.length)} note="The company baseline" />
                <Tile
                  icon="ti-briefcase" tone="var(--primary-c)" label="From their seat" value={String(access.seat?.codenames.length ?? 0)}
                  note={access.seat ? access.seat.title : "No seat held today"}
                />
                <Tile icon="ti-user-plus" tone="var(--primary)" label="Extra, personally" value={String(extra.length)} note={extra.length === 0 ? "None yet" : "Selected below"} />
                <Tile icon="ti-shield-check" tone="var(--success)" label="Can do in total" value={String(effectiveTotal)} note="All three together" />
              </div>

              <div className="space-y-3">
                <div className="flex flex-wrap items-center gap-3">
                  <div className="relative w-72 max-w-full">
                    <i className="ti ti-search pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--on-variant)]" />
                    <input className="finput w-full !pl-9" type="search" value={filter} onChange={event => setFilter(event.target.value)} placeholder="Search e.g. payroll, leave" aria-label="Search permissions" />
                  </div>
                  <div className="flex flex-wrap gap-1.5" role="group" aria-label="Show">
                    {VIEWS.map(option => (
                      <button
                        key={option.value} type="button" aria-pressed={view === option.value} onClick={() => setView(option.value)}
                        className="inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold"
                        style={view === option.value
                          ? { background: "var(--primary)", borderColor: "var(--primary)", color: "#fff" }
                          : { background: "var(--surface)", borderColor: "var(--outline-v)", color: "var(--on-variant)" }}
                      >
                        <i className={`ti ${option.icon}`} /> {option.label}
                      </button>
                    ))}
                  </div>
                  <span className="ml-auto text-xs text-[var(--on-variant)]">Showing {shownModules.length} of {modules.length} modules</span>
                </div>

                <div className="max-h-[30rem] overflow-y-auto rounded-2xl border border-[var(--outline-v)]" style={{ background: "var(--surface)" }}>
                  {shownModules.length === 0 && <p className="p-4 text-sm text-[var(--on-variant)]">Nothing matches. Clear the search or choose &ldquo;All modules&rdquo;.</p>}
                  {shownModules.map(([module, items]) => {
                    const addable = addableIn(items);
                    const isAllOn = addable.length > 0 && addable.every(codename => extra.includes(codename));
                    return (
                      <div key={module} className="flex flex-col gap-2 border-b border-[var(--outline-v)] px-4 py-3 last:border-b-0 sm:flex-row sm:items-start sm:gap-4">
                        <div className="w-40 shrink-0">
                          <h4 className="text-sm font-semibold capitalize text-[var(--on-bg)]">{labelOf(module)}</h4>
                          <p className="text-[11px] text-[var(--on-variant)]">{items.length - addable.length} already held · {addable.filter(codename => extra.includes(codename)).length} extra</p>
                          {canEdit && addable.length > 0 && (
                            <button type="button" className="mt-1 text-[11px] font-semibold hover:underline" style={{ color: "var(--primary)" }} onClick={() => switchModule(items)}>
                              {isAllOn ? "Remove all extra" : `Add all ${addable.length}`}
                            </button>
                          )}
                        </div>
                        <div className="flex flex-1 flex-wrap gap-2">
                          {items.map(item => {
                            const source = sourceOf(item.codename);
                            return (
                              <PermissionChip
                                key={item.codename} label={labelOf(item.action)} isOn={!!source || extra.includes(item.codename)}
                                isDisabled={!canEdit || !!source} isSensitive={item.is_sensitive} note={source ?? undefined}
                                title={item.description || item.codename} onToggle={() => toggleExtra(item.codename)}
                              />
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {canEdit && (changedCount > 0 || isSaving) && (
                <div className="sticky bottom-4 z-30 flex flex-wrap items-center justify-between gap-3 rounded-2xl border px-4 py-3 shadow-lg" role="status" style={{ background: "var(--surface)", borderColor: "var(--primary)" }}>
                  <span className="text-sm font-semibold text-[var(--on-bg)]">
                    <i className="ti ti-pencil mr-2 text-[var(--primary)]" />
                    {changedCount} unsaved {changedCount === 1 ? "change" : "changes"}
                    <span className="ml-2 text-xs font-normal text-[var(--on-variant)]">{addedCount} to add · {removedCount} to remove</span>
                  </span>
                  <span className="flex gap-2">
                    <button type="button" className="btn btn-ghost" onClick={() => setExtra(saved)} disabled={isSaving}><i className="ti ti-arrow-back-up" /> Discard</button>
                    <button type="button" className="btn btn-filled" onClick={save} disabled={changedCount === 0 || isSaving}>
                      <i className={`ti ${isSaving ? "ti-loader-2 animate-spin" : "ti-device-floppy"}`} /> {isSaving ? "Saving…" : "Save access"}
                    </button>
                  </span>
                </div>
              )}
              {!canEdit && <p className="text-xs text-[var(--on-variant)]">You can view access but only a full-access user can change it.</p>}
            </>
          )}
        </>
      )}
    </div>
  );
}

"use client";

// Give one person extra access. They keep everything the company baseline and their seat give them; whatever is
// added here is on top, follows the person (not the seat), and takes effect the next time they sign in.

import { useEffect, useState } from "react";
import EmployeeAccessList from "@/components/EmployeeAccessList";
import { usePersonAccess, type PersonSearchResult } from "@/hooks/usePersonAccess";
import type { EmployeeAccessRow, PermissionCatalogueItem } from "@/types/orgStructure";

interface Props {
  catalogue: Record<string, PermissionCatalogueItem[]>;
  canEdit: boolean;
}

const labelOf = (text: string) => text.replace(/_/g, " ");
// Full access is a seat decision, never a per-person tick.
const NOT_GRANTABLE = "settings.edit";

export default function PersonAccessPanel({ catalogue, canEdit }: Props) {
  const [person, setPerson] = useState<PersonSearchResult | null>(null);
  const [extra, setExtra] = useState<string[]>([]);
  const [filter, setFilter] = useState("");
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
  const visibleModules = Object.entries(catalogue)
    .sort(([first], [second]) => first.localeCompare(second))
    .map(([module, items]) => [module, items.filter(item => item.codename !== NOT_GRANTABLE
      && (!searchTerm || `${module} ${item.action} ${item.codename}`.toLowerCase().includes(searchTerm)))] as const)
    .filter(([, items]) => items.length > 0);
  const isChanged = !!access && [...extra].sort().join() !== [...access.extra].sort().join();

  function toggleExtra(codename: string) {
    setExtra(current => (current.includes(codename) ? current.filter(value => value !== codename) : [...current, codename]));
  }

  function choose(result: EmployeeAccessRow) {
    setPerson(result);
    setMessage(null);
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
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-[var(--on-bg)]">{person.full_name}</h2>
              <p className="text-xs text-[var(--on-variant)]">{person.employee_id}</p>
            </div>
            <button type="button" className="btn btn-ghost" onClick={() => { setPerson(null); setMessage(null); }}>Choose someone else</button>
          </div>

          {loading && <p className="text-sm text-[var(--on-variant)]">Loading access…</p>}
          {(error || saveError) && <div className="alert alert-error" role="alert">{error || saveError}</div>}
          {message && <div className={`alert ${message.isError ? "alert-error" : "alert-success"}`} role="status">{message.text}</div>}

          {access && (
            <>
              <dl className="space-y-1 text-sm">
                <div className="flex gap-2"><dt className="w-40 text-[var(--on-variant)]">Everyone gets</dt><dd>{access.baseline.length} permissions</dd></div>
                <div className="flex gap-2">
                  <dt className="w-40 text-[var(--on-variant)]">From their seat</dt>
                  <dd>{access.seat ? `${access.seat.title} — ${access.seat.codenames.length} permissions` : "No seat held today"}</dd>
                </div>
              </dl>

              <div>
                <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-bold text-[var(--on-bg)]">Extra access for {person.full_name.split(" ")[0]}</h3>
                    <p className="text-xs text-[var(--on-variant)]">
                      {extra.length === 0 ? "None yet." : `${extra.length} extra permission${extra.length === 1 ? "" : "s"} selected.`} Tick what they should also be able to do.
                    </p>
                  </div>
                  <input className="finput w-64" type="search" value={filter} onChange={event => setFilter(event.target.value)} placeholder="Search e.g. payroll, leave" aria-label="Search permissions" />
                </div>

                <div className="max-h-[26rem] overflow-y-auto rounded-xl border border-[var(--outline-v)]">
                  {visibleModules.length === 0 && <p className="p-4 text-sm text-[var(--on-variant)]">No permission matches that search.</p>}
                  {visibleModules.map(([module, items]) => (
                    <div key={module} className="flex flex-col gap-1.5 border-b border-[var(--outline-v)] px-4 py-3 last:border-b-0 sm:flex-row sm:items-start sm:gap-4">
                      <h4 className="w-36 shrink-0 pt-0.5 text-sm font-semibold capitalize text-[var(--on-bg)]">{labelOf(module)}</h4>
                      <div className="flex flex-1 flex-wrap gap-x-5 gap-y-1.5">
                        {items.map(item => {
                          const source = sourceOf(item.codename);
                          return (
                            <label key={item.codename} className={`flex items-center gap-1.5 text-sm capitalize ${source ? "text-[var(--on-variant)]" : "cursor-pointer text-[var(--on-bg)]"}`} title={item.description || item.codename}>
                              <input
                                type="checkbox"
                                className="h-4 w-4 accent-[var(--primary)]"
                                checked={!!source || extra.includes(item.codename)}
                                disabled={!canEdit || !!source}
                                onChange={() => toggleExtra(item.codename)}
                              />
                              {labelOf(item.action)}
                              {source && <span className="text-[11px] normal-case text-[var(--outline)]">({source})</span>}
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
                {canEdit && (
                  <button type="button" className="btn btn-filled mt-3" onClick={save} disabled={!isChanged || isSaving}>
                    {isSaving ? "Saving…" : "Save access"}
                  </button>
                )}
              </div>
              {!canEdit && <p className="text-xs text-[var(--on-variant)]">You can view access but only a full-access user can change it.</p>}
            </>
          )}
        </>
      )}
    </div>
  );
}

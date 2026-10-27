"use client";

// Give one person extra access. They keep everything the company baseline and their seat give them; whatever is
// added here is on top, follows the person (not the seat), and takes effect the next time they sign in.

import { useEffect, useState } from "react";
import { usePersonAccess, usePersonSearch, type PersonSearchResult } from "@/hooks/usePersonAccess";
import type { PermissionCatalogueItem } from "@/types/orgStructure";

interface Props {
  catalogue: Record<string, PermissionCatalogueItem[]>;
  canEdit: boolean;
}

const labelOf = (text: string) => text.replace(/_/g, " ");
// Full access is a seat decision, never a per-person tick.
const NOT_GRANTABLE = "settings.edit";

export default function PersonAccessPanel({ catalogue, canEdit }: Props) {
  const [term, setTerm] = useState("");
  const [person, setPerson] = useState<PersonSearchResult | null>(null);
  const [extra, setExtra] = useState<string[]>([]);
  const [message, setMessage] = useState<{ text: string; isError: boolean } | null>(null);
  const search = usePersonSearch(person ? "" : term);
  const { access: fetchedAccess, loading, error, isSaving, saveError, saveExtra } = usePersonAccess(person?.uuid ?? null);
  // Ignore a previous person's access while the newly chosen person's is still loading.
  const access = fetchedAccess && fetchedAccess.employee === person?.uuid ? fetchedAccess : null;

  useEffect(() => { if (access) setExtra(access.extra); }, [access]);

  const nameOf = new Map(Object.values(catalogue).flat().map(item => [item.codename, item] as const));
  const alreadyHas = new Set([...(access?.baseline ?? []), ...(access?.seat?.codenames ?? []), ...extra]);
  const isChanged = !!access && [...extra].sort().join() !== [...access.extra].sort().join();

  function choose(result: PersonSearchResult) {
    setPerson(result);
    setTerm("");
    setMessage(null);
  }

  async function save() {
    const isSaved = await saveExtra(extra);
    setMessage(isSaved ? { text: "Saved. They get the new access the next time they sign in.", isError: false } : null);
  }

  return (
    <div className="space-y-5">
      {!person ? (
        <div>
          <label className="mb-1 block text-sm font-semibold text-[var(--on-bg)]" htmlFor="person-search">Find an employee</label>
          <input id="person-search" className="finput w-full max-w-md" type="search" value={term} onChange={event => setTerm(event.target.value)} placeholder="Name or email" autoComplete="off" />
          {search.loading && <p className="mt-2 text-xs text-[var(--on-variant)]">Searching…</p>}
          {search.error && <p className="mt-2 text-xs text-[var(--error)]">{search.error}</p>}
          {search.isSearching && !search.loading && search.results.length === 0 && (
            <p className="mt-2 text-xs text-[var(--on-variant)]">No employee found.</p>
          )}
          <ul className="mt-2 max-w-md divide-y divide-[var(--outline-v)]">
            {search.results.map(result => (
              <li key={result.uuid}>
                <button type="button" className="flex w-full items-center justify-between py-2.5 text-left hover:text-[var(--primary)]" onClick={() => choose(result)}>
                  <span className="text-sm font-medium">{result.full_name}</span>
                  <span className="text-xs text-[var(--on-variant)]">{result.employee_id}{result.designation ? ` · ${result.designation}` : ""}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
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
                <h3 className="mb-2 text-sm font-bold text-[var(--on-bg)]">Extra access for {person.full_name.split(" ")[0]}</h3>
                {extra.length === 0 && <p className="text-sm text-[var(--on-variant)]">None yet.</p>}
                <ul className="flex flex-wrap gap-2">
                  {extra.map(codename => {
                    const item = nameOf.get(codename);
                    return (
                      <li key={codename} className="flex items-center gap-1.5 rounded-full bg-[var(--sec-c)] py-1 pl-3 pr-1.5 text-xs font-semibold text-[var(--primary)]">
                        <span className="capitalize">{labelOf(codename.split(".")[0])} · {labelOf(item?.action ?? codename.split(".")[1] ?? codename)}</span>
                        {canEdit && (
                          <button type="button" className="flex h-5 w-5 items-center justify-center rounded-full hover:bg-[var(--surface)]" aria-label={`Remove ${codename}`} onClick={() => setExtra(extra.filter(value => value !== codename))}>
                            <i className="ti ti-x" />
                          </button>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>

              {canEdit && (
                <div className="flex flex-wrap items-center gap-3">
                  <select className="finput w-72" value="" onChange={event => { if (event.target.value) setExtra([...extra, event.target.value]); }} aria-label="Add a permission">
                    <option value="">+ Add a permission…</option>
                    {Object.entries(catalogue).sort(([a], [b]) => a.localeCompare(b)).map(([module, items]) => {
                      const available = items.filter(item => item.codename !== NOT_GRANTABLE && !alreadyHas.has(item.codename));
                      return available.length === 0 ? null : (
                        <optgroup key={module} label={labelOf(module)}>
                          {available.map(item => <option key={item.codename} value={item.codename}>{labelOf(item.action)}</option>)}
                        </optgroup>
                      );
                    })}
                  </select>
                  <button type="button" className="btn btn-filled" onClick={save} disabled={!isChanged || isSaving}>
                    {isSaving ? "Saving…" : "Save access"}
                  </button>
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

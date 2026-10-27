"use client";

import { useEffect, useMemo, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import ToggleSwitch from "@/components/ToggleSwitch";
import type { PermissionCatalogueItem, Position, PositionPermissions } from "@/types/orgStructure";

interface Props {
  position: Position | null;
  onClose: () => void;
  onSaved: () => void;
}

export default function PositionPermissionsModal({ position, onClose, onSaved }: Props) {
  const [catalogue, setCatalogue] = useState<Record<string, PermissionCatalogueItem[]>>({});
  const [granted, setGranted] = useState<Set<string>>(new Set());
  const [canManageTeam, setCanManageTeam] = useState(false);
  const [canManageBranch, setCanManageBranch] = useState(false);
  const [search, setSearch] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [loadedPositionId, setLoadedPositionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const positionId = position?.id;

  useEffect(() => {
    if (!positionId) return;
    let isCurrent = true;
    setIsLoading(true);
    setError(null);
    setSearch("");
    setLoadedPositionId(null);
    setGranted(new Set());

    Promise.all([
      clientApi.get<{ data: { results: Record<string, PermissionCatalogueItem[]> } }>(API.permissions.list, { params: { page_size: 500 } }),
      clientApi.get<{ data: PositionPermissions }>(API.orgStructure.positions.permissions(positionId)),
    ])
      .then(([catalogueResponse, seatResponse]) => {
        if (!isCurrent) return;
        setCatalogue(catalogueResponse.data.data.results ?? {});
        setGranted(new Set(seatResponse.data.data.codenames));
        setCanManageTeam(seatResponse.data.data.can_manage_team);
        setCanManageBranch(seatResponse.data.data.can_manage_branch);
        setLoadedPositionId(positionId);
      })
      .catch((err: unknown) => {
        if (isCurrent) {
          setError(
            (err as { response?: { data?: { message?: string } }; message?: string })?.response?.data?.message
              ?? (err as { message?: string })?.message
              ?? "Could not load this position's permissions.",
          );
        }
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });

    return () => { isCurrent = false; };
  }, [positionId]);

  const filteredModules = useMemo(() => {
    const term = search.trim().toLowerCase();
    return Object.entries(catalogue)
      .map(([module, items]) => [
        module,
        term
          ? items.filter(item =>
              `${item.action} ${item.codename} ${item.description ?? ""}`.toLowerCase().includes(term),
            )
          : items,
      ] as const)
      .filter(([, items]) => items.length > 0);
  }, [catalogue, search]);

  function toggle(codename: string) {
    setGranted(previous => {
      const next = new Set(previous);
      if (next.has(codename)) next.delete(codename);
      else next.add(codename);
      return next;
    });
  }

  async function save() {
    if (!position || loadedPositionId !== position.id || error) return;
    setIsSaving(true);
    setError(null);
    try {
      await clientApi.put(API.orgStructure.positions.permissions(position.id), {
        codenames: [...granted],
        can_manage_team: canManageTeam,
        can_manage_branch: canManageBranch,
      });
      onSaved();
    } catch (err: unknown) {
      setError(
        (err as { response?: { data?: { message?: string } }; message?: string })?.response?.data?.message
          ?? (err as { message?: string })?.message
          ?? "Could not save these permissions.",
      );
    } finally {
      setIsSaving(false);
    }
  }

  if (!position) return null;

  return (
    <Modal
      title={<><i className="ti ti-shield-lock" style={{ marginRight: 8 }} />Position access</>}
      onClose={onClose}
      maxWidth={900}
      scrollBody
      footer={
        <>
          <span className="mr-auto text-xs text-[var(--on-variant)]">
            {granted.size} permission{granted.size === 1 ? "" : "s"} selected
          </span>
          <button className="btn btn-ghost" type="button" onClick={onClose} disabled={isSaving}>Cancel</button>
          <button className="btn btn-filled" type="button" onClick={save} disabled={isSaving || isLoading || loadedPositionId !== position.id || !!error}>
            <i className={`ti ${isSaving ? "ti-loader-2 animate-spin" : "ti-device-floppy"}`} />
            {isSaving ? "Saving…" : "Save access"}
          </button>
        </>
      }
    >
      <div className="space-y-5">
        <section className="rounded-2xl border border-[var(--outline-v)] bg-[var(--bg-low)] p-4 md:p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="flex min-w-0 items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[var(--sec-c)] text-[var(--primary)]">
                <i className="ti ti-id-badge-2 text-lg" />
              </span>
              <div className="min-w-0">
                <h2 className="truncate text-base font-bold text-[var(--on-bg)]">{position.title}</h2>
                <p className="mt-0.5 text-sm text-[var(--on-variant)]">{position.org_unit_name}</p>
                <p className="mt-2 text-xs text-[var(--on-variant)]">
                  Current holder: <strong className="text-[var(--on-bg)]">{position.holder_name ?? "Vacant position"}</strong>
                  {position.is_chief && <span className="ml-2 rounded-full bg-[var(--warn-c)] px-2 py-0.5 font-semibold text-[var(--warn)]">Unit head</span>}
                </p>
              </div>
            </div>
            <div className="rounded-full border border-[var(--primary-c)] bg-[var(--surface)] px-3 py-1.5 text-xs font-semibold text-[var(--primary)]">
              {granted.size} permissions enabled
            </div>
          </div>
          <div className="mt-4 flex items-start gap-2 rounded-xl border border-[var(--info-c)] bg-[var(--surface)] p-3 text-xs leading-5 text-[var(--on-variant)]">
            <i className="ti ti-info-circle mt-0.5 shrink-0 text-base text-[var(--info)]" />
            <p>
              These permissions belong to this position. The current holder receives them; a future holder receives the same access.
              Permissions do not automatically pass between a manager and their reports. Give each position its own access below.
            </p>
          </div>
        </section>

        <section aria-label="Access scope" className="space-y-3">
          <div>
            <h3 className="text-sm font-bold text-[var(--on-bg)]">Data scope</h3>
            <p className="mt-1 text-xs text-[var(--on-variant)]">Choose the team or branch visibility associated with this position.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <label className="flex min-h-20 items-center justify-between gap-4 rounded-xl border border-[var(--outline-v)] bg-[var(--surface)] p-4">
              <span>
                <span className="block text-sm font-semibold text-[var(--on-bg)]">Team manager</span>
                <span className="mt-1 block text-xs leading-5 text-[var(--on-variant)]">Marks this position as a team manager for manager-based workflows.</span>
              </span>
              <ToggleSwitch checked={canManageTeam} onChange={setCanManageTeam} />
            </label>
            <label className="flex min-h-20 items-center justify-between gap-4 rounded-xl border border-[var(--outline-v)] bg-[var(--surface)] p-4">
              <span>
                <span className="block text-sm font-semibold text-[var(--on-bg)]">Branch-wide access</span>
                <span className="mt-1 block text-xs leading-5 text-[var(--on-variant)]">Enables branch scope where the module supports it.</span>
              </span>
              <ToggleSwitch checked={canManageBranch} onChange={setCanManageBranch} />
            </label>
          </div>
        </section>

        <section aria-label="Position permissions">
          <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h3 className="text-sm font-bold text-[var(--on-bg)]">Module permissions</h3>
              <p className="mt-1 text-xs text-[var(--on-variant)]">Select only the actions required for this position.</p>
            </div>
            <label className="relative w-full sm:w-64">
              <i className="ti ti-search pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--on-variant)]" />
              <input
                className="finput w-full pl-9"
                type="search"
                value={search}
                onChange={event => setSearch(event.target.value)}
                placeholder="Search modules or actions"
                aria-label="Search permissions"
              />
            </label>
          </div>

          {error && <div className="alert alert-error mb-3" role="alert"><i className="ti ti-alert-circle" />{error}</div>}
          {isLoading ? (
            <div className="rounded-xl border border-[var(--outline-v)] bg-[var(--bg-low)] px-4 py-10 text-center text-sm text-[var(--on-variant)]">
              <i className="ti ti-loader-2 mr-2 animate-spin text-lg text-[var(--primary)]" />
              Loading position permissions…
            </div>
          ) : filteredModules.length === 0 ? (
            <div className="rounded-xl border border-dashed border-[var(--outline)] px-4 py-10 text-center text-sm text-[var(--on-variant)]">
              No permissions match that search.
            </div>
          ) : (
            <div className="grid items-start gap-3 md:grid-cols-2">
              {filteredModules.map(([module, items]) => {
                const enabled = items.filter(item => granted.has(item.codename)).length;
                return (
                  <section key={module} className="overflow-hidden rounded-xl border border-[var(--outline-v)] bg-[var(--surface)]">
                    <div className="flex items-center justify-between gap-3 border-b border-[var(--outline-v)] px-4 py-3">
                      <h4 className="text-xs font-bold uppercase tracking-[0.08em] text-[var(--on-variant)]">{module.replace(/_/g, " ")}</h4>
                      <span className="text-xs font-medium text-[var(--on-variant)]">{enabled}/{items.length}</span>
                    </div>
                    <div className="space-y-1 p-2">
                      {items.map(item => {
                        const isGranted = granted.has(item.codename);
                        return (
                          <label
                            key={item.codename}
                            className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                              isGranted
                                ? "border-[var(--primary-c)] bg-[var(--sec-c)]"
                                : "border-transparent hover:border-[var(--outline-v)] hover:bg-[var(--bg-low)]"
                            }`}
                          >
                            <input
                              className="mt-0.5 h-4 w-4 shrink-0 accent-[var(--primary)]"
                              type="checkbox"
                              checked={isGranted}
                              onChange={() => toggle(item.codename)}
                            />
                            <span className="min-w-0 flex-1">
                              <span className="flex items-center gap-1.5 text-sm font-semibold capitalize text-[var(--on-bg)]">
                                {item.action}
                                {item.is_sensitive && <i className="ti ti-alert-triangle text-xs text-[var(--warn)]" aria-label="Sensitive permission" />}
                              </span>
                              {item.description && <span className="mt-0.5 block text-xs leading-4 text-[var(--on-variant)]">{item.description}</span>}
                              <span className="mt-1 block truncate font-mono text-[10px] text-[var(--outline)]">{item.codename}</span>
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  </section>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </Modal>
  );
}

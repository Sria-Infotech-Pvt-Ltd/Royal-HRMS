"use client";

// Bulk-applies one PermissionTemplate to as many positions as you pick in
// one action — the alternative to opening each position's own "Position
// access" modal one at a time (the exact complaint this screen exists to
// fix: giving the same access to 50 managers shouldn't mean 50 separate
// edits).

import { useEffect, useMemo, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import type { Position } from "@/types/orgStructure";
import type { PermissionTemplate } from "./permissionTemplateTypes";

interface Props {
  template:  PermissionTemplate;
  onClose:   () => void;
  onApplied: (count: number) => void;
}

export default function ApplyTemplateModal({ template, onClose, onApplied }: Props) {
  const [positions, setPositions] = useState<Position[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [isApplying, setIsApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  // Two-step flow: pick positions, THEN see exactly what's about to change
  // and confirm — applying wipes each selected position's current
  // permissions (replace, not merge), so a one-click "Apply" with no
  // checkpoint was too easy to fire by accident on the wrong selection.
  const [step, setStep] = useState<"select" | "confirm">("select");

  useEffect(() => {
    clientApi.get<{ data: { results: Position[] } }>(API.orgStructure.positions.list, { params: { page_size: 1000 } })
      .then(({ data }) => setPositions(data.data.results ?? []))
      .catch(() => setLoadError("Could not load positions."));
  }, []);

  const term = search.trim().toLowerCase();
  const filtered = useMemo(() => {
    if (!positions) return [];
    if (!term) return positions;
    return positions.filter(p =>
      `${p.title} ${p.org_unit_name} ${p.holder_name ?? ""}`.toLowerCase().includes(term),
    );
  }, [positions, term]);

  function toggle(id: string) {
    setSelected(previous => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function selectAllFiltered() {
    setSelected(previous => {
      const allSelected = filtered.length > 0 && filtered.every(p => previous.has(p.id));
      const next = new Set(previous);
      filtered.forEach(p => { if (allSelected) next.delete(p.id); else next.add(p.id); });
      return next;
    });
  }

  async function apply() {
    if (selected.size === 0) return;
    setIsApplying(true);
    setApplyError(null);
    try {
      await clientApi.post(API.settings.permissionTemplateApply(template.id), { position_ids: [...selected] });
      onApplied(selected.size);
    } catch (err: unknown) {
      setApplyError(
        (err as { response?: { data?: { message?: string } }; message?: string })?.response?.data?.message
          ?? (err as { message?: string })?.message
          ?? "Could not apply this template.",
      );
    } finally {
      setIsApplying(false);
    }
  }

  const allFilteredSelected = filtered.length > 0 && filtered.every(p => selected.has(p.id));
  const selectedPositions = (positions ?? []).filter(p => selected.has(p.id));

  if (step === "confirm") {
    return (
      <Modal
        title={<>Confirm applying <span style={{ color: "var(--primary)", fontStyle: "italic" }}>{template.name}</span></>}
        onClose={onClose}
        maxWidth={640}
        scrollBody
        footer={
          <>
            <button className="btn btn-ghost" type="button" onClick={() => setStep("select")} disabled={isApplying}>
              <i className="ti ti-arrow-left" /> Back
            </button>
            <button className="btn btn-filled" type="button" style={{ background: "var(--error)" }} onClick={apply} disabled={isApplying}>
              <i className={`ti ${isApplying ? "ti-loader-2 animate-spin" : "ti-alert-triangle"}`} />
              {isApplying ? "Applying…" : `Yes, apply to ${selected.size} position${selected.size === 1 ? "" : "s"}`}
            </button>
          </>
        }
      >
        <div className="mb-4 flex items-start gap-2 rounded-xl border border-[var(--error)] bg-[var(--error-c)] p-3 text-sm leading-6 text-[var(--on-bg)]">
          <i className="ti ti-alert-triangle mt-0.5 shrink-0 text-base text-[var(--error)]" />
          <p>
            <strong>This replaces, not adds to, each position&apos;s current permissions.</strong> Any permission a
            selected position already has that isn&apos;t part of &quot;{template.name}&quot; below will be removed.
            This can&apos;t be undone automatically — you&apos;d have to re-set it manually afterward.
          </p>
        </div>

        <h4 className="mb-2 text-xs font-bold uppercase tracking-[0.06em] text-[var(--on-variant)]">
          &quot;{template.name}&quot; will give these positions
        </h4>
        <div className="mb-4 flex flex-wrap gap-2">
          {template.can_manage_team && <span className="rounded-full bg-[var(--sec-c)] px-2.5 py-1 text-xs font-semibold text-[var(--primary)]">Team manager</span>}
          {template.can_manage_branch && <span className="rounded-full bg-[var(--sec-c)] px-2.5 py-1 text-xs font-semibold text-[var(--primary)]">Branch-wide access</span>}
          {template.permission_codenames.length === 0 ? (
            <span className="text-xs text-[var(--on-variant)]">No module permissions.</span>
          ) : (
            template.permission_codenames.map(codename => (
              <span key={codename} className="rounded-full bg-[var(--bg-low)] px-2.5 py-1 font-mono text-[11px] text-[var(--on-variant)]">{codename}</span>
            ))
          )}
        </div>

        <h4 className="mb-2 text-xs font-bold uppercase tracking-[0.06em] text-[var(--on-variant)]">
          On these {selectedPositions.length} position{selectedPositions.length === 1 ? "" : "s"}
        </h4>
        <div className="rounded-xl border border-[var(--outline-v)]" style={{ maxHeight: 280, overflowY: "auto" }}>
          {selectedPositions.map(position => (
            <div key={position.id} className="border-b border-[var(--outline-v)] px-3 py-2.5 last:border-b-0">
              <span className="block truncate text-sm font-semibold text-[var(--on-bg)]">{position.title}</span>
              <span className="block truncate text-xs text-[var(--on-variant)]">{position.org_unit_name} · {position.holder_name ?? "Vacant"}</span>
            </div>
          ))}
        </div>

        {applyError && <div className="alert alert-error mt-3" role="alert"><i className="ti ti-alert-circle" />{applyError}</div>}
      </Modal>
    );
  }

  return (
    <Modal
      title={<>Apply <span style={{ color: "var(--primary)", fontStyle: "italic" }}>{template.name}</span></>}
      onClose={onClose}
      maxWidth={640}
      scrollBody
      footer={
        <>
          <span className="mr-auto text-xs text-[var(--on-variant)]">{selected.size} position{selected.size === 1 ? "" : "s"} selected</span>
          <button className="btn btn-ghost" type="button" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" type="button" onClick={() => setStep("confirm")} disabled={selected.size === 0}>
            Review & apply <i className="ti ti-arrow-right" />
          </button>
        </>
      }
    >
      <div className="mb-3 flex items-start gap-2 rounded-xl border border-[var(--warn-c)] bg-[var(--warn-c)] p-3 text-xs leading-5 text-[var(--on-bg)]">
        <i className="ti ti-alert-triangle mt-0.5 shrink-0 text-base text-[var(--warn)]" />
        <p>
          <strong>Heads up:</strong> applying this <strong>replaces</strong> each selected position&apos;s current permissions and scope
          flags — it doesn&apos;t add on top of what they already have. You&apos;ll see exactly what changes before anything is saved.
        </p>
      </div>

      <label className="relative mb-3 block">
        <i className="ti ti-search pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[var(--on-variant)]" />
        <input
          className="finput w-full pl-9"
          type="search"
          value={search}
          onChange={event => setSearch(event.target.value)}
          placeholder="Search positions, org units, or holder names"
          aria-label="Search positions"
        />
      </label>

      {loadError && <div className="alert alert-error mb-3" role="alert"><i className="ti ti-alert-circle" />{loadError}</div>}

      {!positions && !loadError ? (
        <p className="py-10 text-center text-sm text-[var(--on-variant)]"><i className="ti ti-loader-2 mr-2 animate-spin text-[var(--primary)]" />Loading positions…</p>
      ) : filtered.length === 0 ? (
        <p className="py-10 text-center text-sm text-[var(--on-variant)]">No positions match that search.</p>
      ) : (
        <div className="rounded-xl border border-[var(--outline-v)]">
          <label className="flex items-center gap-2 border-b border-[var(--outline-v)] bg-[var(--bg-low)] px-3 py-2 text-xs font-semibold text-[var(--on-variant)]">
            <input type="checkbox" className="h-4 w-4 accent-[var(--primary)]" checked={allFilteredSelected} onChange={selectAllFiltered} />
            Select all {term ? "matching" : ""} positions ({filtered.length})
          </label>
          <div style={{ maxHeight: 360, overflowY: "auto" }}>
            {filtered.map(position => (
              <label key={position.id} className="flex cursor-pointer items-center gap-3 border-b border-[var(--outline-v)] px-3 py-2.5 last:border-b-0 hover:bg-[var(--bg-low)]">
                <input
                  type="checkbox"
                  className="h-4 w-4 shrink-0 accent-[var(--primary)]"
                  checked={selected.has(position.id)}
                  onChange={() => toggle(position.id)}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-[var(--on-bg)]">{position.title}</span>
                  <span className="block truncate text-xs text-[var(--on-variant)]">
                    {position.org_unit_name} · {position.holder_name ?? "Vacant"}
                  </span>
                </span>
              </label>
            ))}
          </div>
        </div>
      )}
    </Modal>
  );
}

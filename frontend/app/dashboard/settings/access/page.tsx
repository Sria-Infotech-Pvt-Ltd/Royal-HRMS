"use client";

// Access is decided by the org chart: each Position carries its own permissions (Organization > a position >
// Permissions). This page only sets what EVERY employee can do regardless of seat — self-service such as
// requesting leave or viewing their own payslip.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import PermissionMatrix from "@/components/PermissionMatrix";
import PersonAccessPanel from "@/components/PersonAccessPanel";
import type { PermissionCatalogueItem } from "@/types/orgStructure";

interface Catalogue { results: Record<string, PermissionCatalogueItem[]> }
interface Baseline { codenames: string[] }

// Granting this to everyone would give every employee the keys to Settings, so it stays seat-only.
const LOCKED_CODENAMES = ["settings.edit"] as const;

export default function AccessSettingsPage() {
  const router = useRouter();
  const canEdit = usePermission("settings.edit");
  const catalogue = useFetch<Catalogue>(`${API.permissions.list}?page_size=500`);
  const baseline = useFetch<Baseline>(API.access.baselinePermissions);
  const [granted, setGranted] = useState<Set<string>>(new Set());
  const [tab, setTab] = useState<"everyone" | "person">("everyone");
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; isError: boolean } | null>(null);

  useEffect(() => {
    if (baseline.data) setGranted(new Set(baseline.data.codenames));
  }, [baseline.data]);

  function toggle(codename: string) {
    setGranted(previous => {
      const next = new Set(previous);
      if (next.has(codename)) next.delete(codename); else next.add(codename);
      return next;
    });
  }

  function toggleMany(codenames: string[], isOn: boolean) {
    setGranted(previous => {
      const next = new Set(previous);
      codenames.forEach(codename => { if (isOn) next.add(codename); else next.delete(codename); });
      return next;
    });
  }

  async function save() {
    setIsSaving(true);
    setMessage(null);
    try {
      await clientApi.put(API.access.baselinePermissions, { codenames: [...granted] });
      setMessage({ text: "Saved. Takes effect the next time each person signs in.", isError: false });
      baseline.refetch();
    } catch (err: unknown) {
      setMessage({ text: (err as { message?: string })?.message ?? "Could not save.", isError: true });
    } finally {
      setIsSaving(false);
    }
  }

  const modules = Object.entries(catalogue.data?.results ?? {}).sort(([a], [b]) => a.localeCompare(b));
  const permissionCount = modules.reduce((total, [, items]) => total + items.length, 0);
  const grantedCount = modules.reduce(
    (total, [, items]) => total + items.filter(item => granted.has(item.codename)).length,
    0,
  );

  const isLoading = catalogue.loading || baseline.loading;
  const loadError = catalogue.error || baseline.error;
  const catalogueByModule = catalogue.data?.results ?? {};

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6 pb-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <button className="btn btn-ghost" type="button" onClick={() => router.push("/dashboard/settings")}>
          <i className="ti ti-arrow-left" /> Back to Settings
        </button>
        {canEdit && tab === "everyone" && (
          <button className="btn btn-filled" type="button" onClick={save} disabled={isSaving || isLoading}>
            <i className={`ti ${isSaving ? "ti-loader-2 animate-spin" : "ti-device-floppy"}`} />
            {isSaving ? "Saving…" : "Save baseline"}
          </button>
        )}
      </div>

      <header>
        <h1 className="text-2xl font-bold text-[var(--on-bg)]">Access</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--on-variant)]">
          Everyone gets the baseline. On top of that, each person gets the access of the position they hold
          (set in <Link className="font-semibold text-[var(--primary)] hover:underline" href="/dashboard/org-chart">Organization</Link>),
          plus any extra access you give them personally.
        </p>
      </header>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "everyone"} className={`tab${tab === "everyone" ? " active" : ""}`} onClick={() => setTab("everyone")}>
          Everyone
        </button>
        <button role="tab" aria-selected={tab === "person"} className={`tab${tab === "person" ? " active" : ""}`} onClick={() => setTab("person")}>
          One person
        </button>
      </div>

      {loadError && <div className="alert alert-error" role="alert">{loadError}</div>}
      {message && <div className={`alert ${message.isError ? "alert-error" : "alert-success"}`} role="status">{message.text}</div>}

      {isLoading ? (
        <p className="py-10 text-center text-sm text-[var(--on-variant)]">
          <i className="ti ti-loader-2 mr-2 animate-spin text-[var(--primary)]" />Loading permissions…
        </p>
      ) : loadError ? null : tab === "person" ? (
        <PersonAccessPanel catalogue={catalogueByModule} canEdit={canEdit} />
      ) : modules.length === 0 ? (
        <p className="py-10 text-center text-sm text-[var(--on-variant)]">No permissions are available.</p>
      ) : (
        <>
          <p className="text-sm text-[var(--on-variant)]">
            What every employee can do, whatever their position. <strong className="text-[var(--on-bg)]">{grantedCount} of {permissionCount}</strong> enabled.
          </p>
          <PermissionMatrix
            modules={modules}
            granted={granted}
            onToggle={toggle}
            onToggleMany={toggleMany}
            lockedCodenames={LOCKED_CODENAMES}
            isReadOnly={!canEdit}
          />
          {!canEdit && <p className="text-center text-xs text-[var(--on-variant)]">You have read-only access to baseline permissions.</p>}
        </>
      )}
    </div>
  );
}

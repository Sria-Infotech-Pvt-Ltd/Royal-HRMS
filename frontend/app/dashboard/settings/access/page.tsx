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

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5 pb-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <button className="btn btn-ghost" type="button" onClick={() => router.push("/dashboard/settings")}>
          <i className="ti ti-arrow-left" /> Back to Settings
        </button>
        {canEdit && (
          <button className="btn btn-filled" type="button" onClick={save} disabled={isSaving || catalogue.loading || baseline.loading}>
            <i className={`ti ${isSaving ? "ti-loader-2 animate-spin" : "ti-device-floppy"}`} />
            {isSaving ? "Saving…" : "Save baseline"}
          </button>
        )}
      </div>

      <header className="rounded-2xl border border-[var(--outline-v)] bg-[var(--surface)] p-5 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="flex min-w-0 items-start gap-4">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[var(--sec-c)] text-[var(--primary)]">
            <i className="ti ti-shield-lock text-xl" />
          </div>
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.12em] text-[var(--primary)]">People &amp; security</p>
            <h1 className="text-2xl font-bold text-[var(--on-bg)]">Access</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--on-variant)]">
              Baseline permissions apply to every employee, regardless of position. Configure position-specific access from{" "}
              <Link className="font-semibold text-[var(--primary)] hover:underline" href="/dashboard/org-chart">Organization</Link>.
            </p>
          </div>
          </div>
          <Link className="btn btn-filled shrink-0" href="/dashboard/org-chart">
            <i className="ti ti-sitemap" /> Manage position access
          </Link>
        </div>
      </header>

      {message && (
        <div className={`alert ${message.isError ? "alert-error" : "alert-success"}`} role="status">{message.text}</div>
      )}

      {(catalogue.error || baseline.error) && (
        <div className="alert alert-error" role="alert">
          {catalogue.error || baseline.error}
        </div>
      )}

      <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[var(--outline-v)] bg-[var(--surface)] p-4 md:px-6" aria-label="Baseline permission summary">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--bg-mid)] text-[var(--on-variant)]">
            <i className="ti ti-users text-lg" />
          </span>
          <div>
            <h2 className="font-semibold text-[var(--on-bg)]">Everyone baseline</h2>
            <p className="text-xs text-[var(--on-variant)]">Applies across all positions</p>
          </div>
        </div>
        <div className="rounded-full bg-[var(--sec-c)] px-3 py-1.5 text-sm font-semibold text-[var(--primary)]">
          {catalogue.loading || baseline.loading ? "Loading permissions…" : `${grantedCount} of ${permissionCount} enabled`}
        </div>
      </section>

      {catalogue.loading || baseline.loading ? (
        <div className="rounded-2xl border border-[var(--outline-v)] bg-[var(--surface)] px-6 py-12 text-center text-sm text-[var(--on-variant)]">
          <i className="ti ti-loader-2 mr-2 animate-spin text-lg text-[var(--primary)]" />
          Loading permissions…
        </div>
      ) : catalogue.error || baseline.error ? null : modules.length === 0 ? (
        <div className="rounded-2xl border border-[var(--outline-v)] bg-[var(--surface)] px-6 py-12 text-center text-sm text-[var(--on-variant)]">
          No permissions are available.
        </div>
      ) : (
        <PermissionMatrix
          modules={modules}
          granted={granted}
          onToggle={toggle}
          onToggleMany={toggleMany}
          lockedCodenames={LOCKED_CODENAMES}
          isReadOnly={!canEdit}
        />
      )}

      {!canEdit && (
        <p className="text-center text-xs text-[var(--on-variant)]">
          You have read-only access to baseline permissions.
        </p>
      )}
    </div>
  );
}

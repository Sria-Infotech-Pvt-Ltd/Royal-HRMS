"use client";

// Access is decided by the org chart: each Position carries its own permissions (Organization > a position >
// Permissions). This page only sets what EVERY employee can do regardless of seat — self-service such as
// requesting leave or viewing their own payslip.

import Link from "next/link";
import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import type { PermissionCatalogueItem } from "@/types/orgStructure";

interface Catalogue { results: Record<string, PermissionCatalogueItem[]> }
interface Baseline { codenames: string[] }

export default function AccessSettingsPage() {
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

  const modules = Object.entries(catalogue.data?.results ?? {});

  return (
    <div className="page">
      <div className="pagehead">
        <div>
          <h1>Access</h1>
          <p className="lede">
            What a person can do depends on the position they hold. Set a position&apos;s permissions from{" "}
            <Link href="/dashboard/org-chart">Organization</Link>. The permissions below are given to every employee.
          </p>
        </div>
      </div>

      {message && (
        <div className={`alert ${message.isError ? "alert-error" : "alert-success"}`} style={{ marginBottom: 12 }}>{message.text}</div>
      )}

      <div className="card" style={{ padding: 20 }}>
        <div style={{ fontWeight: 700, marginBottom: 12 }}>Everyone (baseline)</div>
        {catalogue.loading || baseline.loading ? <div>Loading…</div> : modules.map(([module, items]) => (
          <div key={module} style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase", color: "var(--on-variant)", marginBottom: 6 }}>
              {module.replace(/_/g, " ")}
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {items.map(item => (
                <label key={item.codename} className="chip" style={{ cursor: canEdit ? "pointer" : "default", display: "inline-flex", gap: 6, alignItems: "center" }}>
                  <input type="checkbox" disabled={!canEdit || item.codename === "settings.edit"} checked={granted.has(item.codename)} onChange={() => toggle(item.codename)} />
                  {item.action}{item.is_sensitive ? " ⚠" : ""}
                </label>
              ))}
            </div>
          </div>
        ))}
        {canEdit && (
          <button className="btn btn-filled" onClick={save} disabled={isSaving}>{isSaving ? "Saving…" : "Save baseline"}</button>
        )}
      </div>
    </div>
  );
}

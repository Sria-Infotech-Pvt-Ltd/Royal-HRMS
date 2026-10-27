"use client";

import { useState, type FormEvent } from "react";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { CompanyAllowance } from "@/types/payroll";

function getErrorMessage(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null && "message" in error && typeof error.message === "string") {
    return error.message;
  }
  return fallback;
}

export default function AllowanceCatalogueTab() {
  const { data: allowances, loading, error, refetch } = useFetch<CompanyAllowance[]>(API.payroll.allowances);
  const canCreate = usePermission("payroll.create");
  const canEdit = usePermission("payroll.edit");
  const [name, setName] = useState("");
  const [isTaxable, setIsTaxable] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  async function addAllowance(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;
    setSaving(true);
    setErrorMessage("");
    setSuccessMessage("");
    try {
      await clientApi.post(API.payroll.allowances, { name: trimmedName, is_taxable: isTaxable });
      setName("");
      setIsTaxable(true);
      setSuccessMessage("Allowance added to the company catalogue.");
      refetch();
    } catch (requestError: unknown) {
      setErrorMessage(getErrorMessage(requestError, "Could not add the allowance."));
    } finally {
      setSaving(false);
    }
  }

  async function toggleAllowance(allowance: CompanyAllowance) {
    setSaving(true);
    setErrorMessage("");
    setSuccessMessage("");
    try {
      await clientApi.put(API.payroll.allowance(allowance.id), { is_active: !allowance.is_active });
      setSuccessMessage(
        allowance.is_active
          ? "Allowance deactivated. Existing salary structures are unchanged."
          : "Allowance activated for salary structures.",
      );
      refetch();
    } catch (requestError: unknown) {
      setErrorMessage(getErrorMessage(requestError, "Could not update the allowance."));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="card">
      <div className="px-5 py-4 border-b border-[var(--outline-v)]">
        <div className="font-semibold" style={{ color: "var(--on-bg)" }}>Company Allowance Catalogue</div>
        <p className="text-[12px] mt-1 mb-0" style={{ color: "var(--outline)" }}>
          Add company allowance options here, then configure their calculation in each salary structure.
          Deactivating an option prevents new structure components; existing structures and payroll history are unchanged.
        </p>
      </div>

      {(error || errorMessage) && (
        <div className="mx-5 mt-4 alert alert-error">{errorMessage || error}</div>
      )}
      {successMessage && (
        <div className="mx-5 mt-4 alert alert-success">{successMessage}</div>
      )}

      {canCreate && (
        <form onSubmit={addAllowance} className="px-5 py-5 border-b border-[var(--outline-v)]">
          <div className="text-[12px] font-bold uppercase tracking-wider mb-3" style={{ color: "var(--on-variant)" }}>
            Add allowance
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex-1 min-w-[220px]">
              <span className="block text-[12px] font-semibold mb-1" style={{ color: "var(--on-bg)" }}>Allowance name</span>
              <input
                value={name}
                onChange={event => setName(event.target.value)}
                maxLength={100}
                required
                placeholder="e.g. Internet Allowance"
                className="w-full rounded-lg border border-[var(--outline-v)] text-sm px-3 py-2"
              />
            </label>
            <label className="flex items-center gap-2 text-[12px]" style={{ color: "var(--on-bg)" }}>
              <input type="checkbox" checked={isTaxable} onChange={event => setIsTaxable(event.target.checked)} />
              Taxable by default
            </label>
            <button type="submit" disabled={saving || !name.trim()} className="btn btn-filled disabled:opacity-50">
              {saving ? "Saving…" : "Add allowance"}
            </button>
          </div>
        </form>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-[var(--bg-mid)] border-b border-[var(--outline-v)]">
              {["Allowance", "Code", "Taxable by default", "Status", ""].map(label => (
                <th key={label} className="text-left text-[11px] font-semibold uppercase tracking-wider px-5 py-3 whitespace-nowrap" style={{ color: "var(--on-variant)" }}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--outline-v)]">
            {(allowances ?? []).map(allowance => (
              <tr key={allowance.id}>
                <td className="px-5 py-3 font-semibold" style={{ color: "var(--on-bg)" }}>{allowance.name}</td>
                <td className="px-5 py-3 text-xs" style={{ color: "var(--on-variant)" }}>{allowance.code}</td>
                <td className="px-5 py-3 text-xs" style={{ color: "var(--on-variant)" }}>{allowance.is_taxable ? "Yes" : "No"}</td>
                <td className="px-5 py-3 text-xs" style={{ color: allowance.is_active ? "var(--success)" : "var(--outline)" }}>
                  {allowance.is_active ? "Available" : "Inactive"}
                </td>
                <td className="px-5 py-3 text-right">
                  {canEdit && (
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => toggleAllowance(allowance)}
                      disabled={saving}
                    >
                      {allowance.is_active ? "Deactivate" : "Activate"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {!loading && (allowances ?? []).length === 0 && (
              <tr>
                <td colSpan={5} className="px-5 py-8 text-center text-sm" style={{ color: "var(--outline)" }}>
                  No allowance options are configured.
                </td>
              </tr>
            )}
            {loading && (
              <tr><td colSpan={5} className="px-5 py-8 text-center text-sm" style={{ color: "var(--outline)" }}>Loading allowances…</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

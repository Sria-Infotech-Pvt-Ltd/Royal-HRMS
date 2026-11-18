"use client";

// Loads one page of the audit log for the chosen module, dates and actor search. Changing a filter goes back to page 1.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { AuditLogPage } from "@/types/audit";

export const AUDIT_PAGE_SIZE = 20;

export interface AuditFilters { module: string; search: string; dateFrom: string; dateTo: string }

export function useAuditLog(initial: AuditFilters) {
  const [filters, setFilters] = useState<AuditFilters>(initial);
  const [page, setPage] = useState(1);

  const params = new URLSearchParams({ page: String(page), page_size: String(AUDIT_PAGE_SIZE) });
  if (filters.module) params.set("module", filters.module);
  if (filters.search) params.set("search", filters.search);
  if (filters.dateFrom) params.set("date_from", filters.dateFrom);
  if (filters.dateTo) params.set("date_to", filters.dateTo);

  const { data, loading, error } = useFetch<AuditLogPage>(`${API.settings.audit}?${params.toString()}`);

  function applyFilters(change: Partial<AuditFilters>) {
    setFilters(previous => ({ ...previous, ...change }));
    setPage(1);
  }

  return { filters, applyFilters, page, setPage, data, loading, error };
}

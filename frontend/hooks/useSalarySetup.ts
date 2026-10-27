"use client";

// Salary Setup data: one server-paginated, searchable list of employees WITH their salary record, plus the KPI summary.
// Both are re-read after every save, so a row never keeps showing "Not set" for a salary that was just saved.

import { useCallback, useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { SalarySetupFilter, SalarySetupPage, SalarySetupSummary } from "@/types/salarySetup";

export const SALARY_SETUP_PAGE_SIZE = 20;
const SEARCH_DELAY_MS = 300;

export interface SalarySavePayload {
  employee: string;
  annual_ctc: string;
  effective_from: string;
  salary_structure: string | null;
}

export function useSalarySetup() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState<SalarySetupFilter>("all");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => { setDebouncedSearch(search.trim()); setPage(1); }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [search]);

  const query = new URLSearchParams({ page: String(page), page_size: String(SALARY_SETUP_PAGE_SIZE), status });
  if (debouncedSearch) query.set("search", debouncedSearch);
  const list = useFetch<SalarySetupPage>(`${API.payroll.salarySetup}?${query.toString()}`);
  const summary = useFetch<SalarySetupSummary>(API.payroll.salarySetupSummary);
  const { refetch: refetchList } = list;
  const { refetch: refetchSummary } = summary;

  const changeStatus = useCallback((value: SalarySetupFilter) => { setStatus(value); setPage(1); }, []);

  /** Saves a salary; resolves to the server's message (and whether nothing changed). Throws with a readable message. */
  const save = useCallback(async (payload: SalarySavePayload): Promise<{ message: string; isUnchanged: boolean }> => {
    const response = await clientApi.post<{ message?: string; data?: { unchanged?: boolean } }>(API.payroll.employeeSalary, payload);
    refetchList();
    refetchSummary();
    return { message: response.data.message ?? "Salary saved.", isUnchanged: !!response.data.data?.unchanged };
  }, [refetchList, refetchSummary]);

  return { list, summary, search, setSearch, status, changeStatus, page, setPage, save };
}

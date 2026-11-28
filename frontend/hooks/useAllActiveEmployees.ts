"use client";

// Every active employee the signed-in person may see. The employee list returns at most 50 rows a page to someone without
// employees.export, so asking for one big page silently cut the list short. The first page comes through useFetch and says
// how many pages there are; the rest are then fetched in parallel, a few at a time, instead of one after another.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { ApiEmployee } from "@/app/dashboard/employees/[id]/_apiMapping";

// The largest page the employee list gives to everyone (LIST_MAX_PAGE_SIZE on the server).
const PAGE_SIZE = 50;
// How many of the remaining pages are requested at the same time, so a large company does not fire dozens at once.
const PARALLEL_PAGES = 4;

interface EmployeePage { results: ApiEmployee[]; page: number; total_pages: number }

const pageUrl = (page: number) => `${API.employees.list}?page_size=${PAGE_SIZE}&status=active&page=${page}`;

async function fetchPages(pageNumbers: number[]): Promise<ApiEmployee[]> {
  const rows: ApiEmployee[] = [];
  for (let start = 0; start < pageNumbers.length; start += PARALLEL_PAGES) {
    const batch = pageNumbers.slice(start, start + PARALLEL_PAGES);
    const responses = await Promise.all(batch.map(page => clientApi.get<{ data: EmployeePage }>(pageUrl(page))));
    for (const response of responses) rows.push(...response.data.data.results);
  }
  return rows;
}

export function useAllActiveEmployees() {
  const { data: firstPage, loading, error, refetch } = useFetch<EmployeePage>(pageUrl(1));
  // The rows of pages 2..N, tagged with the first-page response they belong to, so a reload never mixes old and new rows.
  const [rest, setRest] = useState<{ source: EmployeePage; rows: ApiEmployee[] } | null>(null);
  const [restError, setRestError] = useState<string | null>(null);

  useEffect(() => {
    if (!firstPage || firstPage.total_pages <= 1) return;
    let isCurrent = true;
    const remaining = Array.from({ length: firstPage.total_pages - 1 }, (_, index) => index + 2);
    fetchPages(remaining)
      .then(rows => { if (isCurrent) { setRest({ source: firstPage, rows }); setRestError(null); } })
      .catch(() => { if (isCurrent) setRestError("Could not load every employee. Please try again."); });
    return () => { isCurrent = false; };
  }, [firstPage]);

  const hasMorePages = !!firstPage && firstPage.total_pages > 1;
  const isRestLoaded = !hasMorePages || rest?.source === firstPage;
  const employees = useMemo(
    () => (firstPage ? [...firstPage.results, ...(hasMorePages && rest?.source === firstPage ? rest.rows : [])] : []),
    [firstPage, hasMorePages, rest],
  );
  const combinedError = error ?? restError;
  const isLoading = !combinedError && (loading || !firstPage || !isRestLoaded);

  // Start again from the first page, e.g. after a move changed people's units.
  const reload = useCallback(() => { setRestError(null); refetch(); }, [refetch]);

  return { employees, isLoading, error: combinedError, reload };
}

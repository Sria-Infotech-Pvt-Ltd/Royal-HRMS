"use client";

// The Settings > Permissions employee list: who holds how many permissions, with search and filters.

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { EmployeeAccessRow } from "@/types/orgStructure";

export type AccessFilter = "" | "extra" | "superuser" | "no_seat";

interface ListResponse {
  count: number;
  page: number;
  total_pages: number;
  results: EmployeeAccessRow[];
}

interface BranchOption { id: number; branch_name: string }

const SEARCH_DELAY_MS = 300;
const PAGE_SIZE = 20;

export function useEmployeeAccessList() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [branch, setBranch] = useState("");
  const [access, setAccess] = useState<AccessFilter>("");
  const [page, setPage] = useState(1);

  useEffect(() => {
    const timer = setTimeout(() => { setDebouncedSearch(search.trim()); setPage(1); }, SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [search]);

  const query = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
  if (debouncedSearch) query.set("search", debouncedSearch);
  if (branch) query.set("branch", branch);
  if (access) query.set("access", access);

  const list = useFetch<ListResponse>(`${API.access.employeeList}?${query.toString()}`);
  const branches = useFetch<BranchOption[] | { results: BranchOption[] }>(`${API.branches.list}?page_size=100`, { cache: true });
  const branchOptions = Array.isArray(branches.data) ? branches.data : (branches.data?.results ?? []);

  return {
    list, branchOptions,
    filters: { search, branch, access, page },
    setSearch,
    setBranch: (value: string) => { setBranch(value); setPage(1); },
    setAccess: (value: AccessFilter) => { setAccess(value); setPage(1); },
    setPage,
  };
}

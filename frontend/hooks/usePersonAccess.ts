"use client";

// Search for an employee, load what they can do, and save the extra permissions granted to them personally.

import { useCallback, useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import type { EmployeeAccess } from "@/types/orgStructure";

export interface PersonSearchResult {
  uuid: string;
  employee_id: string;
  full_name: string;
  designation?: string;
}

interface SearchResponse { results: PersonSearchResult[] }

const SEARCH_DELAY_MS = 300;
const MIN_SEARCH_LENGTH = 2;

export function usePersonSearch(term: string) {
  const [debounced, setDebounced] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(term.trim()), SEARCH_DELAY_MS);
    return () => clearTimeout(timer);
  }, [term]);

  const isSearching = debounced.length >= MIN_SEARCH_LENGTH;
  const url = isSearching ? `${API.employees.list}?search=${encodeURIComponent(debounced)}&page_size=8` : null;
  const { data, loading, error } = useFetch<SearchResponse>(url);
  return { results: isSearching ? (data?.results ?? []) : [], loading, error, isSearching };
}

export function usePersonAccess(employeeUuid: string | null) {
  const { data, loading, error, refetch } = useFetch<EmployeeAccess>(
    employeeUuid ? API.access.employeePermissions(employeeUuid) : null,
  );
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const saveExtra = useCallback(async (codenames: string[]): Promise<boolean> => {
    if (!employeeUuid) return false;
    setIsSaving(true);
    setSaveError(null);
    try {
      await clientApi.put(API.access.employeePermissions(employeeUuid), { codenames });
      refetch();
      return true;
    } catch (err: unknown) {
      setSaveError((err as { message?: string })?.message ?? "Could not save.");
      return false;
    } finally {
      setIsSaving(false);
    }
  }, [employeeUuid, refetch]);

  return { access: data, loading, error, isSaving, saveError, saveExtra };
}

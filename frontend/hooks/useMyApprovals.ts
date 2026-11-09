"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { ApprovalChain } from "@/types/approvers";

/** The signed-in employee's own reporting manager and approvers (read-only on the server). */
export function useMyApprovals() {
  const { data, loading, error } = useFetch<ApprovalChain>(API.employees.myApprovals);
  return { chain: data, loading, error };
}

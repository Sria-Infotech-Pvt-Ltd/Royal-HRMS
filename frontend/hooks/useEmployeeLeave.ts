"use client";

import { useEffect, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { useFiscalYearConfig } from "@/lib/fiscalYear";
import type { LeaveRequest, PaginatedResponse, BalanceSummary } from "@/app/dashboard/leave/_data";

export interface EmployeeLeaveStats {
  total:        number;
  approved:     number;
  pending:      number;
  rejected:     number;
  cancelled:    number;
  lop_days:     number;
  lop_requests: number;
  year:         number;
  balances:     BalanceSummary[];
}

export function useEmployeeLeave(employeeId: string) {
  const fy = useFiscalYearConfig();
  const [year, setYear] = useState(fy.currentYear);
  const [yearNavigated, setYearNavigated] = useState(false);
  const [page, setPage] = useState(1);

  // Seed from the configured FY once it resolves — but stop the moment the
  // caller has navigated years themselves, same as the year picker in
  // CreditTab.tsx.
  useEffect(() => {
    if (!yearNavigated) setYear(fy.currentYear);
  }, [fy.currentYear, yearNavigated]);

  const empParam    = `employee_id=${encodeURIComponent(employeeId)}`;
  const requestsUrl = `${API.leave.requests}?${empParam}&year=${year}&page=${page}`;
  const statsUrl    = `${API.leave.stats}?${empParam}&year=${year}`;

  const {
    data: requests, loading: requestsLoading, error: requestsError, refetch: refetchRequests,
  } = useFetch<PaginatedResponse<LeaveRequest>>(requestsUrl);

  const {
    data: stats, loading: statsLoading, error: statsError, refetch: refetchStats,
  } = useFetch<EmployeeLeaveStats>(statsUrl);

  function refetch() {
    refetchRequests();
    refetchStats();
  }

  function prevYear() { setYearNavigated(true); setPage(1); setYear(y => y - 1); }
  function nextYear() { setYearNavigated(true); setPage(1); setYear(y => y + 1); }

  return {
    year,
    prevYear,
    nextYear,
    page,
    setPage,
    totalPages: requests?.total_pages ?? 1,
    requests:   requests?.results ?? [],
    stats,
    loading: requestsLoading || statsLoading,
    error:   requestsError ?? statsError ?? null,
    refetch,
  };
}

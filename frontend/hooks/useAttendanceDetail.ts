"use client";

// Everything the Attendance Detail panel needs for one employee-day: the record, that day's correction requests, and the audit history.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { AttendanceAuditEntry, AttendanceDetail, CorrectionRow, PaginatedCorrections } from "@/types/attendance";

export function useAttendanceDetail(recordId: string, date: string) {
  const record = useFetch<AttendanceDetail>(`${API.attendance.record(recordId)}?date=${date}`);

  const correctionsUrl = record.data ? `${API.attendance.corrections}?employee_id=${record.data.employee_id}&date=${date}` : null;
  const correctionsFetch = useFetch<PaginatedCorrections>(correctionsUrl);
  const corrections: CorrectionRow[] = (correctionsFetch.data?.results ?? []).filter(
    correction => correction.employee_id === record.data?.employee_id && correction.date === date,
  );

  const auditFetch = useFetch<AttendanceAuditEntry[]>(API.attendance.recordAudit(recordId));
  const auditEntries = (auditFetch.data ?? []).slice().sort((a, b) => b.performed_at.localeCompare(a.performed_at));

  return {
    record: record.data, loading: record.loading, error: record.error, refetch: record.refetch,
    corrections, refetchCorrections: correctionsFetch.refetch,
    auditEntries, auditLoading: auditFetch.loading, auditError: auditFetch.error,
  };
}

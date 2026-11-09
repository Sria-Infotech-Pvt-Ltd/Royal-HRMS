"use client";

import { useCallback, useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { downloadBlob, filenameFromDisposition } from "@/lib/downloadBlob";
import { withQuery } from "@/lib/reportQuery";
import type { ReportCatalog, ReportFilterValues, ReportPreview, ReportRecipient } from "@/types/reports";

/** The reports this person may run (the server lists only those their permissions allow). */
export function useReportCatalog() {
  return useFetch<ReportCatalog>(API.dashboard.reports);
}

/** The first rows and the row count for a report with the current filters. */
export function useReportPreview(key: string, filters: ReportFilterValues, isEnabled: boolean) {
  return useFetch<ReportPreview>(isEnabled ? withQuery(API.dashboard.reportPreview(key), filters) : null);
}

/** Active employees matching what the sender typed, after a short pause so every keystroke is not a request. */
export function useRecipientSearch(term: string) {
  const [debounced, setDebounced] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(term.trim()), 250);
    return () => clearTimeout(timer);
  }, [term]);
  const { data, loading } = useFetch<{ results: ReportRecipient[] }>(
    debounced.length >= 2 ? `${API.dashboard.reportRecipients}?q=${encodeURIComponent(debounced)}` : null,
  );
  return { results: debounced.length >= 2 ? data?.results ?? [] : [], loading };
}

function messageOf(err: unknown, fallback: string): string {
  return (err as { response?: { data?: { message?: string } }; message?: string })?.response?.data?.message
    ?? (err as { message?: string })?.message ?? fallback;
}

/** Download and email actions for one report. Both run on the server, in the signed-in person's own scope. */
export function useReportActions(key: string, filters: ReportFilterValues) {
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState("");

  const download = useCallback(async (): Promise<boolean> => {
    setIsBusy(true);
    setError("");
    try {
      const response = await clientApi.get<Blob>(withQuery(API.dashboard.reportDownload(key), filters), { responseType: "blob" });
      const header = response.headers["content-disposition"] as string | undefined;
      downloadBlob(response.data, filenameFromDisposition(header, `${key}-report.csv`));
      return true;
    } catch (err: unknown) {
      setError(messageOf(err, "Could not download this report."));
      return false;
    } finally {
      setIsBusy(false);
    }
  }, [key, filters]);

  const send = useCallback(async (recipients: string[], note: string): Promise<string | null> => {
    setIsBusy(true);
    setError("");
    try {
      const response = await clientApi.post<{ message: string }>(API.dashboard.reportSend(key), { filters, recipients, note });
      return response.data.message;
    } catch (err: unknown) {
      setError(messageOf(err, "Could not send this report."));
      return null;
    } finally {
      setIsBusy(false);
    }
  }, [key, filters]);

  return { download, send, isBusy, error, clearError: () => setError("") };
}

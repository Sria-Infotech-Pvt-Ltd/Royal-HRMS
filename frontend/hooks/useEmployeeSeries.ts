"use client";

// The Employee ID ranges and everything being edited in them. Each worker type keeps its own draft (what was typed, its errors, whether
// it is saving), so one type saves without disturbing another's unsaved edit, and "Save all" saves every changed type one after another.

import { useCallback, useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { validateSeries, type NumberDraft, type NumericField, type RowErrors, type SeriesRow } from "@/app/dashboard/settings/employee-code/_components/employeeCodeView";

export interface SeriesDraft {
  text: Record<NumericField, string>;
  form: NumberDraft;
  errors: RowErrors;
  saving: boolean;
  saved: boolean;
  apiError: string | null;
}

const FIELDS: NumericField[] = ["range_start", "range_end", "next_sequence"];

const draftOf = (row: SeriesRow): SeriesDraft => ({
  text: { range_start: String(row.range_start), range_end: String(row.range_end), next_sequence: String(row.next_sequence) },
  form: { range_start: row.range_start, range_end: row.range_end, next_sequence: row.next_sequence },
  errors: {}, saving: false, saved: false, apiError: null,
});

export const isDraftDirty = (row: SeriesRow, draft: SeriesDraft | undefined): boolean => Boolean(draft) && FIELDS.some(field => draft!.text[field] !== String(row[field]));

export function useEmployeeSeries() {
  const { data: fetched, error: loadError } = useFetch<SeriesRow[]>(API.settings.employeeCodeSeries);
  const [rows, setRows] = useState<SeriesRow[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, SeriesDraft>>({});
  const latest = useRef({ rows, drafts });
  useEffect(() => { latest.current = { rows, drafts }; });

  useEffect(() => {
    if (!fetched) return;
    setRows(fetched);
    setDrafts(Object.fromEntries(fetched.map(row => [row.employment_type, draftOf(row)])));
  }, [fetched]);

  const patch = useCallback((type: string, change: (draft: SeriesDraft) => SeriesDraft) => {
    setDrafts(previous => previous[type] ? { ...previous, [type]: change(previous[type]) } : previous);
  }, []);

  const setField = useCallback((type: string, key: NumericField, value: string) => {
    // A number box tied straight to a number snaps back to "0" while it is cleared and retyped, so the typed text is kept apart from the
    // parsed numbers; only a fully numeric value updates the numbers that checking and saving use.
    patch(type, draft => ({
      ...draft, saved: false, apiError: null, errors: { ...draft.errors, [key]: undefined },
      text: { ...draft.text, [key]: value },
      form: /^\d+$/.test(value) ? { ...draft.form, [key]: Number(value) } : draft.form,
    }));
  }, [patch]);

  const reset = useCallback((type: string) => {
    const row = latest.current.rows?.find(entry => entry.employment_type === type);
    if (row) patch(type, () => draftOf(row));
  }, [patch]);

  const save = useCallback(async (type: string): Promise<boolean> => {
    const draft = latest.current.drafts[type];
    if (!draft) return false;
    const problems = validateSeries(draft.text, draft.form);
    if (Object.keys(problems).length > 0) { patch(type, current => ({ ...current, errors: problems })); return false; }
    patch(type, current => ({ ...current, saving: true, apiError: null, errors: {} }));
    try {
      const { data } = await clientApi.put<{ data: SeriesRow }>(
        API.settings.employeeCodeSeriesDetail(type),
        { range_start: draft.form.range_start, range_end: draft.form.range_end, next_sequence: draft.form.next_sequence },
      );
      setRows(previous => previous?.map(row => row.employment_type === type ? data.data : row) ?? previous);
      patch(type, () => ({ ...draftOf(data.data), saved: true }));
      return true;
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { data?: RowErrors; message?: string } } };
      const fieldErrors = apiErr?.response?.data?.data;
      patch(type, current => ({ ...current, saving: false, errors: fieldErrors ?? current.errors, apiError: fieldErrors ? null : (apiErr?.response?.data?.message ?? "Failed to save.") }));
      return false;
    }
  }, [patch]);

  const dirtyTypes = (rows ?? []).filter(row => isDraftDirty(row, drafts[row.employment_type])).map(row => row.employment_type);

  const saveAll = useCallback(async () => {
    const { rows: current, drafts: currentDrafts } = latest.current;
    for (const row of current ?? []) {
      if (isDraftDirty(row, currentDrafts[row.employment_type])) await save(row.employment_type);
    }
  }, [save]);

  const resetAll = useCallback(() => { setDrafts(Object.fromEntries((latest.current.rows ?? []).map(row => [row.employment_type, draftOf(row)]))); }, []);

  return { rows, loadError, drafts, dirtyTypes, setField, reset, save, saveAll, resetAll };
}

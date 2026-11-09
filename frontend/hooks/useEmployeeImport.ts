"use client";

import { useCallback, useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import { validateImportFile } from "@/lib/employeeImport";
import type { ImportCommitResult, ImportInviteProgress, ImportPreview, ImportStep } from "@/types/employeeImport";

interface Envelope<T> { status: string; message: string; data: T }
interface ApiFailure { response?: { status?: number; data?: { message?: string } } }

const UPLOAD_TIMEOUT_MS = 120_000;
const INVITE_POLL_MS = 3_000;

function failureMessage(err: unknown, fallback: string): string {
  const failure = err as ApiFailure;
  return failure.response?.data?.message || fallback;
}

function buildForm(file: File, extra: Record<string, string> = {}): FormData {
  const form = new FormData();
  form.append("file", file, file.name);
  Object.entries(extra).forEach(([key, value]) => form.append(key, value));
  return form;
}

/** State and calls for the guided employee import: template -> upload -> preview -> confirm -> result. */
export function useEmployeeImport(onCreated: () => void) {
  const [step, setStep] = useState<ImportStep>("start");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [result, setResult] = useState<ImportCommitResult | null>(null);
  const [progress, setProgress] = useState<ImportInviteProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);

  const chooseFile = useCallback((picked: File | null) => {
    setPreview(null);
    setResult(null);
    setStep("start");
    const problem = picked ? validateImportFile(picked) : null;
    setFile(problem ? null : picked);
    setError(problem);
  }, []);

  // Activation emails are sent in the background; follow them until every one is sent or failed.
  const batchId = result?.batch_id ?? null;
  const isSending = step === "done" && !result?.already_committed && progress?.state !== "done";
  useEffect(() => {
    if (!batchId || !isSending) return undefined;
    let isCancelled = false;
    async function poll() {
      try {
        const response = await clientApi.get<Envelope<ImportInviteProgress>>(API.employees.importInvites(batchId as string));
        if (!isCancelled) setProgress(response.data.data);
      } catch {
        // A missed poll is harmless: the next one tries again.
      }
    }
    void poll();
    const timer = setInterval(poll, INVITE_POLL_MS);
    return () => { isCancelled = true; clearInterval(timer); };
  }, [batchId, isSending]);

  const downloadTemplate = useCallback(async () => {
    setError(null);
    const outcome = await downloadBlobFile(API.employees.importTemplate, {}, "employee_import_template.xlsx");
    if (!outcome.success) setError(outcome.message ?? "Could not download the template.");
  }, []);

  const runPreview = useCallback(async () => {
    if (!file) { setError("Choose the filled template first."); return; }
    setIsBusy(true);
    setError(null);
    try {
      const response = await clientApi.post<Envelope<ImportPreview>>(API.employees.importPreview, buildForm(file), { timeout: UPLOAD_TIMEOUT_MS });
      setPreview(response.data.data);
      setStep("previewed");
    } catch (err: unknown) {
      setError(failureMessage(err, "The file could not be checked. Nothing was imported."));
    } finally {
      setIsBusy(false);
    }
  }, [file]);

  const downloadErrors = useCallback(async () => {
    if (!file) return;
    setError(null);
    try {
      const response = await clientApi.post(API.employees.importErrors, buildForm(file), { responseType: "blob", timeout: UPLOAD_TIMEOUT_MS });
      const url = URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement("a");
      link.href = url;
      link.download = "employee_import_errors.xlsx";
      link.click();
      URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(failureMessage(err, "Could not create the error file."));
    }
  }, [file]);

  const confirmImport = useCallback(async () => {
    if (!file || !preview || !preview.can_import) return;
    setIsBusy(true);
    setError(null);
    try {
      const form = buildForm(file, { batch_id: preview.batch_id, file_hash: preview.file_hash });
      const response = await clientApi.post<Envelope<ImportCommitResult>>(API.employees.importCommit, form, { timeout: UPLOAD_TIMEOUT_MS });
      setResult(response.data.data);
      setStep("done");
      onCreated();
    } catch (err: unknown) {
      const failure = err as ApiFailure;
      // No answer from the server: the outcome is unknown, and pressing Confirm again is safe (same batch id).
      setError(failure.response?.status
        ? failureMessage(err, "The import was rejected. Nothing was created.")
        : "The connection was lost, so the outcome is unknown. Press Confirm again: this import cannot be applied twice.");
    } finally {
      setIsBusy(false);
    }
  }, [file, preview, onCreated]);

  return { step, file, preview, result, progress, error, isBusy, chooseFile, downloadTemplate, runPreview, downloadErrors, confirmImport };
}

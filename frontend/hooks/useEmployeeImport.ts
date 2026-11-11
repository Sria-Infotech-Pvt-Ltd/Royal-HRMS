"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import clientApi, { isSessionKnownExpired } from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { downloadBlobFile } from "@/lib/downloadFile";
import { POLL_ACTIVE_MS, emailsInFlight, pollDelayMs, validateImportFile } from "@/lib/employeeImport";
import type { ImportJobProgress, ImportPreview, ImportStep } from "@/types/employeeImport";

interface Envelope<T> { status: string; message: string; data: T }
interface ApiFailure { response?: { status?: number; data?: { message?: string } } }

const UPLOAD_TIMEOUT_MS = 120_000;
const RESTORE_WINDOW_MS = 30 * 60 * 1000;

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

/** Reopening the window picks an import back up while it is running, or while its emails are still being sent (recently finished). */
function shouldRestore(job: ImportJobProgress): boolean {
  if (job.is_active) return true;
  const finished = job.finished_at ? Date.parse(job.finished_at) : 0;
  return emailsInFlight(job) > 0 && !job.invitations.held && Date.now() - finished < RESTORE_WINDOW_MS;
}

/**
 * State and calls for the guided employee import: template -> upload -> preview -> confirm -> background job.
 * Confirm only creates the job (the server answers at once); the page then follows the job's progress. Closing the window does not
 * stop it, and reopening restores it.
 */
export function useEmployeeImport(onCreated: () => void) {
  const [step, setStep] = useState<ImportStep>("start");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [job, setJob] = useState<ImportJobProgress | null>(null);
  const [recent, setRecent] = useState<ImportJobProgress[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isBusy, setIsBusy] = useState(false);
  const [isActing, setIsActing] = useState(false);
  const [pollNonce, setPollNonce] = useState(0);
  const notifiedFor = useRef<string | null>(null);

  const chooseFile = useCallback((picked: File | null) => {
    setPreview(null);
    setStep("start");
    const problem = picked ? validateImportFile(picked) : null;
    setFile(problem ? null : picked);
    setError(problem);
  }, []);

  const restartPolling = useCallback(() => setPollNonce(value => value + 1), []);

  // On open: list recent imports, and go straight back to one that is still running.
  const loadRecent = useCallback(async (restore: boolean) => {
    try {
      const response = await clientApi.get<Envelope<{ jobs: ImportJobProgress[] }>>(API.employees.importJobs);
      const jobs = response.data.data.jobs;
      setRecent(jobs);
      const resumable = restore ? jobs.find(shouldRestore) : undefined;
      if (resumable) {
        if (!resumable.is_active) notifiedFor.current = resumable.job_id;
        setJob(resumable);
        setStep("job");
      }
    } catch {
      // The list is a convenience: the import flow works without it.
    }
  }, []);
  useEffect(() => { void loadRecent(true); }, [loadRecent]);

  // Follow the job: quickly while employees are created, slowly while only emails remain, not at all once settled.
  const jobId = job?.job_id ?? null;
  useEffect(() => {
    if (step !== "job" || !jobId) return undefined;
    let isStopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const schedule = (delay: number | null) => {
      if (isStopped || delay === null || isSessionKnownExpired()) return;
      timer = setTimeout(() => { void tick(); }, delay);
    };
    async function tick() {
      try {
        const response = await clientApi.get<Envelope<ImportJobProgress>>(API.employees.importJob(jobId as string));
        if (isStopped) return;
        setJob(response.data.data);
        schedule(pollDelayMs(response.data.data));
      } catch {
        schedule(POLL_ACTIVE_MS); // a missed poll is harmless: ask again
      }
    }
    void tick();
    return () => { isStopped = true; if (timer) clearTimeout(timer); };
  }, [step, jobId, pollNonce]);

  // Tell the page (to refresh its employee list) once, when a job has finished.
  useEffect(() => {
    if (!job || job.is_active || notifiedFor.current === job.job_id) return;
    notifiedFor.current = job.job_id;
    if (job.created > 0) onCreated();
  }, [job, onCreated]);

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
      const response = await clientApi.post<Envelope<ImportJobProgress>>(API.employees.importJobs, form, { timeout: UPLOAD_TIMEOUT_MS });
      setJob(response.data.data);
      setStep("job");
    } catch (err: unknown) {
      const failure = err as ApiFailure;
      // No answer from the server: the outcome is unknown, and pressing Confirm again is safe (same batch id returns the same job).
      setError(failure.response?.status
        ? failureMessage(err, "The import was rejected. Nothing was created.")
        : "The connection was lost, so the outcome is unknown. Press Confirm again: this import cannot be applied twice.");
    } finally {
      setIsBusy(false);
    }
  }, [file, preview]);

  const openJob = useCallback(async (id: string) => {
    setError(null);
    try {
      const response = await clientApi.get<Envelope<ImportJobProgress>>(API.employees.importJob(id));
      if (!response.data.data.is_active) notifiedFor.current = id;
      setJob(response.data.data);
      setStep("job");
    } catch (err: unknown) {
      setError(failureMessage(err, "Could not open that import."));
    }
  }, []);

  const startNew = useCallback(() => {
    setJob(null);
    setFile(null);
    setPreview(null);
    setError(null);
    setStep("start");
    void loadRecent(false);
  }, [loadRecent]);

  const cancelJob = useCallback(async () => {
    if (!job) return;
    setIsActing(true);
    setError(null);
    try {
      const response = await clientApi.post<Envelope<ImportJobProgress>>(API.employees.importJobCancel(job.job_id));
      setJob(response.data.data);
      restartPolling();
    } catch (err: unknown) {
      setError(failureMessage(err, "Could not cancel the import."));
    } finally {
      setIsActing(false);
    }
  }, [job, restartPolling]);

  // Re-queues only the FAILED emails of this import. No employee is created and no second open invitation is made.
  const retryEmails = useCallback(async () => {
    if (!job) return;
    setIsActing(true);
    setError(null);
    try {
      await clientApi.post(API.employees.importInvitesRetry(job.job_id));
      const response = await clientApi.get<Envelope<ImportJobProgress>>(API.employees.importJob(job.job_id));
      setJob(response.data.data);
      restartPolling();
    } catch (err: unknown) {
      setError(failureMessage(err, "Could not retry the failed emails."));
    } finally {
      setIsActing(false);
    }
  }, [job, restartPolling]);

  const downloadJobErrors = useCallback(async () => {
    if (!job) return;
    setError(null);
    const outcome = await downloadBlobFile(API.employees.importJobErrors(job.job_id), {}, "employee_import_errors.xlsx");
    if (!outcome.success) setError(outcome.message ?? "Could not download the error report.");
  }, [job]);

  return {
    step, file, preview, job, recent, error, isBusy, isActing,
    chooseFile, downloadTemplate, runPreview, downloadErrors, confirmImport, openJob, startNew, cancelJob, retryEmails, downloadJobErrors,
  };
}

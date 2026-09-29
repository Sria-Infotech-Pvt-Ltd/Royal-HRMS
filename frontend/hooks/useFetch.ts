import { useState, useEffect, useCallback, useRef } from "react";
import clientApi from "@/lib/clientApi";

interface FetchState<T> {
  data:    T | null;
  loading: boolean;
  error:   string | null;
  // HTTP status of the last failed request, or null if it hasn't failed
  // (or succeeded). Lets consumers distinguish "genuinely empty" from
  // e.g. a 403 permission gate, which look identical if you only check
  // whether `data` is empty.
  status:  number | null;
  refetch: () => void;
}

export interface UseFetchOptions {
  // When true, a successful response for this exact URL is kept in a small
  // in-memory (module-level, per browser tab) cache and reused instead of
  // re-hitting the API the next time a useFetch(url, { cache: true }) call
  // mounts for the same URL — e.g. the Hire wizard's Employment step
  // re-fetching the same 7 lookup endpoints (roles/branches/positions/etc.)
  // every time that step is reopened within one wizard session (QA #67).
  // Off by default so every other existing useFetch() call keeps its
  // current always-refetch behavior unchanged.
  cache?:    boolean;
  // How long a cached entry stays fresh before a mount triggers a real
  // refetch again. Default 5 minutes — long enough to cover flipping
  // between wizard steps, short enough that stale lookup data (e.g. a
  // newly added Role) doesn't linger for an entire session.
  cacheTtlMs?: number;
}

const DEFAULT_CACHE_TTL_MS = 5 * 60 * 1000;

// Module-level so it survives remounts of the component (reopening a wizard
// step) but not a full page reload — matches "within the same wizard
// session" from QA #67, not a permanent cross-session cache.
const responseCache = new Map<string, { data: unknown; expiresAt: number }>();

export function useFetch<T>(url: string | null, options?: UseFetchOptions): FetchState<T> {
  const useCache = options?.cache ?? false;
  const cacheTtlMs = options?.cacheTtlMs ?? DEFAULT_CACHE_TTL_MS;

  const cached = useCache && url ? responseCache.get(url) : undefined;
  const hasFreshCache = !!cached && cached.expiresAt > Date.now();

  const [data,    setData]    = useState<T | null>(hasFreshCache ? (cached!.data as T) : null);
  const [loading, setLoading] = useState<boolean>(!!url && !hasFreshCache);
  const [error,   setError]   = useState<string | null>(null);
  const [status,  setStatus]  = useState<number | null>(null);
  const counter = useRef(0);

  const run = useCallback((opts?: { bypassCache?: boolean }) => {
    if (!url) { setData(null); setLoading(false); setError(null); setStatus(null); return; }

    if (useCache && !opts?.bypassCache) {
      const entry = responseCache.get(url);
      if (entry && entry.expiresAt > Date.now()) {
        setData(entry.data as T);
        setError(null);
        setStatus(null);
        setLoading(false);
        return;
      }
    }

    const ticket = ++counter.current;
    setLoading(true);
    setError(null);
    setStatus(null);
    clientApi
      .get<{ data: T }>(url)
      .then(r => {
        if (ticket !== counter.current) return;
        // Unwrap the {success, message, data} envelope by checking for the
        // "data" key's presence, not its truthiness — a `?? fallback` here
        // would treat a legitimate `data: null` (e.g. "nothing configured
        // yet") as absent and fall back to the whole envelope object,
        // which is truthy and has none of T's real fields.
        const body = r.data as unknown;
        const hasEnvelope = body !== null && typeof body === "object" && "data" in body;
        const resolved = hasEnvelope ? (body as { data: T }).data : (body as T);
        setData(resolved);
        setError(null);
        if (useCache) {
          responseCache.set(url, { data: resolved, expiresAt: Date.now() + cacheTtlMs });
        }
      })
      .catch((err: unknown) => {
        if (ticket !== counter.current) return;
        const msg =
          (err as { response?: { data?: { message?: string } } })
            ?.response?.data?.message ?? "Request failed.";
        setError(msg);
        setStatus((err as { status?: number })?.status ?? null);
      })
      .finally(() => {
        if (ticket === counter.current) setLoading(false);
      });
  }, [url, useCache, cacheTtlMs]);

  useEffect(() => { run(); }, [run]);

  // refetch() always bypasses the cache and hits the API — a consumer that
  // explicitly asks to refetch means "get me the latest", not "give me back
  // what I already have cached".
  const refetch = useCallback(() => run({ bypassCache: true }), [run]);

  return { data, loading, error, status, refetch };
}

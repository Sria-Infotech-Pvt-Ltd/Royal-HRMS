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

export function useFetch<T>(url: string | null): FetchState<T> {
  const [data,    setData]    = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(!!url);
  const [error,   setError]   = useState<string | null>(null);
  const [status,  setStatus]  = useState<number | null>(null);
  const counter = useRef(0);

  const run = useCallback(() => {
    if (!url) { setData(null); setLoading(false); setError(null); setStatus(null); return; }
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
        setData(hasEnvelope ? (body as { data: T }).data : (body as T));
        setError(null);
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
  }, [url]);

  useEffect(() => { run(); }, [run]);

  return { data, loading, error, status, refetch: run };
}

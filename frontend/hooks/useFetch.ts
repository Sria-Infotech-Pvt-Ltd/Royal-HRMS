import { useState, useEffect, useCallback, useRef } from "react";
import clientApi from "@/lib/clientApi";

interface FetchState<T> {
  data:    T | null;
  loading: boolean;
  error:   string | null;
  refetch: () => void;
}

export function useFetch<T>(url: string | null): FetchState<T> {
  const [data,    setData]    = useState<T | null>(null);
  const [loading, setLoading] = useState<boolean>(!!url);
  const [error,   setError]   = useState<string | null>(null);
  const counter = useRef(0);

  const run = useCallback(() => {
    if (!url) { setData(null); setLoading(false); setError(null); return; }
    const ticket = ++counter.current;
    setLoading(true);
    setError(null);
    clientApi
      .get<{ data: T }>(url)
      .then(r => {
        if (ticket !== counter.current) return;
        setData(r.data?.data ?? (r.data as T));
        setError(null);
      })
      .catch((err: unknown) => {
        if (ticket !== counter.current) return;
        const msg =
          (err as { response?: { data?: { message?: string } } })
            ?.response?.data?.message ?? "Request failed.";
        setError(msg);
      })
      .finally(() => {
        if (ticket === counter.current) setLoading(false);
      });
  }, [url]);

  useEffect(() => { run(); }, [run]);

  return { data, loading, error, refetch: run };
}

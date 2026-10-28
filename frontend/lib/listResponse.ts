// A list endpoint answers either with a plain array or with a paged { results: [...] } body; callers should not guess which.

export function rowsOf<T>(payload: unknown): T[] {
  if (Array.isArray(payload)) return payload as T[]; // the API contract: a list endpoint's data is an array of T
  if (typeof payload === "object" && payload !== null && Array.isArray((payload as { results?: unknown }).results)) {
    return (payload as { results: T[] }).results; // the same contract, paged
  }
  return [];
}

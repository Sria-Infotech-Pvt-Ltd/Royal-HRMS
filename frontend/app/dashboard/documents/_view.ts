// Pure helpers for the Document Center list: sorting and the "new" marker.
import type { ApiDocument } from "./_data";

export type DocSort = "newest" | "oldest" | "name" | "size";

export const SORT_OPTIONS: { value: DocSort; label: string }[] = [
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "name",   label: "Name (A–Z)"  },
  { value: "size",   label: "Largest first" },
];

const NEW_WITHIN_DAYS = 7;
const MS_PER_DAY = 86_400_000;

export function sortDocuments(documents: ApiDocument[], sort: DocSort): ApiDocument[] {
  const copy = [...documents];
  const time = (doc: ApiDocument) => new Date(doc.uploaded_at).getTime() || 0;
  if (sort === "oldest") copy.sort((a, b) => time(a) - time(b));
  else if (sort === "name") copy.sort((a, b) => a.title.localeCompare(b.title));
  else if (sort === "size") copy.sort((a, b) => b.file_size - a.file_size);
  else copy.sort((a, b) => time(b) - time(a));
  return copy;
}

/** True for a document uploaded within the last week. */
export function isNewDocument(doc: ApiDocument, now: number = Date.now()): boolean {
  const uploaded = new Date(doc.uploaded_at).getTime();
  return Number.isFinite(uploaded) && now - uploaded >= 0 && now - uploaded <= NEW_WITHIN_DAYS * MS_PER_DAY;
}

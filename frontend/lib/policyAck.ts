// Company Policy acknowledgement — what the Document Center shows for a
// document, and the counts on the HR acknowledgement report.

export interface AckFields {
  requires_acknowledgement?: boolean;
  version?: number;
  my_acknowledged_at?: string | null;
}

export type AckState = "not_required" | "pending" | "acknowledged";

export function ackState(doc: AckFields): AckState {
  if (!doc.requires_acknowledgement) return "not_required";
  return doc.my_acknowledged_at ? "acknowledged" : "pending";
}

export interface AckReportRow {
  employee_id: string;
  name: string;
  branch: string;
  department: string;
  acknowledged_at: string | null;
}

export function filterAckRows(rows: AckReportRow[], show: "all" | "pending" | "acknowledged"): AckReportRow[] {
  if (show === "pending") return rows.filter(r => !r.acknowledged_at);
  if (show === "acknowledged") return rows.filter(r => !!r.acknowledged_at);
  return rows;
}

/** "Policies" tab when the page is opened as /dashboard/documents?category=policy. */
export function initialDocFilter<T extends string>(category: string | null, map: Record<T, string>, fallback: T): T {
  if (!category) return fallback;
  const hit = (Object.keys(map) as T[]).find(k => map[k] === category);
  return hit ?? fallback;
}

import { formatDate } from "@/lib/formatDate";
import type { PersonnelActionRequest } from "@/types/personnelAction";

export function personnelValuesSummary(r: PersonnelActionRequest): string {
  const labels: Record<string, string> = {
    position: "Position", annual_ctc: "Annual CTC", reporting_manager: "Reporting manager",
    work_location: "Work location", employment_status: "Status",
  };
  return Object.entries(r.after).map(([key, value]) => {
    const before = r.before[key as keyof typeof r.before] ?? "—";
    const fmt = (v: string) => (key === "annual_ctc" && /^\d/.test(v) ? `₹${Number(v).toLocaleString("en-IN")}` : v);
    return `${labels[key] ?? key}: ${fmt(before)} → ${fmt(value ?? "—")}`;
  }).join(" · ");
}

export function personnelEffective(iso: string): string {
  return formatDate(iso) || "—";
}

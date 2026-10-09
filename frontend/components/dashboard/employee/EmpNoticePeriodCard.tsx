"use client";

import Link from "next/link";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { formatNoticeDate, noticeRemainingLabel } from "@/lib/noticePeriod";
import type { EmployeeNoticePeriod } from "@/types/dashboard";

// Renders only for the logged-in employee's own fully approved separation.
export default function EmpNoticePeriodCard() {
  const { data: response } = useFetch<{ notice_period: EmployeeNoticePeriod | null }>(API.employeeDashboard.noticePeriod);
  const data = response?.notice_period;
  if (!data) return null;

  const completed = data.notice_status === "completed";
  return (
    <div className="card mb-20">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-hourglass" /> Notice Period</div>
        <span className={`badge ${completed ? "badge-success" : "badge-warn"}`}>
          {completed ? "Completed" : "Serving notice"}
        </span>
      </div>
      <div className="card-body" style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 24 }}>
        <div>
          <div style={{ fontSize: 28, fontWeight: 700, color: completed ? "var(--success)" : "var(--error)", lineHeight: 1.1 }}>
            {completed ? "Done" : data.days_remaining}
          </div>
          <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
            {noticeRemainingLabel(data.days_remaining, data.notice_status)}
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "auto auto", columnGap: 16, rowGap: 4, fontSize: 12 }}>
          <span style={{ color: "var(--on-variant)" }}>Approved on</span>
          <span style={{ fontWeight: 600 }}>{formatNoticeDate(data.approved_at)}</span>
          <span style={{ color: "var(--on-variant)" }}>Last working day</span>
          <span style={{ fontWeight: 600 }}>{formatNoticeDate(data.confirmed_last_working_day)}</span>
          <span style={{ color: "var(--on-variant)" }}>Type</span>
          <span style={{ fontWeight: 600 }}>{data.separation_type}</span>
        </div>
        <Link href={`/dashboard/separation/${data.request_id}`} className="btn btn-ghost btn-sm" style={{ marginLeft: "auto" }}>
          View details
        </Link>
      </div>
    </div>
  );
}

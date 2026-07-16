"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { HRBirthdayEmployee } from "@/types/dashboard";

function initials(name: string): string {
  return name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2);
}

export default function HrBirthdaysWidget() {
  const { data: todayList, loading: loadingToday }       = useFetch<HRBirthdayEmployee[]>(API.dashboard.hrBirthdaysToday);
  const { data: upcomingList, loading: loadingUpcoming } = useFetch<HRBirthdayEmployee[]>(API.dashboard.hrBirthdaysUpcoming);

  const today    = Array.isArray(todayList)    ? todayList    : [];
  const upcoming = Array.isArray(upcomingList) ? upcomingList : [];
  const loading  = loadingToday || loadingUpcoming;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-cake" /> Birthdays</div>
        {!loading && today.length > 0 && (
          <span className="badge badge-success">{today.length} today</span>
        )}
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : (
        <div style={{ padding: "8px 0" }}>
          {today.length > 0 && (
            <>
              <div style={{ padding: "2px 20px 6px", fontSize: 10, fontWeight: 700, letterSpacing: "0.07em", textTransform: "uppercase", color: "var(--on-variant)" }}>Today</div>
              {today.map(emp => (
                <div key={emp.employee_id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 20px", background: "rgba(22,163,74,0.05)" }}>
                  <div style={{ width: 32, height: 32, borderRadius: "50%", flexShrink: 0, background: "#16a34a", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700 }}>
                    {initials(emp.full_name)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{emp.full_name}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{emp.department}{emp.branch ? ` · ${emp.branch}` : ""}</div>
                  </div>
                  <span style={{ fontSize: 16 }}>🎂</span>
                </div>
              ))}
            </>
          )}

          {upcoming.length > 0 && (
            <>
              <div style={{ padding: "8px 20px 4px", fontSize: 10, fontWeight: 700, letterSpacing: "0.07em", textTransform: "uppercase", color: "var(--on-variant)", borderTop: today.length > 0 ? "1px solid var(--border)" : undefined, marginTop: today.length > 0 ? 4 : 0 }}>
                Upcoming
              </div>
              {upcoming.map(emp => (
                <div key={emp.employee_id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "7px 20px" }}>
                  <div style={{ width: 32, height: 32, borderRadius: "50%", flexShrink: 0, background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700 }}>
                    {initials(emp.full_name)}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{emp.full_name}</div>
                    <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{emp.department}</div>
                  </div>
                  <span style={{ fontSize: 11, color: "var(--on-variant)", whiteSpace: "nowrap" }}>
                    in {emp.days_until} day{emp.days_until !== 1 ? "s" : ""}
                  </span>
                </div>
              ))}
            </>
          )}

          {today.length === 0 && upcoming.length === 0 && (
            <div style={{ padding: "24px 20px", textAlign: "center" }}>
              <i className="ti ti-cake" style={{ fontSize: 28, opacity: 0.25, display: "block", marginBottom: 8, color: "var(--on-variant)" }} />
              <div style={{ fontSize: 13, color: "var(--on-variant)" }}>No birthdays soon</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

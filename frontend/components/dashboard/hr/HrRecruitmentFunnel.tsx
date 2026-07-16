"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { RecruitmentFunnel } from "@/types/dashboard";

const STAGES: { key: keyof RecruitmentFunnel; label: string; icon: string }[] = [
  { key: "interviews_scheduled", label: "Scheduled",        icon: "ti-calendar-event" },
  { key: "interviewed",          label: "Interviewed",      icon: "ti-microphone"     },
  { key: "selected",             label: "Selected",         icon: "ti-circle-check"   },
  { key: "details_submitted",    label: "Details Submitted",icon: "ti-file-check"     },
  { key: "onboarded",            label: "Onboarded",        icon: "ti-user-check"     },
];

export default function HrRecruitmentFunnel() {
  const { data, loading } = useFetch<RecruitmentFunnel>(API.dashboard.hrRecruitmentFunnel);

  const maxVal = data
    ? Math.max(...STAGES.map(s => data[s.key] ?? 0), 1)
    : 1;

  return (
    <div className="card">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-filter" /> Recruitment Funnel</div>
      </div>

      {loading ? (
        <div style={{ padding: "24px 20px", display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
        </div>
      ) : (
        <div style={{ padding: "12px 20px 16px" }}>
          {STAGES.map((stage, index) => {
            const val = data?.[stage.key] ?? 0;
            const pct = maxVal > 0 ? (val / maxVal) * 100 : 0;
            const opacity = 1 - index * 0.12;
            const color = `rgba(37,99,235,${opacity})`;
            return (
              <div key={stage.key} style={{ marginBottom: 10 }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <i className={`ti ${stage.icon}`} style={{ fontSize: 13, color: "var(--on-variant)", width: 16 }} />
                    <span style={{ fontSize: 12, fontWeight: 500, color: "var(--on-bg)" }}>{stage.label}</span>
                  </div>
                  <span style={{ fontSize: 13, fontWeight: 700, color: "var(--on-bg)", minWidth: 24, textAlign: "right" }}>{val}</span>
                </div>
                <div style={{ height: 6, borderRadius: 4, background: "var(--bg-high)", overflow: "hidden" }}>
                  <div style={{
                    height: "100%",
                    width: `${pct}%`,
                    background: color,
                    borderRadius: 4,
                    transition: "width 0.4s ease",
                  }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

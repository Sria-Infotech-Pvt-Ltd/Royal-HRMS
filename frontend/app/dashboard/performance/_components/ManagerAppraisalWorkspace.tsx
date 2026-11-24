"use client";

// Performance, as a Reporting Manager sees it: the "Appraisal review
// workspace" from the artifact. Lists every direct report's appraisal for the
// active cycle with the stage it is at; the ones waiting on this manager are
// highlighted and open straight into the assessment dialog.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useT } from "@/hooks/useI18n";
import { API } from "@/lib/api/endpoints";
import { formatDate } from "@/lib/formatDate";
import { KpiTile, OverviewRow } from "@/components/dashboard/ModuleOverviewKit";
import { managerStageLabel, type TeamReview } from "@/types/appraisal";
import TeamReviewModal from "./TeamReviewModal";

// Chips needing the manager's attention are amber; everything else is neutral/green.
const CHIP_TONE: Record<TeamReview["status"], "warn" | "success"> = {
  not_started: "warn", returned: "warn", self_review: "warn", hr_calibration: "success", published: "success", completed: "success",
};

export default function ManagerAppraisalWorkspace() {
  const t = useT();
  const { data, loading, error, refetch } = useFetch<TeamReview[]>(API.performance.teamReviews);
  const [openId, setOpenId] = useState<string | null>(null);

  const reviews = data ?? [];
  const open = reviews.find(r => r.id === openId) ?? null;
  const waiting = reviews.filter(r => r.status === "self_review").length;
  const selfDone = reviews.filter(r => r.self_submitted_at || r.manager_submitted_at).length;
  const mgrDone = reviews.filter(r => r.manager_submitted_at).length;
  const cycle = reviews[0];

  return (
    <div className="plain-stack">
      <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 8 }}>{t("Dashboard / Performance")}</div>
      <div className="pagehead">
        <div>
          <h1>{t("Appraisal")} <em>{t("review workspace")}</em></h1>
          <p className="lede">{t("Assess your team's self-reviews, return them for changes, or send them to HR for calibration.")}</p>
        </div>
      </div>

      <div className="stats">
        <KpiTile label={t("ACTIVE CYCLE")} value={cycle?.cycle_name ?? "—"} sub={cycle?.cycle_manager_review_due ? t("Manager reviews due {date}", { date: formatDate(cycle.cycle_manager_review_due) }) : t("No active cycle")} tone="brand" />
        <KpiTile label={t("WAITING FOR YOU")} value={waiting} sub={t("Self-review submitted")} tone="warn" />
        <KpiTile label={t("SELF REVIEWS")} value={`${selfDone} / ${reviews.length}`} sub={t("Submitted by your team")} tone="ok" />
        <KpiTile label={t("SENT TO HR")} value={`${mgrDone} / ${reviews.length}`} sub={t("Your assessments")} tone="ok" />
      </div>

      <section className="module-card">
        <h2>{t("Your team's appraisals")}</h2>
        <p>{cycle ? t("{name} · one review per direct report.", { name: cycle.cycle_name }) : t("Reviews appear here once HR opens a cycle.")}</p>

        {error && <div className="alert alert-error mb-16">{error}</div>}
        {loading ? (
          <p className="hint">{t("Loading…")}</p>
        ) : reviews.length === 0 ? (
          <div className="empty-state"><i className="ti ti-users" /><h3>{t("No reviews to show")}</h3>
            <p>{t("Either there is no active review cycle, or nobody currently reports to you.")}</p></div>
        ) : (
          <div className="module-list">
            {reviews.map(r => (
              <OverviewRow
                key={r.id}
                label={r.employee_name}
                sub={`${r.employee_code}${r.manager_next_checkin ? ` · ${t("next check-in {date}", { date: formatDate(r.manager_next_checkin) })}` : ""}`}
                chip={managerStageLabel(r.status)}
                chipTone={CHIP_TONE[r.status]}
                onOpen={() => setOpenId(r.id)}
              />
            ))}
          </div>
        )}
      </section>

      {open && <TeamReviewModal review={open} onClose={() => setOpenId(null)} onChanged={refetch} />}
    </div>
  );
}

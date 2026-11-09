"use client";

import styles from "./hrHome.module.css";
import { countOrDash, relativeTime, totalPending, type PendingRequestRow } from "@/lib/hrHome";
import type { PipelineCounts } from "@/hooks/useHrHomeData";
import type { Notification } from "@/types/notifications";

const ROW_ICONS: Record<string, string> = {
  face: "ti-face-id", leave: "ti-calendar-off", wfh: "ti-home-2", expense: "ti-receipt", other: "ti-file-description",
};

interface PendingProps {
  rows: PendingRequestRow[];
  isLoading: boolean;
  onOpen: () => void;
}

export function HrPendingRequestsCard({ rows, isLoading, onOpen }: PendingProps) {
  const total = totalPending(rows);
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}><i className="ti ti-inbox" /> My Pending Requests{rows.length > 0 && !isLoading ? ` (${total})` : ""}</h2>
        <button type="button" className={styles.viewAll} onClick={onOpen}>View All →</button>
      </div>
      {isLoading && <div className={styles.emptyFill}>Loading…</div>}
      {!isLoading && rows.length === 0 && <div className={styles.emptyFill}>No approval workflows are assigned to you.</div>}
      {!isLoading && rows.map(row => (
        <button key={row.key} type="button" className={styles.row} onClick={onOpen}>
          <span className={styles.rowLeft}>
            <span className={styles.rowIcon}><i className={`ti ${ROW_ICONS[row.key] ?? "ti-file"}`} /></span>
            <span>
              <div className={styles.rowLabel}>{row.label}</div>
              <div className={styles.rowSub}>{row.sub}</div>
            </span>
          </span>
          <span className={`${styles.badge} ${row.count === 0 ? styles.badgeZero : ""}`}>{row.count}</span>
        </button>
      ))}
    </section>
  );
}

interface PipelineProps {
  pipeline: PipelineCounts;
  onOpen: () => void;
}

export function HrPipelineCard({ pipeline, onOpen }: PipelineProps) {
  const stages = [
    { key: "positions", label: "Open Positions", icon: "ti-briefcase", value: null, tone: styles.stageViolet },
    { key: "applications", label: "Applications", icon: "ti-users", value: pipeline.applications, tone: styles.stageBlue },
    { key: "screening", label: "Screening", icon: "ti-search", value: pipeline.screening, tone: styles.stageGreen },
    { key: "interviews", label: "Interviews", icon: "ti-calendar-event", value: pipeline.interviews, tone: styles.stageAmber },
    { key: "offer", label: "Offer Stage", icon: "ti-file-certificate", value: pipeline.offerStage, tone: styles.stageOrange },
  ];
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}><i className="ti ti-filter" /> Recruitment Pipeline</h2>
        <button type="button" className={styles.viewAll} onClick={onOpen}>View All →</button>
      </div>
      {stages.map(stage => (
        <div key={stage.key} className={`${styles.stage} ${stage.tone}`} title={stage.value === null ? "No data source for this figure yet" : undefined}>
          <span><i className={`ti ${stage.icon}`} />{stage.label}</span>
          <span className={styles.stageValue}>{countOrDash(stage.value)}</span>
        </div>
      ))}
    </section>
  );
}

interface ActivityProps {
  activities: Notification[];
  now: Date | null;
  isLoading: boolean;
}

/** The person's own latest notifications, which is where approvals and requests addressed to them are announced. */
export function HrRecentActivitiesCard({ activities, now, isLoading }: ActivityProps) {
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}><i className="ti ti-history" /> Recent Activities</h2>
      </div>
      {isLoading && <div className={styles.emptyFill}>Loading…</div>}
      {!isLoading && activities.length === 0 && <div className={styles.emptyFill}>No recent activity.</div>}
      {!isLoading && activities.map(activity => (
        <div key={activity.id} className={styles.activity}>
          <span className={styles.rowIcon}><i className="ti ti-user" /></span>
          <div>
            <div className={styles.activityText}><strong>{activity.title}</strong>{activity.message ? ` — ${activity.message}` : ""}</div>
            <div className={styles.activityTime}>{now ? relativeTime(activity.created_at, now) : ""}</div>
          </div>
        </div>
      ))}
    </section>
  );
}

interface ComplianceProps {
  attendanceExceptions: number | null;
  onOpenAttendance: () => void;
}

/** Document verifications and policy acknowledgements have no count source yet, so they show a dash. */
export function HrTeamComplianceCard({ attendanceExceptions, onOpenAttendance }: ComplianceProps) {
  const rows = [
    { key: "exceptions", label: "Attendance Exceptions", icon: "ti-alert-triangle", value: attendanceExceptions, onClick: onOpenAttendance },
    { key: "documents", label: "Document Verifications", icon: "ti-file-check", value: null, onClick: undefined },
    { key: "policies", label: "Policy Acknowledgements", icon: "ti-shield-check", value: null, onClick: undefined },
  ];
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}><i className="ti ti-shield-check" /> Team &amp; Compliance</h2>
      </div>
      {rows.map(row => (
        <button key={row.key} type="button" className={styles.row} onClick={row.onClick} disabled={!row.onClick}
          title={row.value === null && !row.onClick ? "No data source for this figure yet" : undefined}>
          <span className={styles.rowLeft}>
            <span className={styles.rowIcon}><i className={`ti ${row.icon}`} /></span>
            <span className={styles.rowLabel}>{row.label}</span>
          </span>
          <span className={`${styles.badge} ${styles.badgeWarn}`}>{countOrDash(row.value)}</span>
        </button>
      ))}
    </section>
  );
}

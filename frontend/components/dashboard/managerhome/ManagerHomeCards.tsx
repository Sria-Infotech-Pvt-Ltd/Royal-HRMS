"use client";

import styles from "@/components/dashboard/hrhome/hrHome.module.css";
import { countOrDash, relativeTime } from "@/lib/hrHome";
import { donutArcs, totalTeamPending, type TeamApprovalRow, type TeamBreakdown } from "@/lib/managerHome";
import { KIND_LABELS } from "@/lib/approvalOverview";
import type { ApprovalKind } from "@/app/dashboard/approvals/_data";
import type { ManagerActivityEntry } from "@/types/managerDashboard";

const RADIUS = 62;

interface OverviewProps {
  breakdown: TeamBreakdown;
  isLoading: boolean;
  onOpenTeam: (() => void) | null;
}

/** Today's team split, from each direct report's attendance status. WFH has no figure: the attendance status does not carry it. */
export function TeamOverviewCard({ breakdown, isLoading, onOpenTeam }: OverviewProps) {
  const arcs = donutArcs(breakdown, RADIUS);
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}><i className="ti ti-chart-donut" /> Team Overview</h2>
        {onOpenTeam && <button type="button" className={styles.viewAll} onClick={onOpenTeam}>View Team →</button>}
      </div>
      {isLoading ? <div className={styles.emptyFill}>Loading…</div> : (
        <div className={styles.donutWrap}>
          <div className={styles.donut}>
            <svg viewBox="0 0 160 160" width="168" height="168" role="img" aria-label="Team attendance today">
              <circle cx="80" cy="80" r={RADIUS} fill="none" stroke="rgba(124,58,237,0.08)" strokeWidth="18" />
              {arcs.map(arc => (
                <circle key={arc.key} cx="80" cy="80" r={RADIUS} fill="none" stroke={arc.color} strokeWidth="18"
                  strokeDasharray={arc.dash} strokeDashoffset={arc.offset} transform="rotate(-90 80 80)" />
              ))}
            </svg>
            <div className={styles.donutCentre}>
              <div className={styles.donutTotal}>{breakdown.total}</div>
              <div className={styles.donutCaption}>Team<br />Members</div>
            </div>
          </div>
          <div className={styles.legend}>
            {arcs.map(arc => (
              <div key={arc.key} className={styles.legendRow}>
                <span><span className={styles.legendDot} style={{ background: arc.color }} />{arc.label}</span>
                <span className={styles.legendValue}>{countOrDash(arc.value)}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

const ROW_ICONS: Record<string, string> = {
  leave: "ti-beach", wfh: "ti-home-2", expense: "ti-receipt", attendance_correction: "ti-clock-edit", separation: "ti-user-minus",
};

interface ApprovalsProps {
  rows: TeamApprovalRow[];
  isLoading: boolean;
  onOpen: () => void;
}

export function PendingTeamApprovalsCard({ rows, isLoading, onOpen }: ApprovalsProps) {
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}><i className="ti ti-inbox" /> Pending Team Approvals{rows.length > 0 && !isLoading ? ` (${totalTeamPending(rows)})` : ""}</h2>
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
          <span className={`${styles.badge} ${row.count === 0 ? styles.badgeZero : styles.badgeWarn}`}>{row.count}</span>
        </button>
      ))}
    </section>
  );
}

interface ActivityProps {
  activity: ManagerActivityEntry[];
  now: Date | null;
  isLoading: boolean;
}

/** What the manager's direct reports have done recently, from the audit trail the manager endpoint already returns. */
export function RecentTeamActivityCard({ activity, now, isLoading }: ActivityProps) {
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}><i className="ti ti-history" /> Recent Team Activity</h2>
      </div>
      {isLoading && <div className={styles.emptyFill}>Loading…</div>}
      {!isLoading && activity.length === 0 && <div className={styles.emptyFill}>No recent team activity.</div>}
      {!isLoading && activity.slice(0, 4).map((entry, index) => (
        <div key={`${entry.employee_id}-${entry.created_at}-${index}`} className={styles.activity}>
          <span className={styles.rowIcon}><i className="ti ti-user" /></span>
          <div>
            <div className={styles.activityText}><strong>{entry.employee_name || entry.employee_id}</strong> — {entry.description}</div>
            <div className={styles.activityTime}>{now ? relativeTime(entry.created_at, now) : ""}</div>
          </div>
        </div>
      ))}
    </section>
  );
}

interface MonthProps {
  counts: Record<ApprovalKind, number>;
  kinds: ApprovalKind[];
}

const TONES = [styles.stageViolet, styles.stageBlue, styles.stageAmber, styles.stageGreen, styles.stageOrange];

/** Requests submitted this month that are still waiting on this manager (the lists only hold what is waiting for them). */
export function TeamRequestsMonthCard({ counts, kinds }: MonthProps) {
  return (
    <section className={styles.card}>
      <div className={styles.cardHead}>
        <h2 className={styles.cardTitle}><i className="ti ti-calendar-stats" /> Team Requests (This Month)</h2>
      </div>
      <p style={{ margin: "0 0 10px", fontSize: 12, color: "var(--on-variant)" }}>Submitted this month and still waiting for your decision.</p>
      {kinds.length === 0 && <div className={styles.emptyFill}>No approval workflows are assigned to you.</div>}
      {kinds.map((kind, index) => (
        <div key={kind} className={`${styles.stage} ${TONES[index % TONES.length]}`}>
          <span>{KIND_LABELS[kind]}</span>
          <span className={styles.stageValue}>{counts[kind]}</span>
        </div>
      ))}
    </section>
  );
}

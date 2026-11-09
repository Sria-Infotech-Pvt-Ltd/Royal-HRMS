"use client";

import styles from "./hrHome.module.css";
import { countOrDash, greetingFor, initialsOf } from "@/lib/hrHome";
import type { DashboardOverview } from "@/types/dashboard";
import type { PipelineCounts } from "@/hooks/useHrHomeData";

interface BannerProps {
  /** The screen's title; the HR dashboard's by default. The Manager dashboard shares this banner. */
  title?: string;
  name: string;
  designation: string;
  /** Null until mounted, so the greeting is not computed on the server (it would not match the browser's clock). */
  now: Date | null;
  onOpenWorkspace: () => void;
}

export function HrHomeBanner({ title = "HR Dashboard", name, designation, now, onOpenWorkspace }: BannerProps) {
  const firstName = name.trim().split(/\s+/)[0] ?? "";
  return (
    <section className={styles.banner}>
      <div className={styles.bannerLeft}>
        <div className={styles.avatar} aria-hidden="true">{initialsOf(name)}</div>
        <div>
          <h1 className={styles.bannerTitle}>{title}</h1>
          <p className={styles.bannerSub}>
            {now ? `${greetingFor(now.getHours())}, ${firstName}` : firstName}
            {designation && <><span>|</span>{designation}</>}
          </p>
        </div>
      </div>
      <button type="button" className={styles.bannerButton} onClick={onOpenWorkspace}>
        <i className="ti ti-user" /> My Workspace <i className="ti ti-arrow-right" />
      </button>
    </section>
  );
}

interface TilesProps {
  overview: DashboardOverview | null;
  pendingApprovals: number | null;
  pipeline: PipelineCounts;
  isLoading: boolean;
}

export interface StatTile {
  key: string;
  label: string;
  icon: string;
  value: number | null;
  sub?: string;
  subGood?: boolean;
}

/** A row of stat tiles. A tile whose value is null shows a dash: a figure with no data source is never invented. */
export function StatTiles({ tiles, isLoading }: { tiles: StatTile[]; isLoading: boolean }) {
  return (
    <div className={styles.tiles}>
      {tiles.map(tile => (
        <div key={tile.key} className={styles.tile}>
          <div className={styles.tileIcon}><i className={`ti ${tile.icon}`} /></div>
          <div style={{ minWidth: 0 }}>
            <div className={styles.tileLabel}>{tile.label}</div>
            <div className={styles.tileValue}>{isLoading && tile.value === null ? "…" : countOrDash(tile.value)}</div>
            {tile.sub && <div className={`${styles.tileSub} ${tile.subGood ? styles.tileSubGood : ""}`}>{tile.sub}</div>}
          </div>
        </div>
      ))}
    </div>
  );
}

/** The six stat tiles. A figure with no data source (open requisitions) is a dash, not a number. */
export function HrHomeTiles({ overview, pendingApprovals, pipeline, isLoading }: TilesProps) {
  const tiles: StatTile[] = [
    {
      key: "employees", label: "Total Employees", icon: "ti-users", value: overview?.total_headcount ?? null,
      sub: overview && overview.new_this_month > 0 ? `↑ +${overview.new_this_month} this month` : undefined, subGood: true,
    },
    { key: "requests", label: "Open Requests", icon: "ti-file-text", value: overview?.open_requests ?? null },
    { key: "approvals", label: "Pending Approvals", icon: "ti-calendar-check", value: pendingApprovals },
    { key: "requisitions", label: "Open Requisitions", icon: "ti-users-group", value: null, sub: "not tracked yet" },
    { key: "interviews", label: "Active Interviews", icon: "ti-briefcase", value: pipeline.interviews },
    { key: "onboarding", label: "Onboarding", icon: "ti-calendar-event", value: overview?.onboarding_in_progress ?? null, sub: "in progress" },
  ];
  return <StatTiles tiles={tiles} isLoading={isLoading} />;
}

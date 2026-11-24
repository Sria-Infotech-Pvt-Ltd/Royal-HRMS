// Pure helpers for the Interview List: no component state, safe to import anywhere.

import { MODE_LABELS, fmtDate, type Candidate, type CandidateStatus, type RecruitmentStats } from "./_data";
import { tr } from "@/lib/i18n/tr";

export type StatusFilter = "" | CandidateStatus;

export interface StatCardSpec {
  /** The status filter this card sets when clicked ("" = everyone). */
  key:   StatusFilter;
  label: string;
  value: number | null;
  icon:  string;
  tone:  string;
  sub:   string;
}

/** "40% of all candidates", or null when there is nothing to take a share of. */
export function shareOfTotal(part: number, total: number): string | null {
  if (total <= 0) return null;
  return tr("{percent}% of all candidates", { percent: Math.round((part / total) * 100) });
}

/** The four summary cards, each with one line of context. Counts are null until the stats arrive. */
export function buildStatCards(stats: RecruitmentStats | null, branchName?: string): StatCardSpec[] {
  const total = stats?.total ?? 0;
  const share = (part: number | undefined) => (stats ? shareOfTotal(part ?? 0, total) ?? tr("No candidates yet") : tr("Loading…"));
  return [
    { key: "",         label: tr("Total"),    value: stats?.total    ?? null, icon: "ti-users",      tone: "si-primary", sub: branchName ? tr("In {branch}", { branch: branchName }) : tr("Across all company codes") },
    { key: "pending",  label: tr("Pending"),  value: stats?.pending  ?? null, icon: "ti-clock",      tone: "si-warn",    sub: share(stats?.pending) },
    { key: "selected", label: tr("Selected"), value: stats?.selected ?? null, icon: "ti-user-check", tone: "si-success",
      sub: stats && stats.pending_review > 0 ? tr("{count} awaiting HR review", { count: stats.pending_review }) : share(stats?.selected) },
    { key: "rejected", label: tr("Rejected"), value: stats?.rejected ?? null, icon: "ti-user-x",     tone: "si-error",   sub: share(stats?.rejected) },
  ];
}

/** True when something narrows the list. The company code only counts when the person is allowed to change it. */
export function hasActiveFilters(search: string, status: StatusFilter, branch: number | "", canChooseBranch: boolean): boolean {
  return search.trim() !== "" || status !== "" || (canChooseBranch && branch !== "");
}

/** "10:30" from the server's "10:30:00"; null when there is no time. */
export function fmtTime(time: string | null): string | null {
  return time ? time.slice(0, 5) : null;
}

export interface InterviewSummary {
  /** "12 Nov 2026 · 10:30", or null when no interview is scheduled. */
  when:        string | null;
  mode:        string;
  interviewer: string | null;
}

/** What to show in the Interview column. */
export function interviewSummary(candidate: Pick<Candidate, "interview_date" | "interview_time" | "interview_mode" | "interviewer_name">): InterviewSummary {
  if (!candidate.interview_date) return { when: null, mode: tr(MODE_LABELS[candidate.interview_mode]), interviewer: null };
  const time = fmtTime(candidate.interview_time);
  return {
    when:        time ? `${fmtDate(candidate.interview_date)} · ${time}` : fmtDate(candidate.interview_date),
    mode:        tr(MODE_LABELS[candidate.interview_mode]),
    interviewer: candidate.interviewer_name || null,
  };
}

/** A referred candidate whose branch or interview date has not been filled in yet needs HR to "Set Details". */
export function needsDetails(candidate: Pick<Candidate, "referral_by" | "branch" | "interview_date">): boolean {
  return candidate.referral_by !== null && (!candidate.branch || !candidate.interview_date);
}

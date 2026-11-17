"use client";

import { formatDate } from "@/lib/formatDate";
import { cycleProgress, relativeDay } from "@/lib/performanceHub";
import type { ApiCycle } from "@/types/performanceHub";

interface CycleTimelineProps {
  cycle: ApiCycle
  today: Date
}

const PHASE_TEXT = { upcoming: "Starts soon", running: "In progress", ended: "Period ended" } as const;

/** One cycle laid out along its period: today's position and the self-review and manager-review deadlines. */
export default function CycleTimeline({ cycle, today }: CycleTimelineProps) {
  const progress = cycleProgress(cycle, today);
  if (!progress) {
    return <p className="perf-muted">This cycle&apos;s dates are not set up properly, so a timeline cannot be drawn.</p>;
  }
  return (
    <div className="perf-timeline">
      <div className="perf-timeline-top">
        <span className={`badge ${progress.phase === "running" ? "badge-success" : "badge-neutral"}`}>{PHASE_TEXT[progress.phase]}</span>
        <span className="perf-muted">
          {progress.phase === "ended" ? `Ended ${relativeDay(cycle.period_end, today)}` : `${progress.daysLeft} day${progress.daysLeft === 1 ? "" : "s"} left`}
        </span>
      </div>
      <div className="perf-track" role="img" aria-label={`${Math.round(progress.percent)}% of the period has passed`}>
        <span className="perf-track-fill" style={{ width: `${progress.percent}%` }} />
        {progress.milestones.map(milestone => (
          <span key={milestone.key} className={`perf-pin ${milestone.state}`} style={{ left: `${milestone.percent}%` }} />
        ))}
        <span className="perf-today" style={{ left: `${progress.percent}%` }} title="Today" />
      </div>
      <ul className="perf-milestones">
        {progress.milestones.map(milestone => (
          <li key={milestone.key} className={milestone.state}>
            <strong>{milestone.label}</strong>
            <span>{formatDate(milestone.date)} · {relativeDay(milestone.date, today)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

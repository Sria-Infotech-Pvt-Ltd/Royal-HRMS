"use client";

import { coverageItems, coveragePercent, segmentWidth } from "@/lib/faceRegistrationStatus";
import type { FaceRosterCounts, FaceRosterFilter } from "@/types/faceRegistration";

interface FaceCoverageCardProps {
  counts:    FaceRosterCounts
  isLoading: boolean
  filter:    FaceRosterFilter
  onFilter:  (filter: FaceRosterFilter) => void
}

/** How far Face ID registration has got across all active employees, and one click to list who has not completed it. */
export default function FaceCoverageCard({ counts, isLoading, filter, onFilter }: FaceCoverageCardProps) {
  const percent = coveragePercent(counts);
  const toggle = (next: FaceRosterFilter) => onFilter(filter === next ? "" : next);
  return (
    <div className="card fid-coverage">
      <div className="fid-coverage-top">
        <div>
          <div className="fid-coverage-title">Face ID coverage</div>
          <div className="fid-coverage-figure">
            {isLoading ? "—" : <><strong>{counts.approved.toLocaleString()}</strong> of {counts.total.toLocaleString()} employees registered <span>({percent}%)</span></>}
          </div>
        </div>
        <button
          type="button"
          className={`btn btn-sm ${filter === "incomplete" ? "btn-filled" : "btn-ghost"}`}
          aria-pressed={filter === "incomplete"}
          disabled={isLoading || counts.incomplete === 0}
          onClick={() => toggle("incomplete")}
        >
          <i className="ti ti-user-exclamation" /> {counts.incomplete === 0 && !isLoading ? "Everyone is registered" : `Show ${counts.incomplete.toLocaleString()} not completed`}
        </button>
      </div>

      <div className="fid-bar" role="img" aria-label={`${percent}% registered`}>
        {coverageItems(counts).map(item => (
          <span key={item.filter} className={`fid-seg tone-${item.tone}`} style={{ width: `${segmentWidth(item.value, counts.total)}%` }} />
        ))}
      </div>

      <div className="fid-legend" role="group" aria-label="Filter employees by Face ID status">
        {coverageItems(counts).map(item => (
          <button
            key={item.filter}
            type="button"
            className={`fid-legend-item${filter === item.filter ? " on" : ""}`}
            aria-pressed={filter === item.filter}
            disabled={isLoading}
            onClick={() => toggle(item.filter)}
          >
            <i className={`fid-dot tone-${item.tone}`} /> {item.label} <strong>{isLoading ? "—" : item.value.toLocaleString()}</strong>
          </button>
        ))}
      </div>
    </div>
  );
}

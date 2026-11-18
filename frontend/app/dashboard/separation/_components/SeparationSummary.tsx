"use client";

import type { CSSProperties } from "react";
import type { SeparationCounts } from "../_view";

/** Four summary tiles for the requests on screen: everything, waiting for a decision, approved, closed. */
export default function SeparationSummary({ counts, isTeam }: { counts: SeparationCounts; isTeam: boolean }) {
  const tiles = [
    { label: "Requests",          value: counts.all,      icon: "ti-logout",         accent: "#7c3aed" },
    { label: isTeam ? "Need your decision" : "Waiting for a decision", value: isTeam ? counts.needsMe : counts.waiting, icon: "ti-hourglass", accent: "#d97706" },
    { label: "Approved",          value: counts.approved, icon: "ti-circle-check",   accent: "#16a34a" },
    { label: "Rejected / cancelled", value: counts.closed, icon: "ti-circle-x",      accent: "#6b7280" },
  ];
  return (
    <div className="sp-tiles">
      {tiles.map(tile => (
        <div key={tile.label} className="sp-tile" style={{ "--sp-accent": tile.accent } as CSSProperties}>
          <span className="sp-icon"><i className={`ti ${tile.icon}`} /></span>
          <div><b>{tile.value}</b><span className="sp-tile-label">{tile.label}</span></div>
        </div>
      ))}
    </div>
  );
}

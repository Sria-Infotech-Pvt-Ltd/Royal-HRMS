"use client";

import type { CSSProperties } from "react";
import { useT } from "@/hooks/useI18n";
import type { SeparationCounts } from "../_view";

/** Four summary tiles for the requests on screen: everything, waiting for a decision, approved, closed. */
export default function SeparationSummary({ counts, isTeam }: { counts: SeparationCounts; isTeam: boolean }) {
  const t = useT();
  const tiles = [
    { label: t("Requests"),          value: counts.all,      icon: "ti-logout",         accent: "var(--brand)" },
    { label: isTeam ? t("Need your decision") : t("Waiting for a decision"), value: isTeam ? counts.needsMe : counts.waiting, icon: "ti-hourglass", accent: "#d97706" },
    { label: t("Approved"),          value: counts.approved, icon: "ti-circle-check",   accent: "#16a34a" },
    { label: t("Rejected / cancelled"), value: counts.closed, icon: "ti-circle-x",      accent: "#6b7280" },
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

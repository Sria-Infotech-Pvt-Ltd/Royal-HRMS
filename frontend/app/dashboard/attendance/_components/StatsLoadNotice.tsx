"use client";

import { useT } from "@/hooks/useI18n";
import { describeStatsFailure } from "./statsFailure";

interface Props {
  /** HTTP status of the failed request; null when the server could not be reached. */
  status: number | null;
  onRetry: () => void;
}

// A one-line notice above the status tabs when their counts could not be loaded. Without it the tabs used to show a misleading 0.
export default function StatsLoadNotice({ status, onRetry }: Props) {
  const t = useT();
  return (
    <div role="alert" className="alert alert-error mb-16" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <i className="ti ti-alert-circle" aria-hidden="true" />
      <span style={{ flex: 1, minWidth: 200 }}>
        <b>{t("The counts could not be loaded.")}</b> {describeStatsFailure(status, t)}
      </span>
      <button type="button" className="btn btn-ghost btn-sm" onClick={onRetry}>{t("Try again")}</button>
    </div>
  );
}

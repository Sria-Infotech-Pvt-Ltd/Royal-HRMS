"use client";

// Per-row action buttons for the HR review queue table — "Review" (opens
// ReviewActionModal for the manager-review step, already existed), plus the
// two HR-only lifecycle steps that come after it: "Calibrate" (once the
// manager has submitted, before HR calibrates) and "Publish" (once HR has
// calibrated, before the outcome is published to the employee). Kept as its
// own component so _client.tsx's table cell stays a single call, matching
// the file-length rule in CLAUDE.md.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { ApiReview } from "../_client";

interface Props {
  review: ApiReview;
  onReview: (review: ApiReview) => void;
  onChanged: () => void;
}

export default function ReviewQueueRowActions({ review, onReview, onChanged }: Props) {
  const [busy, setBusy] = useState(false);

  async function handleCalibrate() {
    setBusy(true);
    try {
      await clientApi.post(API.performance.calibrateReview(review.id));
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function handlePublish() {
    setBusy(true);
    try {
      await clientApi.post(API.performance.publishReview(review.id));
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  if (review.self_submitted_at && !review.manager_submitted_at) {
    return (
      <button className="btn btn-filled btn-sm" onClick={() => onReview(review)}>
        Review
      </button>
    );
  }

  if (review.manager_submitted_at && !review.hr_calibrated_at) {
    return (
      <button className="btn btn-filled btn-sm" onClick={handleCalibrate} disabled={busy}>
        {busy ? "Calibrating…" : "Calibrate"}
      </button>
    );
  }

  if (review.hr_calibrated_at && !review.published_at) {
    return (
      <button className="btn btn-filled btn-sm" onClick={handlePublish} disabled={busy}>
        {busy ? "Publishing…" : "Publish"}
      </button>
    );
  }

  return null;
}

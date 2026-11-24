"use client";

import { useT } from "@/hooks/useI18n";

interface AnnouncementSkeletonProps {
  count?: number
}

/** Placeholder cards shown while the list loads, so the page keeps its shape instead of jumping. */
export default function AnnouncementSkeleton({ count = 3 }: AnnouncementSkeletonProps) {
  const t = useT();
  return (
    <div className="ann-skeleton" aria-busy="true" aria-label={t("Loading announcements")}>
      {Array.from({ length: count }, (_, index) => (
        <div className="ann-skel-card" key={index}>
          <div className="ann-skel-line" style={{ width: "34%", height: 14 }} />
          <div className="ann-skel-line" style={{ width: "92%" }} />
          <div className="ann-skel-line" style={{ width: "76%" }} />
          <div className="ann-skel-line" style={{ width: "22%", height: 10 }} />
        </div>
      ))}
    </div>
  )
}

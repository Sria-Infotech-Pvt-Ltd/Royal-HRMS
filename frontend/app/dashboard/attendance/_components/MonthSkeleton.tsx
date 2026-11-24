"use client";

import { useT } from "@/hooks/useI18n";

// What shows while a month loads: the shape of the page (a calendar grid and the side column) shimmering, instead of a spinner on a blank page.

const SHIMMER: React.CSSProperties = {
  background: "linear-gradient(90deg, #eceff6 25%, #f7f8fc 50%, #eceff6 75%)", backgroundSize: "300% 100%", animation: "ann-shimmer 1.4s linear infinite",
};

function Block({ height, radius = 12, width = "100%" }: { height: number; radius?: number; width?: string | number }) {
  return <div aria-hidden="true" style={{ ...SHIMMER, height, width, borderRadius: radius }} />;
}

export default function MonthSkeleton() {
  const t = useT();
  return (
    <div role="status" aria-label={t("Loading attendance")} style={{ display: "flex", gap: 18, flexWrap: "wrap", alignItems: "flex-start" }}>
      <div style={{ flex: "65 1 0%", minWidth: "min(560px, 100%)" }}>
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <Block height={38} radius={0} />
          <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 1, padding: 1 }}>
            {Array.from({ length: 35 }, (_, index) => <Block key={index} height={84} radius={0} />)}
          </div>
        </div>
      </div>
      <div style={{ flex: "35 1 0%", minWidth: "min(340px, 100%)", display: "flex", flexDirection: "column", gap: 12 }}>
        <Block height={190} radius={16} />
        <Block height={110} radius={16} />
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
          {Array.from({ length: 6 }, (_, index) => <Block key={index} height={64} radius={14} />)}
        </div>
      </div>
    </div>
  );
}

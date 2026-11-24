"use client";

// Top of the Attendance Detail panel: who, which day, and the status as a coloured pill, under a thin bar in the status colour.

import { useT } from "@/hooks/useI18n";
import type { AttendanceDetail } from "@/types/attendance";
import { statusColour, tint } from "./attendancePalette";
import { dateCaption, longDate } from "./detailView";

interface Props {
  data: AttendanceDetail;
  date: string;
  todayISO: string;
  editing: boolean;
  onEdit: () => void;
}

const initialsOf = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0].toUpperCase()).join("") || "?";

export default function DetailHeader({ data, date, todayISO, editing, onEdit }: Props) {
  const t = useT();
  const colour = statusColour(data.status_key);
  return (
    <div style={{ borderRadius: 14, border: "1px solid var(--outline-v)", overflow: "hidden", marginBottom: 14 }}>
      <div aria-hidden="true" style={{ height: 5, background: colour }} />
      <div style={{ padding: "14px 16px", display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <div aria-hidden="true" style={{ width: 44, height: 44, borderRadius: "50%", background: tint(colour, 0.14), color: colour, fontWeight: 800, display: "grid", placeItems: "center", flexShrink: 0 }}>{initialsOf(data.name)}</div>
        <div style={{ flex: "1 1 180px", minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 16, color: "var(--on-bg)" }}>{data.name}</div>
          <div style={{ fontSize: 12.5, color: "var(--on-variant)", marginTop: 1 }}>{[data.employee_id, data.department, data.branch].filter(Boolean).join(" · ")}</div>
        </div>
        <span style={{ fontSize: 12.5, fontWeight: 700, padding: "4px 12px", borderRadius: 999, background: colour, color: "#fff" }}>{data.status}</span>
        {!editing && <button className="btn btn-ghost btn-sm" onClick={onEdit}><i className="ti ti-edit" /> {t("Edit")}</button>}
      </div>
      <div style={{ padding: "10px 16px", background: "var(--bg-low)", borderTop: "1px solid var(--outline-v)", display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
        <i className="ti ti-calendar-event" aria-hidden="true" style={{ color: "var(--primary)" }} />
        <span style={{ fontWeight: 600, color: "var(--on-bg)" }}>{longDate(date)}</span>
        <span style={{ color: "var(--on-variant)" }}>· {dateCaption(date, todayISO).split(" · ")[1]}</span>
      </div>
    </div>
  );
}

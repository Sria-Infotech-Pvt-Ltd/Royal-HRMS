import { formatNoticeDate, noticeRemainingLabel, type NoticeStatus } from "@/lib/noticePeriod";

interface Props {
  fullName:       string;
  employeeId?:    string;
  department?:    string;
  branch?:        string;
  approvedAt?:    string | null;
  lastWorkingDay?: string;
  daysRemaining?: number;
  noticeStatus?:  NoticeStatus;
}

export default function NoticePeriodRow({
  fullName, employeeId, department, branch, approvedAt, lastWorkingDay, daysRemaining, noticeStatus,
}: Props) {
  const initials = fullName.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2) || "?";
  const meta = [employeeId, department, branch].filter(Boolean).join(" · ");
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 20px", borderBottom: "1px solid var(--bg-high)" }}>
      <div style={{
        width: 32, height: 32, borderRadius: "50%", flexShrink: 0,
        background: "var(--primary)", color: "#fff",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 11, fontWeight: 700,
      }}>
        {initials}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{fullName}</div>
        <div style={{ fontSize: 11, color: "var(--on-variant)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{meta || "—"}</div>
        <div style={{ fontSize: 10, color: "var(--on-variant)", marginTop: 1 }}>Approved {formatNoticeDate(approvedAt)}</div>
      </div>
      <div style={{ textAlign: "right", flexShrink: 0 }}>
        <div style={{ fontSize: 11, color: "var(--error)", fontWeight: 600, whiteSpace: "nowrap" }}>
          Last day: {formatNoticeDate(lastWorkingDay)}
        </div>
        <div style={{ fontSize: 10, color: "var(--on-variant)", marginTop: 1, whiteSpace: "nowrap" }}>
          {noticeRemainingLabel(daysRemaining, noticeStatus)}
        </div>
      </div>
    </div>
  );
}

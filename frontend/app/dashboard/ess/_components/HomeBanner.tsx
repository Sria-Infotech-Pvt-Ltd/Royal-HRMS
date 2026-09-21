"use client";

// Purple/gradient greeting banner for the ESS Home tab. Reuses the same
// employee profile fetch (employees/me — already used by ProfileClient and
// DashboardShell for the header avatar) and the existing ClockInButton /
// useAttendanceStatus hook so punching in here is the exact same flow as
// every other punch-in button in the app, not a new one.

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import Avatar from "@/app/dashboard/employees/_components/Avatar";
import ClockInButton from "@/components/ClockInButton";
import type { AttendanceStatus } from "@/types/employeeDashboard";

interface HomeProfile {
  full_name:         string;
  employee_id:       string;
  department:        string;
  designation:       string;
  branch:            string;
  profile_photo_url: string | null;
}

function greetingWord(hour: number): string {
  if (hour < 12) return "morning";
  if (hour < 17) return "afternoon";
  return "evening";
}

function initials(name: string): string {
  return name.split(" ").filter(Boolean).map(n => n[0]).join("").toUpperCase().slice(0, 2);
}

interface Props {
  // Real per-employee "today" state — clocked_in / clock_in_time — used in
  // place of the mockup's fixed "General shift · 09:30-18:30" text, since no
  // endpoint exposes an individual employee's assigned shift hours to ESS
  // (attendance/settings is the org-wide default and is gated behind
  // settings.view, which most employees don't hold). Passed down from
  // HomeTab so this and HomeTodayPanel share one fetch instead of two.
  status: AttendanceStatus | null;
  onPunchSuccess: () => void;
}

export default function HomeBanner({ status, onPunchSuccess }: Props) {
  const { data: profile } = useFetch<HomeProfile>(API.employees.me);

  const firstName = (profile?.full_name ?? "").split(" ")[0] || "there";
  const now = new Date();
  const greeting = `Good ${greetingWord(now.getHours())}, ${firstName}`;
  const dateLabel = now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });

  const subtitleParts = [
    profile && [profile.designation, profile.department].filter(Boolean).join(", "),
    profile?.employee_id,
    profile?.branch,
  ].filter(Boolean);

  const statusLabel = status?.clocked_in
    ? `Clocked in · ${status.clock_in_time ?? "—"}`
    : "Not clocked in yet";

  return (
    <div
      className="mb-20"
      style={{ background: "linear-gradient(135deg, var(--primary) 0%, #6d28d9 100%)", borderRadius: "var(--radius-lg)", padding: "22px 26px", position: "relative", overflow: "hidden" }}
    >
      <div style={{ position: "absolute", top: -50, right: -50, width: 180, height: 180, borderRadius: "50%", border: "1px solid rgba(255,255,255,0.06)", pointerEvents: "none" }} />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap", position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <Avatar text={initials(profile?.full_name ?? firstName)} size={52} photoUrl={profile?.profile_photo_url} />
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, color: "#fff", lineHeight: 1.25 }}>{greeting}</div>
            <div style={{ fontSize: 13, color: "rgba(255,255,255,0.72)" }}>
              {subtitleParts.length > 0 ? subtitleParts.join(" · ") : "Welcome to your workspace"}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "#fff" }}>{dateLabel}</div>
            <div style={{ fontSize: 12, color: "rgba(255,255,255,0.65)" }}>{statusLabel}</div>
          </div>
          <ClockInButton onPunchSuccess={onPunchSuccess} />
        </div>
      </div>
    </div>
  );
}

"use client";

// Purple/gradient greeting banner for the ESS Home tab. Reuses the same
// employee profile fetch (employees/me — already used by ProfileClient and
// DashboardShell for the header avatar) and the existing ClockInButton /
// useAttendanceStatus hook so punching in here is the exact same flow as
// every other punch-in button in the app, not a new one.

import { useEffect } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import Avatar from "@/app/dashboard/employees/_components/Avatar";
import ClockInButton from "@/components/ClockInButton";
import { PROFILE_PHOTO_UPDATED_EVENT } from "@/hooks/useProfilePhotoUpload";
import type { AttendanceStatus } from "@/types/employeeDashboard";

interface Shift { name: string; start_time: string; end_time: string }

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
  // Real per-employee "today" state, passed down from HomeTab so this and
  // HomeTodayPanel share one fetch instead of two.
  status: AttendanceStatus | null;
  onPunchSuccess: () => void;
}

export default function HomeBanner({ status, onPunchSuccess }: Props) {
  const { data: profile, refetch: refetchProfile } = useFetch<HomeProfile>(API.employees.me);

  useEffect(() => {
    function onPhotoUpdated() { refetchProfile(); }
    window.addEventListener(PROFILE_PHOTO_UPDATED_EVENT, onPhotoUpdated);
    return () => window.removeEventListener(PROFILE_PHOTO_UPDATED_EVENT, onPhotoUpdated);
  }, [refetchProfile]);
  // Org-wide default shift (no per-employee shift assignment exists yet —
  // see /attendance/my-shift/'s own docstring). Falls back to the real
  // clock-in status line when no default is configured, rather than a
  // fabricated shift string.
  const { data: shift } = useFetch<Shift | null>(API.attendance.myShift);

  const firstName = (profile?.full_name ?? "").split(" ")[0] || "there";
  const now = new Date();
  const greeting = `Good ${greetingWord(now.getHours())}, ${firstName}`;
  const dateLabel = now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" });

  const subtitleParts = [
    profile?.designation,
    profile?.employee_id,
    profile?.department,
  ].filter(Boolean);

  // shift is {} (not null) from the backend when no default shift is
  // configured — check for a real field, not just object truthiness.
  const statusLabel = shift?.start_time
    ? `${shift.name} · ${shift.start_time}-${shift.end_time}`
    : status?.clocked_in
      ? `Clocked in · ${status.clock_in_time ?? "—"}`
      : "Not clocked in yet";

  return (
    <div
      className="mb-16"
      style={{ background: "linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%)", borderRadius: "var(--radius-lg)", padding: "26px 30px", position: "relative", overflow: "hidden" }}
    >
      {/* Text on this card always uses var(--on-primary) rather than a literal
          white so it stays readable against the primary/secondary gradient's
          lighter dark-mode tones, not just the darker light-mode ones. */}
      <div style={{ position: "absolute", top: -50, right: -50, width: 180, height: 180, borderRadius: "50%", border: "1px solid color-mix(in srgb, var(--on-primary) 6%, transparent)", pointerEvents: "none" }} />

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap", position: "relative" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <Avatar text={initials(profile?.full_name ?? firstName)} size={60} shape="square" photoUrl={profile?.profile_photo_url} />
          <div>
            <div style={{ fontSize: 20, fontWeight: 700, color: "var(--on-primary)", lineHeight: 1.25 }}>{greeting}</div>
            <div style={{ fontSize: 13, color: "color-mix(in srgb, var(--on-primary) 72%, transparent)" }}>
              {subtitleParts.length > 0 ? subtitleParts.join(" · ") : "Welcome to your workspace"}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap" }}>
          <div style={{ textAlign: "right" }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-primary)" }}>{dateLabel}</div>
            <div style={{ fontSize: 12, color: "color-mix(in srgb, var(--on-primary) 65%, transparent)" }}>{statusLabel}</div>
          </div>
          <ClockInButton onPunchSuccess={onPunchSuccess} />
        </div>
      </div>
    </div>
  );
}

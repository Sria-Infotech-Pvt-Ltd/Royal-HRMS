"use client";

// The ESS hero — greeting, role · id · org unit, today's date + shift, and the
// single white Punch in / Punch out button (reference: .ess-hero). Reuses the
// same employee profile fetch (employees/me) and the existing ClockInButton /
// useAttendanceStatus flow, so punching here is the exact same punch (with
// geofence + face verification) as every other punch button in the app.
//
// Restored to this exact shape (not the earlier gradient/Avatar rewrite) per
// a direct reference screenshot of the Attendance tab showing precisely this
// layout — photo + greeting/subtitle on the left, date/shift + a single plain
// "Punch in" button on the right, no extra correction-request link.

import { useEffect } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import ClockInButton from "@/components/ClockInButton";
import { PROFILE_PHOTO_UPDATED_EVENT } from "@/hooks/useProfilePhotoUpload";
import type { AttendanceStatus } from "@/types/employeeDashboard";

interface Shift { name: string; start_time: string; end_time: string }

interface HomeProfile {
  full_name:         string;
  employee_id:       string;
  department:        string;
  designation:       string;
  org_unit_name?:    string | null;
  position_title?:   string | null;
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
  status: AttendanceStatus | null;
  onPunchSuccess: () => void;
  /** Someone else is looking at this workspace: no Punch in / out. */
  isReadOnly?: boolean;
}

export default function HomeBanner({ status, onPunchSuccess, isReadOnly = false }: Props) {
  const { data: profile, refetch: refetchProfile } = useFetch<HomeProfile>(API.employees.me);
  const { data: shift } = useFetch<Shift | null>(API.attendance.myShift);

  useEffect(() => {
    function onPhotoUpdated() { refetchProfile(); }
    window.addEventListener(PROFILE_PHOTO_UPDATED_EVENT, onPhotoUpdated);
    return () => window.removeEventListener(PROFILE_PHOTO_UPDATED_EVENT, onPhotoUpdated);
  }, [refetchProfile]);

  const now = new Date();
  const firstName = (profile?.full_name ?? "").split(" ")[0];
  const subtitle = [
    profile?.position_title || profile?.designation,
    profile?.employee_id,
    profile?.org_unit_name || profile?.department,
  ].filter(Boolean).join(" · ");

  // shift is {} (not null) from the backend when no default shift is
  // configured — check for a real field, not just object truthiness.
  const shiftLabel = shift?.start_time
    ? `${shift.name} · ${shift.start_time}–${shift.end_time}`
    : status?.clocked_in
      ? `Clocked in · ${status.clock_in_time ?? "—"}`
      : "Not clocked in yet";

  return (
    <section className="ess-hero">
      <div className="ess-person">
        <div
          className="ess-photo"
          aria-hidden="true"
          style={{
            backgroundImage: profile?.profile_photo_url ? `url(${profile.profile_photo_url})` : "none",
            backgroundSize: "cover", backgroundPosition: "center", backgroundColor: "rgba(255,255,255,.18)",
            display: "grid", placeItems: "center", color: "#fff", fontWeight: 800, fontSize: 20,
          }}
        >
          {!profile?.profile_photo_url && profile ? initials(profile.full_name) : null}
        </div>
        <div>
          <h1>{firstName ? `Good ${greetingWord(now.getHours())}, ${firstName}` : `Good ${greetingWord(now.getHours())}`}</h1>
          <p>{subtitle || "Welcome to your workspace"}</p>
        </div>
      </div>
      <div className="ess-clock">
        <div>
          <b>{now.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long" })}</b>
          <span>{shiftLabel}</span>
        </div>
        {!isReadOnly && <ClockInButton variant="ess" onPunchSuccess={onPunchSuccess} />}
      </div>
    </section>
  );
}

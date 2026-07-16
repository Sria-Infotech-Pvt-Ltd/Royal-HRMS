"use client";

import { useRouter } from "next/navigation";
import AttendanceSettings from "@/app/dashboard/attendance/_components/AttendanceSettings";

export default function AttendanceConfigPage() {
  const router = useRouter();

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">Attendance Rules</div>
          <div className="page-sub">Shift timings, late marks, overtime and absence alerts</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
        </div>
      </div>

      <AttendanceSettings />
    </>
  );
}

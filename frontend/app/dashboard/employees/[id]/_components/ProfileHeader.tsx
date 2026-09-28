"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { usePermission } from "@/hooks/usePermission";
import { formatDate } from "@/lib/formatDate";
import {
  experienceFrom,
  fullName,
  initials,
  avatarColor,
  type Employee,
} from "../../_data";
import Avatar from "../../_components/Avatar";
import StatusBadge from "../../_components/StatusBadge";
import ActionMenu from "./ActionMenu";

export default function ProfileHeader({
  employee,
  employeeUuid,
}: {
  employee: Employee;
  employeeUuid: string;
}) {
  const router = useRouter();
  const exp = experienceFrom(employee.dateOfJoining);
  const canResetPassword = usePermission("employees.reset_password");

  const [resetting, setResetting] = useState(false);
  const [resetMsg,  setResetMsg]  = useState<string | null>(null);
  const [resetErr,  setResetErr]  = useState<string | null>(null);

  // Only meaningful before the employee has ever set a real password —
  // invite_status comes back null once no invite token exists at all (a
  // pre-invite-flow account, or one created some other way), so the
  // badge/Resend button below simply don't render in that case either.
  const { data: invite, refetch: refetchInvite } = useFetch<{
    invite_status: "sent" | "opened" | "activated" | "expired" | null;
    invite_sent_at: string | null;
    invite_expires_at: string | null;
  }>(canResetPassword ? API.employees.inviteStatus(employeeUuid) : null);
  const [resending, setResending] = useState(false);

  async function handleResendInvite() {
    setResending(true);
    setResetMsg(null);
    setResetErr(null);
    try {
      const res = await clientApi.post(API.employees.resendInvite(employeeUuid));
      setResetMsg(res.data?.message ?? "Activation invite resent.");
      refetchInvite();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to resend invite.";
      setResetErr(msg);
    } finally {
      setResending(false);
    }
  }

  const INVITE_BADGE: Record<string, { label: string; bg: string; color: string }> = {
    sent:    { label: "Invite Sent",    bg: "var(--info-c)",    color: "var(--info)" },
    opened:  { label: "Invite Opened",  bg: "var(--warn-c)",    color: "var(--warn)" },
    expired: { label: "Invite Expired", bg: "var(--error-c)",   color: "var(--error)" },
  };

  async function handleResetPassword() {
    if (!employeeUuid) return;
    const confirmed = window.confirm(
      `Reset ${fullName(employee)}'s password? A new temporary password will be emailed to them, ` +
      `and any devices they're currently logged in on will be signed out.`,
    );
    if (!confirmed) return;

    setResetting(true);
    setResetMsg(null);
    setResetErr(null);
    try {
      const res = await clientApi.post(API.employees.resetPassword(employeeUuid));
      setResetMsg(res.data?.message ?? "Password reset successfully.");
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to reset password.";
      setResetErr(msg);
    } finally {
      setResetting(false);
    }
  }

  return (
    <div className="mb-4">
      {/* breadcrumb + title row */}
      <div className="flex items-start justify-between flex-wrap gap-3 mb-3">
        <div>
          <nav className="flex items-center gap-1 text-[12px] mb-1.5" style={{ color: "var(--on-variant)" }}>
            <Link
              href="/dashboard/employees"
              className="hover:underline transition-colors"
              style={{ color: "var(--on-variant)" }}
            >
              Employee List
            </Link>
            <i className="ti ti-chevron-right text-[11px]" style={{ color: "var(--outline)" }} />
            <span className="font-medium" style={{ color: "var(--on-bg)" }}>{employee.code}</span>
          </nav>
          <h1 className="text-[22px] font-bold tracking-tight" style={{ color: "var(--on-bg)" }}>
            Employee Profile
          </h1>
        </div>

        <div className="flex items-center gap-2">
          <ActionMenu employee={employee} />
          {canResetPassword && invite?.invite_status && invite.invite_status !== "activated" && (
            <button
              onClick={handleResendInvite}
              disabled={resending}
              suppressHydrationWarning
              title="Resend the account-activation email"
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium border transition-colors"
              style={{
                borderColor: "var(--outline-v)",
                color: "var(--on-bg)",
                background: "var(--surface)",
              }}
            >
              <i className={`ti ${resending ? "ti-loader-2 animate-spin" : "ti-mail-forward"} text-[14px]`} />
              {resending ? "Sending…" : "Resend Invite"}
            </button>
          )}
          {canResetPassword && (
            <button
              onClick={handleResetPassword}
              disabled={resetting}
              suppressHydrationWarning
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium border transition-colors"
              style={{
                borderColor: "var(--outline-v)",
                color: "var(--on-bg)",
                background: "var(--surface)",
              }}
            >
              <i className={`ti ${resetting ? "ti-loader-2 animate-spin" : "ti-key"} text-[14px]`} />
              {resetting ? "Resetting…" : "Reset Password"}
            </button>
          )}
          <button
            onClick={() => router.push("/dashboard/employees")}
            suppressHydrationWarning
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium border transition-colors"
            style={{
              borderColor: "var(--outline-v)",
              color: "var(--on-bg)",
              background: "var(--surface)",
            }}
          >
            <i className="ti ti-arrow-left text-[14px]" />
            Back
          </button>
        </div>
      </div>

      {(resetMsg || resetErr) && (
        <div
          className="mb-3 flex items-center gap-2 px-4 py-2.5 rounded-lg text-[13px] font-medium"
          style={resetErr
            ? { background: "var(--error-c)", color: "var(--error)" }
            : { background: "var(--success-c)", color: "var(--success)" }}
        >
          <i className={`ti ${resetErr ? "ti-alert-circle" : "ti-circle-check"} text-[16px]`} />
          {resetErr ?? resetMsg}
        </div>
      )}

      {/* identity card */}
      <div
        className="rounded-xl border p-5 sm:p-6"
        style={{ background: "var(--surface)", borderColor: "var(--outline-v)" }}
      >
        <div className="flex flex-col sm:flex-row gap-5">
          {/* avatar — no camera badge here: the profile photo endpoint is
              deliberately self-service only (see views_profile_photo.py),
              so there's nothing for HR to change on someone else's photo
              from this page. */}
          <div className="relative flex-shrink-0">
            <Avatar
              text={initials(employee.firstName, employee.lastName)}
              size={80}
              color={avatarColor(employee.department)}
              photoUrl={employee.photoUrl}
            />
          </div>

          {/* identity + meta */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap mb-0.5">
              <span className="text-[13px] font-semibold" style={{ color: "var(--on-variant)" }}>
                {employee.code}
              </span>
              <h2 className="text-[20px] font-bold" style={{ color: "var(--on-bg)" }}>
                {fullName(employee)}
              </h2>
              <StatusBadge status={employee.status} />
              {invite?.invite_status && INVITE_BADGE[invite.invite_status] && (
                <span
                  className="text-[11px] font-semibold px-2.5 py-1 rounded-full"
                  style={{
                    background: INVITE_BADGE[invite.invite_status].bg,
                    color: INVITE_BADGE[invite.invite_status].color,
                  }}
                  title={
                    invite.invite_expires_at
                      ? `Expires ${formatDate(invite.invite_expires_at)}`
                      : undefined
                  }
                >
                  {INVITE_BADGE[invite.invite_status].label}
                </span>
              )}
            </div>

            <p className="text-[13px] mb-4" style={{ color: "var(--on-variant)" }}>
              {employee.designation} · {employee.department}
            </p>

            {/* 2-col meta grid: left column DOB/Phone/Location, right column DOJ/Current Exp/Total Exp */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-2 gap-x-10">
              {/* Left */}
              <div className="flex flex-col gap-2">
                <MetaItem icon="ti-cake" label="DOB" value={formatDate(employee.dateOfBirth)} />
                <MetaItem icon="ti-phone" label="Phone" value={employee.phone || "—"} link={`tel:${employee.phone}`} highlight />
                <MetaItem icon="ti-map-pin" label="Location" value={employee.location || "—"} />
              </div>
              {/* Right */}
              <div className="flex flex-col gap-2">
                <MetaItem icon="ti-calendar" label="DOJ" value={formatDate(employee.dateOfJoining)} />
                <MetaItem icon="ti-clock" label="Current Experience" value={exp} highlight />
                <MetaItem icon="ti-clock-hour-4" label="Total Experience" value={exp} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetaItem({
  icon,
  label,
  value,
  link,
  highlight,
}: {
  icon: string;
  label: string;
  value: string;
  link?: string;
  highlight?: boolean;
}) {
  const val = link ? (
    <a href={link} className="font-medium hover:underline" style={{ color: "var(--primary)" }}>
      {value}
    </a>
  ) : (
    <span
      className="font-medium"
      style={{ color: highlight ? "var(--primary)" : "var(--on-bg)" }}
    >
      {value}
    </span>
  );

  return (
    <div className="flex items-center gap-2 text-[13px]">
      <i className={`ti ${icon} text-[14px]`} style={{ color: "var(--primary)" }} />
      <span style={{ color: "var(--on-variant)" }}>{label}:</span>
      {val}
    </div>
  );
}

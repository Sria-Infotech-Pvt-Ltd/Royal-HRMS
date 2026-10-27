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
  type Employee,
} from "../../_data";
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
  // The backend requires BOTH (acting on another person's login is an admin
  // action: views_reset_password._can_manage_accounts), so only offer the
  // buttons to someone for whom they will actually work.
  const canResetPermission = usePermission("employees.reset_password");
  const canEditEmployees = usePermission("employees.edit");
  const canResetPassword = canResetPermission && canEditEmployees;

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

      {/* identity banner — the same purple hero the workspace page uses, with the employee's photo (the photo
          endpoint is self-service only, so there is nothing for HR to change here). */}
      <section className="ess-hero" style={{ gridTemplateColumns: "1.1fr .9fr" }}>
        <div className="ess-person">
          <div
            className="ess-photo"
            role="img"
            aria-label={`${fullName(employee)} profile photo`}
            style={{
              backgroundImage: employee.photoUrl ? `url(${employee.photoUrl})` : "none",
              backgroundSize: "cover", backgroundPosition: "center", backgroundColor: "rgba(255,255,255,.18)",
              display: "grid", placeItems: "center", color: "#fff", fontWeight: 800, fontSize: 20, flexShrink: 0,
            }}
          >
            {!employee.photoUrl && initials(employee.firstName, employee.lastName)}
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <h1>{fullName(employee)}</h1>
              <StatusBadge status={employee.status} />
              {invite?.invite_status && INVITE_BADGE[invite.invite_status] && (
                <span
                  className="text-[11px] font-semibold px-2.5 py-1 rounded-full"
                  style={{ background: INVITE_BADGE[invite.invite_status].bg, color: INVITE_BADGE[invite.invite_status].color }}
                  title={invite.invite_expires_at ? `Expires ${formatDate(invite.invite_expires_at)}` : undefined}
                >
                  {INVITE_BADGE[invite.invite_status].label}
                </span>
              )}
            </div>
            {/* orgUnitName first (the real OrgUnit); the legacy `department` string is blank for anyone hired onto
                a real Position. Only joins with " · " when both sides are non-empty. */}
            <p>{[employee.designation, employee.code, employee.orgUnitName || employee.department].filter(Boolean).join(" · ")}</p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-y-2 gap-x-8 content-center">
          <MetaItem icon="ti-cake" label="DOB" value={formatDate(employee.dateOfBirth)} />
          <MetaItem icon="ti-calendar" label="DOJ" value={formatDate(employee.dateOfJoining)} />
          <MetaItem icon="ti-phone" label="Phone" value={employee.phone || "—"} link={employee.phone ? `tel:${employee.phone}` : undefined} />
          <MetaItem icon="ti-clock" label="Experience" value={exp} />
          <MetaItem icon="ti-map-pin" label="Location" value={employee.location || "—"} />
        </div>
      </section>
    </div>
  );
}

function MetaItem({ icon, label, value, link }: { icon: string; label: string; value: string; link?: string }) {
  const val = link ? (
    <a href={link} className="font-semibold hover:underline" style={{ color: "#fff" }}>{value}</a>
  ) : (
    <span className="font-semibold" style={{ color: "#fff" }}>{value}</span>
  );

  return (
    <div className="flex items-center gap-2 text-[13px]">
      <i className={`ti ${icon} text-[14px]`} style={{ color: "#ddd6fe" }} />
      <span style={{ color: "#ddd6fe" }}>{label}:</span>
      {val}
    </div>
  );
}

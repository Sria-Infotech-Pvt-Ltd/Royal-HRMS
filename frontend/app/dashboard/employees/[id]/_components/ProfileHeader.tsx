"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  experienceFrom,
  formatDate,
  fullName,
  initials,
  avatarColor,
  type Employee,
} from "../../_data";
import Avatar from "../../_components/Avatar";
import StatusBadge from "../../_components/StatusBadge";
import { useCurrentUser } from "@/hooks/useCurrentUser";

export default function ProfileHeader({ employee }: { employee: Employee }) {
  const router = useRouter();
  const user = useCurrentUser();
  const exp = experienceFrom(employee.dateOfJoining);

  return (
    <div className="mb-4">
      {/* breadcrumb + title row */}
      <div className="flex items-start justify-between flex-wrap gap-3 mb-3">
        <div>
          <nav className="flex items-center gap-1 text-[12px] mb-1.5" style={{ color: "var(--on-variant)" }}>
            <span className="font-medium" style={{ color: "var(--primary)" }}>{user?.companyName}</span>
            <i className="ti ti-chevron-right text-[11px]" style={{ color: "var(--outline)" }} />
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

        <button
          onClick={() => router.push("/dashboard/employees")}
          suppressHydrationWarning
          className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-[13px] font-medium border transition-colors"
          style={{
            borderColor: "var(--outline-v)",
            color: "var(--on-bg)",
            background: "#fff",
          }}
        >
          <i className="ti ti-arrow-left text-[14px]" />
          Back
        </button>
      </div>

      {/* identity card */}
      <div
        className="rounded-xl border p-5 sm:p-6"
        style={{ background: "#fff", borderColor: "var(--outline-v)" }}
      >
        <div className="flex flex-col sm:flex-row gap-5">
          {/* avatar with camera badge */}
          <div className="relative flex-shrink-0">
            <Avatar
              text={initials(employee.firstName, employee.lastName)}
              size={80}
              color={avatarColor(employee.department)}
            />
            <button
              title="Change photo"
              suppressHydrationWarning
              className="absolute bottom-0 right-0 w-6 h-6 rounded-full text-white flex items-center justify-center border-2 border-white transition-colors"
              style={{ background: "var(--primary)" }}
            >
              <i className="ti ti-camera text-[11px]" />
            </button>
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

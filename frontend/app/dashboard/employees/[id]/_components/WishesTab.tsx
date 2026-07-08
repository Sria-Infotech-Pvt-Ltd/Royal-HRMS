"use client";

import { useState } from "react";
import { SendWishModal } from "@/components/dashboard/SendWishModal";

interface Occasion {
  key:       string;
  label:     string;
  icon:      string;
  color:     string;
  dateField: "dateOfBirth" | "dateOfJoining" | null;
}

const OCCASIONS: Occasion[] = [
  { key: "birthday",    label: "Birthday Wish",         icon: "ti-cake",      color: "#e53e3e",        dateField: "dateOfBirth"   },
  { key: "anniversary", label: "Work Anniversary Wish", icon: "ti-briefcase", color: "var(--primary)", dateField: "dateOfJoining" },
  { key: "other",       label: "Other Occasion",        icon: "ti-confetti",  color: "#7c3aed",        dateField: null            },
];

function daysUntilAnniversary(isoDate: string): number | null {
  if (!isoDate) return null;
  const ref = new Date(isoDate);
  if (isNaN(ref.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const thisYear = new Date(today.getFullYear(), ref.getMonth(), ref.getDate());
  const diff = Math.round((thisYear.getTime() - today.getTime()) / 86_400_000);
  if (diff >= 0) return diff;
  const nextYear = new Date(today.getFullYear() + 1, ref.getMonth(), ref.getDate());
  return Math.round((nextYear.getTime() - today.getTime()) / 86_400_000);
}

function yearsCompleted(isoDate: string): number {
  const ref = new Date(isoDate);
  const today = new Date();
  let y = today.getFullYear() - ref.getFullYear();
  if (today.getMonth() < ref.getMonth() || (today.getMonth() === ref.getMonth() && today.getDate() < ref.getDate())) y--;
  return Math.max(0, y);
}

function formatDate(isoDate: string): string {
  if (!isoDate) return "";
  return new Date(isoDate).toLocaleDateString("en-IN", { day: "numeric", month: "long" });
}

interface Props {
  employeeId:    string;
  employeeName:  string;
  employeeEmail: string;
  dateOfBirth:   string;
  dateOfJoining: string;
}

export function WishesTab({ employeeId, employeeName, employeeEmail, dateOfBirth, dateOfJoining }: Props) {
  const [openModal,     setOpenModal]     = useState<string | null>(null);
  const [sentOccasions, setSentOccasions] = useState<Set<string>>(new Set()); // tracks which have been sent at least once

  function getDateForOccasion(occ: Occasion): string {
    if (occ.dateField === "dateOfBirth")   return dateOfBirth;
    if (occ.dateField === "dateOfJoining") return dateOfJoining;
    return "";
  }

  const activeOcc = OCCASIONS.find(o => o.key === openModal);

  return (
    <div>
      {/* Recipient banner */}
      <div style={{ background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "14px 18px", marginBottom: 20, display: "flex", alignItems: "center", gap: 10 }}>
        <i className="ti ti-send" style={{ fontSize: 16, color: "var(--primary)", flexShrink: 0 }} />
        <span style={{ fontSize: 13, color: "var(--on-variant)" }}>
          Wish emails will be sent to <strong style={{ color: "var(--on-bg)" }}>{employeeName}</strong> at <strong style={{ color: "var(--on-bg)" }}>{employeeEmail}</strong>
        </span>
      </div>

      {/* Occasion cards */}
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        {OCCASIONS.map(occ => {
          const dateStr   = getDateForOccasion(occ);
          const daysUntil = dateStr ? daysUntilAnniversary(dateStr) : null;
          const isToday   = daysUntil === 0;
          const isSoon    = daysUntil !== null && daysUntil > 0 && daysUntil <= 7;
          const years     = dateStr && occ.dateField === "dateOfJoining" ? yearsCompleted(dateStr) : null;
          const alreadySent = sentOccasions.has(occ.key);

          return (
            <div
              key={occ.key}
              style={{
                background:   "var(--surface)",
                border:       `1px solid ${isToday ? occ.color : "var(--outline-v)"}`,
                borderRadius: "var(--radius)",
                padding:      "18px 20px",
                position:     "relative",
                boxShadow:    isToday ? `0 0 0 2px ${occ.color}22` : "none",
                display:      "flex",
                alignItems:   "center",
                gap:          16,
              }}
            >
              {/* TODAY / SOON badge */}
              {isToday && (
                <div style={{ position: "absolute", top: -1, right: 14, background: occ.color, color: "#fff", fontSize: 10, fontWeight: 700, padding: "3px 10px", borderRadius: "0 0 8px 8px", letterSpacing: "0.04em" }}>
                  TODAY
                </div>
              )}
              {isSoon && !isToday && (
                <div style={{ position: "absolute", top: -1, right: 14, background: "var(--warn)", color: "#fff", fontSize: 10, fontWeight: 700, padding: "3px 10px", borderRadius: "0 0 8px 8px", letterSpacing: "0.04em" }}>
                  IN {daysUntil} DAY{daysUntil === 1 ? "" : "S"}
                </div>
              )}

              {/* Icon */}
              <div style={{ width: 48, height: 48, borderRadius: 12, background: `${occ.color}18`, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                <i className={`ti ${occ.icon}`} style={{ fontSize: 24, color: occ.color }} />
              </div>

              {/* Title + date info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)" }}>{occ.label}</div>
                {dateStr ? (
                  <div style={{ fontSize: 12, marginTop: 3, color: isToday ? occ.color : "var(--on-variant)", fontWeight: isToday ? 600 : 400, display: "flex", alignItems: "center", gap: 5 }}>
                    <i className="ti ti-calendar" style={{ fontSize: 12 }} />
                    {isToday
                      ? `${occ.dateField === "dateOfBirth" ? "Birthday" : "Anniversary"} is today!${years && years > 0 ? ` · ${years} year${years !== 1 ? "s" : ""}` : ""}`
                      : `${formatDate(dateStr)} · ${daysUntil} day${daysUntil === 1 ? "" : "s"} away${years && years > 0 ? ` · ${years} yr${years !== 1 ? "s" : ""}` : ""}`
                    }
                  </div>
                ) : occ.dateField ? (
                  <div style={{ fontSize: 12, marginTop: 3, color: "var(--outline)", display: "flex", alignItems: "center", gap: 5 }}>
                    <i className="ti ti-calendar-off" style={{ fontSize: 12 }} /> No date on record
                  </div>
                ) : (
                  <div style={{ fontSize: 12, marginTop: 3, color: "var(--on-variant)" }}>
                    Send a custom wish for any occasion
                  </div>
                )}
              </div>

              {/* Action */}
              <button
                onClick={() => setOpenModal(occ.key)}
                suppressHydrationWarning
                style={{
                  padding: "8px 18px", borderRadius: 8,
                  border: `1.5px solid ${alreadySent ? "var(--outline-v)" : occ.color}`,
                  background: "transparent",
                  color: alreadySent ? "var(--on-variant)" : occ.color,
                  fontSize: 13, fontWeight: 600, cursor: "pointer",
                  display: "flex", alignItems: "center", gap: 6, flexShrink: 0,
                }}
              >
                <i className={`ti ${alreadySent ? "ti-send" : occ.icon}`} style={{ fontSize: 14 }} />
                {alreadySent ? "Resend" : "Send Wish"}
              </button>
            </div>
          );
        })}
      </div>

      {/* Shared wish modal */}
      {activeOcc && (
        <SendWishModal
          employeeId={employeeId}
          employeeName={employeeName}
          employeeEmail={employeeEmail}
          preferredKey={activeOcc.key}
          onClose={() => setOpenModal(null)}
          onSent={() => {
            setSentOccasions(s => new Set([...s, activeOcc.key]));
            setOpenModal(null);
          }}
        />
      )}
    </div>
  );
}

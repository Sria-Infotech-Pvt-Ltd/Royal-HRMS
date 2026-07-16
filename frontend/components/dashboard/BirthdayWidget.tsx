"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { SendWishModal, type SendWishTarget } from "./SendWishModal";
import { SendAllBirthdayModal } from "./SendAllBirthdayModal";

export interface BirthdayEntry {
  employee_id:   string;
  name:          string;
  department:    string;
  designation:   string;
  date_of_birth: string;
  days_until:    number;
}

function getAge(dob: string): number {
  const d = new Date(dob);
  const today = new Date();
  let age = today.getFullYear() - d.getFullYear();
  if (today.getMonth() < d.getMonth() || (today.getMonth() === d.getMonth() && today.getDate() < d.getDate())) age--;
  return age;
}

function initials(name: string) {
  return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
}

function EntryRow({
  entry,
  isToday,
  sentIds,
  onOpenModal,
}: {
  entry:       BirthdayEntry;
  isToday:     boolean;
  sentIds:     Set<string>;
  onOpenModal: (target: SendWishTarget) => void;
}) {
  const alreadySent = sentIds.has(entry.employee_id);

  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "12px 20px",
      borderBottom: "1px solid var(--bg-high)",
      background: isToday ? "rgba(229,62,62,0.03)" : "transparent",
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: "50%",
        background: isToday ? "#e53e3e" : "var(--primary)",
        color: "#fff",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: isToday ? 18 : 12, fontWeight: 600, flexShrink: 0,
      }}>
        {isToday ? "🎂" : initials(entry.name)}
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{entry.name}</div>
        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
          {entry.designation} · {entry.department}
          {isToday
            ? ` · Turning ${getAge(entry.date_of_birth)}`
            : ` · In ${entry.days_until} day${entry.days_until === 1 ? "" : "s"}`}
        </div>
      </div>

      <div style={{ flexShrink: 0 }}>
        <button
          className="btn btn-outline btn-sm"
          suppressHydrationWarning
          style={alreadySent
            ? {}
            : isToday ? { borderColor: "#e53e3e", color: "#e53e3e" } : {}}
          onClick={() => onOpenModal({
            employeeId:   entry.employee_id,
            employeeName: entry.name,
            department:   entry.department,
            designation:  entry.designation,
            preferredKey: "birthday",
          })}
        >
          <i className={`ti ${alreadySent ? "ti-send" : "ti-cake"}`} />
          {alreadySent ? "Resend" : "Send Wish"}
        </button>
      </div>
    </div>
  );
}

export default function BirthdayWidget() {
  const [data,    setData]    = useState<{ today: BirthdayEntry[]; upcoming: BirthdayEntry[] } | null>(null);
  const [loading, setLoading] = useState(true);
  const [sentIds,     setSentIds]     = useState<Set<string>>(new Set());
  const [modal,       setModal]       = useState<SendWishTarget | null>(null);
  const [showSendAll, setShowSendAll] = useState(false);

  useEffect(() => {
    clientApi
      .get<{ success: boolean; data: { today: BirthdayEntry[]; upcoming: BirthdayEntry[] } }>(API.hrms.birthdays)
      .then(res => setData(res.data?.data ?? { today: [], upcoming: [] }))
      .catch(() => setData({ today: [], upcoming: [] }))
      .finally(() => setLoading(false));
  }, []);

  function markSent(id: string) {
    setSentIds(s => new Set([...s, id]));
  }

  const todayList    = data?.today    ?? [];
  const upcomingList = data?.upcoming ?? [];

  return (
    <>
      {/* Today's Birthdays */}
      <div className="card mb-16">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-cake" /> Today&apos;s Birthdays</div>
          {!loading && todayList.length > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="badge" style={{ background: "rgba(229,62,62,0.12)", color: "#e53e3e" }}>
                {todayList.length} today
              </span>
              <button
                className="btn btn-outline btn-sm"
                style={{ borderColor: "#e53e3e", color: "#e53e3e" }}
                onClick={() => setShowSendAll(true)}
                suppressHydrationWarning
              >
                <i className="ti ti-confetti" /> Send All
              </button>
            </div>
          )}
        </div>

        {loading ? (
          <div style={{ padding: "20px", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
          </div>
        ) : todayList.length === 0 ? (
          <div style={{ padding: "20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
            <i className="ti ti-cake" style={{ fontSize: 24, display: "block", marginBottom: 6, opacity: 0.3 }} />
            No birthdays today
          </div>
        ) : (
          <div style={{ padding: 0 }}>
            {todayList.map(entry => (
              <EntryRow key={entry.employee_id} entry={entry} isToday sentIds={sentIds} onOpenModal={setModal} />
            ))}
          </div>
        )}
      </div>

      {/* Upcoming Birthdays */}
      <div className="card mb-16">
        <div className="card-header">
          <div className="card-title"><i className="ti ti-confetti" /> Upcoming Birthdays</div>
          {!loading && upcomingList.length > 0 && (
            <span className="badge badge-primary">{upcomingList.length} upcoming</span>
          )}
        </div>

        {loading ? (
          <div style={{ padding: "20px", display: "flex", alignItems: "center", justifyContent: "center", gap: 8, fontSize: 13, color: "var(--on-variant)" }}>
            <i className="ti ti-loader-2 spin" style={{ color: "var(--primary)" }} /> Loading…
          </div>
        ) : upcomingList.length === 0 ? (
          <div style={{ padding: "20px", textAlign: "center", fontSize: 13, color: "var(--on-variant)" }}>
            <i className="ti ti-calendar-event" style={{ fontSize: 24, display: "block", marginBottom: 6, opacity: 0.3 }} />
            No upcoming birthdays in the next 30 days
          </div>
        ) : (
          <div style={{ padding: 0 }}>
            {upcomingList.map(entry => (
              <EntryRow key={entry.employee_id} entry={entry} isToday={false} sentIds={sentIds} onOpenModal={setModal} />
            ))}
          </div>
        )}
      </div>

      {/* Wish modal */}
      {modal && (
        <SendWishModal
          {...modal}
          onClose={() => setModal(null)}
          onSent={() => {
            markSent(modal.employeeId);
            setModal(null);
          }}
        />
      )}

      {/* Send All modal */}
      {showSendAll && (
        <SendAllBirthdayModal
          entries={todayList}
          onClose={() => setShowSendAll(false)}
          onAllSent={ids => {
            setSentIds(s => new Set([...s, ...ids]));
            setShowSendAll(false);
          }}
        />
      )}
    </>
  );
}

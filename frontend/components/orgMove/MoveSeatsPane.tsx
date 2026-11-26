"use client";

// Right pane of the "Move employees" board: the target unit's vacant positions as slots. Chosen people fill them
// automatically (same title first); drag a person onto a slot to place them there (swapping with whoever had it), use the
// slot's picker to do the same without a mouse, or press x to take someone out of the move.

import { useState } from "react";
import Avatar from "@/app/dashboard/employees/_components/Avatar";
import { initialsOf } from "@/lib/accessListView";
import { useT } from "@/hooks/useI18n";
import type { BulkMove } from "@/hooks/useBulkMoveOrgUnit";
import { DRAG_TYPE } from "./MovePeoplePane";
import styles from "./orgMove.module.css";

interface MoveSeatsPaneProps { move: BulkMove }

export default function MoveSeatsPane({ move }: MoveSeatsPaneProps) {
  const t = useT();
  const [overSeat, setOverSeat] = useState<string | null>(null);

  if (!move.toUnitId) {
    return (
      <section className={styles.pane} aria-label={t("New positions")}>
        <div className={styles.emptyPane}><i className="ti ti-building-arch" /><b style={{ color: "var(--ink-2)" }}>{t("Where are they going?")}</b>{t("Choose the new org unit at the top. Its vacant positions appear here.")}</div>
      </section>
    );
  }

  const occupantOf = (seatId: string) => move.chosenPeople.find(person => move.seatFor[person.employee_id] === seatId);
  const waiting = move.chosenPeople.filter(person => !move.seatFor[person.employee_id]);
  const filled = move.vacantSeats.filter(seat => occupantOf(seat.id)).length;
  const isFull = filled === move.vacantSeats.length && filled > 0;

  return (
    <section className={styles.pane} aria-label={t("New positions")}>
      <div className={styles.paneHead}>
        <div className={styles.paneTitle}>
          <h4>{move.unitName(move.toUnitId)}</h4>
          <span>{t("{filled} of {total} vacant positions filled", { filled, total: move.vacantSeats.length })}</span>
        </div>
        {move.vacantSeats.length > 0 && (
          <div className={styles.meter} aria-hidden="true">
            {move.vacantSeats.map((seat, index) => <i key={seat.id} className={index < filled ? (isFull ? styles.full : styles.on) : undefined} />)}
          </div>
        )}
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button type="button" className="btn btn-ghost btn-sm" onClick={move.resetMatches} disabled={move.chosenPeople.length === 0}>
            <i className="ti ti-wand" /> {t("Auto-fill by title")}
          </button>
        </div>
      </div>

      {waiting.length > 0 && (
        <div className={styles.waiting}>
          <b>{t("Waiting for a position ({count})", { count: waiting.length })}</b>
          {waiting.map(person => (
            <span key={person.employee_id} className={styles.occupant} draggable onDragStart={event => event.dataTransfer.setData(DRAG_TYPE, person.employee_id)}>
              <Avatar text={initialsOf(person.full_name)} size={22} photoUrl={person.profile_photo_url} />
              <span>{person.full_name}</span>
            </span>
          ))}
        </div>
      )}

      <div className={styles.paneBody} role="list">
        {move.vacantSeats.length === 0 && (
          <div className={styles.emptyPane}><i className="ti ti-armchair-off" /><b style={{ color: "var(--ink-2)" }}>{t("No vacant positions here")}</b>{t("Add positions to this unit in Organization Management, then come back.")}</div>
        )}
        {move.vacantSeats.map(seat => {
          const occupant = occupantOf(seat.id);
          return (
            <div
              key={seat.id} role="listitem"
              className={`${styles.seat}${occupant ? ` ${styles.filled}` : ""}${overSeat === seat.id ? ` ${styles.over}` : ""}`}
              onDragOver={event => { if (event.dataTransfer.types.includes(DRAG_TYPE)) { event.preventDefault(); setOverSeat(seat.id); } }}
              onDragLeave={() => setOverSeat(current => (current === seat.id ? null : current))}
              onDrop={event => { event.preventDefault(); setOverSeat(null); const code = event.dataTransfer.getData(DRAG_TYPE); if (code) move.placeOnSeat(code, seat.id); }}
            >
              <span className={styles.seatIcon}><i className={`ti ${occupant ? "ti-user-check" : "ti-armchair"}`} /></span>
              <span className={styles.seatText}>
                <b>{seat.title}</b>
                <small>{[seat.grade, seat.is_chief ? t("Head of unit") : ""].filter(Boolean).join(" · ") || t("Vacant")}</small>
              </span>
              {occupant ? (
                <span className={styles.occupant} draggable onDragStart={event => event.dataTransfer.setData(DRAG_TYPE, occupant.employee_id)}>
                  <Avatar text={initialsOf(occupant.full_name)} size={24} photoUrl={occupant.profile_photo_url} />
                  <span>{occupant.full_name}</span>
                  <button type="button" onClick={() => move.removePerson(occupant.employee_id)} aria-label={t("Remove {name}", { name: occupant.full_name })}><i className="ti ti-x" /></button>
                </span>
              ) : waiting.length > 0 ? (
                <select className={styles.fillSelect} value="" onChange={event => event.target.value && move.placeOnSeat(event.target.value, seat.id)} aria-label={t("Fill {position}", { position: seat.title })}>
                  <option value="">{t("Place someone…")}</option>
                  {waiting.map(person => <option key={person.employee_id} value={person.employee_id}>{person.full_name}</option>)}
                </select>
              ) : (
                <span className={styles.dropHint}>{t("Drop someone here")}</span>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

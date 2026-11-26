"use client";

// Left pane of the "Move employees" board: the people who can move. Click a row (or its box) to choose someone; drag a row
// onto a position on the right to place them there. A chosen row shows where that person is going.

import Avatar from "@/app/dashboard/employees/_components/Avatar";
import { initialsOf } from "@/lib/accessListView";
import TriStateCheckbox from "@/components/TriStateCheckbox";
import { useT } from "@/hooks/useI18n";
import type { BulkMove } from "@/hooks/useBulkMoveOrgUnit";
import styles from "./orgMove.module.css";

export const DRAG_TYPE = "application/x-aira-employee";

interface MovePeoplePaneProps { move: BulkMove }

export default function MovePeoplePane({ move }: MovePeoplePaneProps) {
  const t = useT();
  const shownChosen = move.people.filter(person => move.selected.has(person.employee_id)).length;
  const headState = shownChosen === 0 ? "none" : shownChosen === move.people.length ? "all" : "some";
  const seatTitle = (code: string) => move.vacantSeats.find(seat => seat.id === move.seatFor[code])?.title;

  return (
    <section className={styles.pane} aria-label={t("People")}>
      <div className={styles.paneHead}>
        <div className={styles.paneTitle}>
          <h4>{move.fromUnitId ? move.unitName(move.fromUnitId) : t("All org units")}</h4>
          <span>{t("{chosen} of {total} chosen", { chosen: move.selected.size, total: move.people.length })}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <TriStateCheckbox
            state={headState} label={t("Choose everyone shown")}
            onChange={() => (headState === "all" ? move.people.forEach(person => move.removePerson(person.employee_id)) : move.selectShown())}
          />
          <label className={styles.search} style={{ flex: 1 }}>
            <i className="ti ti-search" />
            <input type="search" value={move.search} onChange={event => move.setSearch(event.target.value)} placeholder={t("Name, employee ID or position")} aria-label={t("Search")} />
          </label>
        </div>
      </div>

      <div className={styles.paneBody} role="list">
        {move.isLoading && <div className={styles.emptyPane}><i className="ti ti-loader-2 animate-spin" />{t("Loading…")}</div>}
        {!move.isLoading && move.people.length === 0 && <div className={styles.emptyPane}><i className="ti ti-users" />{t("No active employees match.")}</div>}
        {move.people.map(person => {
          const code = person.employee_id;
          const isChosen = move.selected.has(code);
          const goesTo = isChosen ? seatTitle(code) : undefined;
          return (
            <div
              key={code} role="listitem" draggable className={`${styles.person}${isChosen ? ` ${styles.chosen}` : ""}`}
              onDragStart={event => { event.dataTransfer.setData(DRAG_TYPE, code); event.dataTransfer.effectAllowed = "move"; }}
              onClick={() => (isChosen ? move.removePerson(code) : move.toggle(code))}
            >
              <input type="checkbox" checked={isChosen} readOnly tabIndex={-1} aria-hidden="true" style={{ accentColor: "var(--brand)", pointerEvents: "none" }} />
              <Avatar text={initialsOf(person.full_name)} size={32} photoUrl={person.profile_photo_url} />
              <span className={styles.personText}>
                <b>{person.full_name}</b>
                <small>{code} · {person.designation || t("No position")}</small>
              </span>
              {goesTo ? (
                <span className={styles.goesTo}><i className="ti ti-arrow-right" />{goesTo}</span>
              ) : isChosen && move.toUnitId ? (
                <span className={styles.goesTo} style={{ color: "var(--warn)" }}>{t("No position yet")}</span>
              ) : !move.fromUnitId ? (
                <span className={styles.unitTag}>{move.unitName(person.org_unit_id) || t("No org unit")}</span>
              ) : null}
              <button
                type="button" className="sr-only" aria-pressed={isChosen}
                onClick={event => { event.stopPropagation(); if (isChosen) move.removePerson(code); else move.toggle(code); }}
              >
                {isChosen ? t("Remove {name}", { name: person.full_name }) : t("Choose {name}", { name: person.full_name })}
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
}

"use client";

// Data and saving for the "Move employees" wizard: who can be moved (filtered by unit and search), every unit with its
// vacant seats, a suggested seat for each chosen person (editable), and the one POST that moves them all.

import { useCallback, useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useOrgUnitsAndPositions } from "@/hooks/useOrgUnitsAndPositions";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { rowsOf } from "@/lib/listResponse";
import { suggestSeats, todayIsoDate } from "@/lib/orgMove";
import type { ApiEmployee } from "@/app/dashboard/employees/[id]/_apiMapping";
import type { OrgUnit, Position } from "@/types/orgStructure";

export interface BulkMoveSkipped { employee_id: string; reason: string }
export interface BulkMoveResult { moved: { employee_id: string; org_unit: string; position: string }[]; skipped: BulkMoveSkipped[] }
export interface UnitSummary { unit: OrgUnit; parentName: string | null; vacant: number; filled: number }

const EMPLOYEE_LIST_URL = `${API.employees.list}?page_size=200&status=active`;

function matchesSearch(person: ApiEmployee, query: string): boolean {
  if (!query) return true;
  const haystack = `${person.full_name} ${person.employee_id} ${person.designation ?? ""}`.toLowerCase();
  return haystack.includes(query.toLowerCase());
}

export function useBulkMoveOrgUnit(initialFromUnitId = "") {
  const { data: employeePage, loading: isLoadingEmployees, refetch } = useFetch<{ results: ApiEmployee[] }>(EMPLOYEE_LIST_URL);
  const { units, positions, loading: isLoadingUnits } = useOrgUnitsAndPositions();
  const [fromUnitId, setFromUnitId] = useState(initialFromUnitId);
  const [toUnitId, setToUnitId] = useState("");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [seatOverrides, setSeatOverrides] = useState<Record<string, string>>({});
  const [effectiveDate, setEffectiveDate] = useState(todayIsoDate());
  const [reason, setReason] = useState("");

  const unitSummaries = useMemo<UnitSummary[]>(() => {
    const nameById = new Map(units.map(unit => [unit.id, unit.name]));
    return units.filter(unit => unit.is_active).map(unit => {
      const seats = positions.filter(position => position.org_unit === unit.id && position.is_active);
      const vacant = seats.filter(position => !position.holder).length;
      return { unit, parentName: unit.parent ? nameById.get(unit.parent) ?? null : null, vacant, filled: seats.length - vacant };
    });
  }, [units, positions]);
  const unitName = useCallback((id: string | null) => units.find(unit => unit.id === id)?.name ?? "", [units]);

  const everyone = useMemo(() => rowsOf<ApiEmployee>(employeePage).filter(person => person.is_active), [employeePage]);
  const people = useMemo(
    () => everyone.filter(person => (!fromUnitId || person.org_unit_id === fromUnitId) && matchesSearch(person, search.trim())),
    [everyone, fromUnitId, search],
  );
  // Chosen people stay chosen when the filter or search changes; they are listed from everyone, not just the visible rows.
  const chosenPeople = useMemo(() => everyone.filter(person => selected.has(person.employee_id)), [everyone, selected]);
  const vacantSeats = useMemo<Position[]>(
    () => positions.filter(position => position.org_unit === toUnitId && position.is_active && !position.holder),
    [positions, toUnitId],
  );

  // The suggestion follows the selection; a seat picked by hand wins over it and is not offered to anyone else.
  const seatFor = useMemo(() => {
    const pickedByHand = new Set(Object.values(seatOverrides).filter(Boolean));
    const suggested = suggestSeats(
      chosenPeople.filter(person => !(person.employee_id in seatOverrides)).map(person => ({ employeeId: person.employee_id, title: person.designation ?? "" })),
      vacantSeats.filter(seat => !pickedByHand.has(seat.id)).map(seat => ({ id: seat.id, title: seat.title })),
    );
    return { ...suggested, ...seatOverrides };
  }, [chosenPeople, vacantSeats, seatOverrides]);
  const matchedCount = chosenPeople.filter(person => seatFor[person.employee_id]).length;

  const toggle = useCallback((code: string) => {
    setSelected(previous => {
      const next = new Set(previous);
      if (next.has(code)) next.delete(code); else next.add(code);
      return next;
    });
  }, []);
  const selectShown = useCallback(() => setSelected(previous => new Set([...previous, ...people.map(person => person.employee_id)])), [people]);
  const clearSelection = useCallback(() => { setSelected(new Set()); setSeatOverrides({}); }, []);
  const chooseToUnit = useCallback((unitId: string) => { setToUnitId(unitId); setSeatOverrides({}); }, []);
  const chooseSeat = useCallback((code: string, seatId: string) => setSeatOverrides(previous => ({ ...previous, [code]: seatId })), []);
  const resetMatches = useCallback(() => setSeatOverrides({}), []);

  // A hand placement (drag or pick) freezes everyone's current seat, so nobody else is reshuffled, and swaps with whoever
  // already had that seat (they take the placed person's old seat, or wait without one).
  const placeOnSeat = useCallback((code: string, seatId: string) => {
    setSelected(previous => (previous.has(code) ? previous : new Set([...previous, code])));
    setSeatOverrides(() => {
      const frozen: Record<string, string> = {};
      for (const person of chosenPeople) frozen[person.employee_id] = seatFor[person.employee_id] ?? "";
      const occupant = Object.keys(frozen).find(other => other !== code && frozen[other] === seatId);
      if (occupant) frozen[occupant] = frozen[code] ?? "";
      frozen[code] = seatId;
      return frozen;
    });
  }, [chosenPeople, seatFor]);
  const removePerson = useCallback((code: string) => {
    setSelected(previous => { const next = new Set(previous); next.delete(code); return next; });
    setSeatOverrides(previous => { const next = { ...previous }; delete next[code]; return next; });
  }, []);
  const swapUnits = useCallback(() => {
    setFromUnitId(toUnitId);
    setToUnitId(fromUnitId);
    setSelected(new Set());
    setSeatOverrides({});
  }, [fromUnitId, toUnitId]);

  const submit = useCallback(async (): Promise<BulkMoveResult> => {
    const moves = chosenPeople
      .filter(person => seatFor[person.employee_id])
      .map(person => ({ employee_id: person.employee_id, position_id: seatFor[person.employee_id] }));
    const { data } = await clientApi.post<{ data: BulkMoveResult }>(API.employees.bulkMoveOrgUnit, { moves, effective_date: effectiveDate, reason });
    setSelected(new Set());
    setSeatOverrides({});
    refetch();
    return data.data;
  }, [chosenPeople, seatFor, effectiveDate, reason, refetch]);

  return {
    isLoading: isLoadingEmployees || isLoadingUnits, unitSummaries, unitName, people, chosenPeople, vacantSeats, selected, seatFor,
    matchedCount, fromUnitId, toUnitId, search, effectiveDate, reason, isPastDate: effectiveDate < todayIsoDate(),
    setFromUnitId, chooseToUnit, setSearch, toggle, selectShown, clearSelection, chooseSeat, resetMatches, setEffectiveDate, setReason, submit,
    placeOnSeat, removePerson, swapUnits,
  };
}

export type BulkMove = ReturnType<typeof useBulkMoveOrgUnit>;

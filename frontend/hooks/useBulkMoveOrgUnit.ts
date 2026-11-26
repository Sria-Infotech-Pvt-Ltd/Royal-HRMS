"use client";

// Data and saving for "Move to another org unit": the employees in the unit being moved FROM, the vacant seats in the
// unit being moved TO, a suggested seat for each person, and the one POST that moves them all.

import { useCallback, useMemo, useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import { useOrgUnitsAndPositions } from "@/hooks/useOrgUnitsAndPositions";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { rowsOf } from "@/lib/listResponse";
import { suggestSeats, todayIsoDate } from "@/lib/orgMove";
import type { ApiEmployee } from "@/app/dashboard/employees/[id]/_apiMapping";

export interface BulkMoveSkipped { employee_id: string; reason: string }
export interface BulkMoveResult { moved: { employee_id: string; org_unit: string; position: string }[]; skipped: BulkMoveSkipped[] }

const EMPLOYEE_LIST_URL = `${API.employees.list}?page_size=200`;

export function useBulkMoveOrgUnit(initialFromUnitId = "") {
  const { data: employeePage, loading: isLoadingEmployees, refetch } = useFetch<{ results: ApiEmployee[] }>(EMPLOYEE_LIST_URL);
  const { units, positionsForUnit, loading: isLoadingUnits } = useOrgUnitsAndPositions();
  const [fromUnitId, setFromUnitId] = useState(initialFromUnitId);
  const [toUnitId, setToUnitId] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [seatOverrides, setSeatOverrides] = useState<Record<string, string>>({});
  const [effectiveDate, setEffectiveDate] = useState(todayIsoDate());
  const [reason, setReason] = useState("");

  const activeUnits = useMemo(() => units.filter(unit => unit.is_active), [units]);
  const people = useMemo(
    () => rowsOf<ApiEmployee>(employeePage).filter(person => person.is_active && (!fromUnitId || person.org_unit_id === fromUnitId)),
    [employeePage, fromUnitId],
  );
  const vacantSeats = useMemo(() => (toUnitId ? positionsForUnit(toUnitId, true) : []), [toUnitId, positionsForUnit]);
  const chosenPeople = useMemo(() => people.filter(person => selected.has(person.employee_id)), [people, selected]);

  // The suggestion follows the selection; a seat HR picked by hand wins over it.
  const seatFor = useMemo(() => {
    const pickedByHand = new Set(Object.values(seatOverrides).filter(Boolean));
    const suggested = suggestSeats(
      chosenPeople
        .filter(person => !(person.employee_id in seatOverrides))
        .map(person => ({ employeeId: person.employee_id, title: person.designation ?? "" })),
      vacantSeats.filter(seat => !pickedByHand.has(seat.id)).map(seat => ({ id: seat.id, title: seat.title })),
    );
    return { ...suggested, ...seatOverrides };
  }, [chosenPeople, vacantSeats, seatOverrides]);

  const toggle = useCallback((code: string) => {
    setSelected(previous => {
      const next = new Set(previous);
      if (next.has(code)) next.delete(code); else next.add(code);
      return next;
    });
  }, []);

  const chooseToUnit = useCallback((unitId: string) => { setToUnitId(unitId); setSeatOverrides({}); }, []);
  const chooseFromUnit = useCallback((unitId: string) => { setFromUnitId(unitId); setSelected(new Set()); }, []);
  const chooseSeat = useCallback((code: string, seatId: string) => setSeatOverrides(previous => ({ ...previous, [code]: seatId })), []);
  const selectAll = useCallback(() => setSelected(new Set(people.map(person => person.employee_id))), [people]);

  const unmatchedCount = chosenPeople.filter(person => !seatFor[person.employee_id]).length;

  const submit = useCallback(async (): Promise<BulkMoveResult> => {
    const moves = chosenPeople
      .filter(person => seatFor[person.employee_id])
      .map(person => ({ employee_id: person.employee_id, position_id: seatFor[person.employee_id] }));
    const { data } = await clientApi.post<{ data: BulkMoveResult }>(API.employees.bulkMoveOrgUnit, {
      moves, effective_date: effectiveDate, reason,
    });
    setSelected(new Set());
    setSeatOverrides({});
    refetch();
    return data.data;
  }, [chosenPeople, seatFor, effectiveDate, reason, refetch]);

  return {
    isLoading: isLoadingEmployees || isLoadingUnits, activeUnits, people, vacantSeats, chosenPeople, selected, seatFor, unmatchedCount,
    fromUnitId, toUnitId, effectiveDate, reason,
    chooseFromUnit, chooseToUnit, toggle, selectAll, chooseSeat, setEffectiveDate, setReason, submit,
  };
}

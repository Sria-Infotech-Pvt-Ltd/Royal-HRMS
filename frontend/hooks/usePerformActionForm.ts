"use client";

// The values the "Perform an action" modal collects, kept as one object. Choosing a different action type clears every field
// that belonged to the previous one, so nothing typed for a promotion leaks into a separation.

import { useCallback, useState } from "react";
import type { ActionType } from "@/app/dashboard/employees/_components/PerformActionFields/types";
import { performActionToday } from "@/lib/performAction";

export interface PerformActionValues {
  actionType: ActionType | "";
  reason: string;
  effectiveFrom: string;
  positionId: string;
  annualCtc: string;
  managerId: string;
  workLocation: string;
  moveUnitId: string;
  separationType: string;
  lastWorkingDay: string;
  separationConfirmed: boolean;
}

type FieldSetters = { [K in keyof PerformActionValues as `set${Capitalize<string & K>}`]: (value: PerformActionValues[K]) => void };

function blankFor(actionType: ActionType | "", effectiveFrom: string): PerformActionValues {
  return {
    actionType, effectiveFrom, reason: "", positionId: "", annualCtc: "", managerId: "", workLocation: "", moveUnitId: "",
    separationType: "", lastWorkingDay: "", separationConfirmed: false,
  };
}

export function usePerformActionForm(initialActionType?: ActionType) {
  const [values, setValues] = useState<PerformActionValues>(() => blankFor(initialActionType ?? "", performActionToday()));

  const update = useCallback(<K extends keyof PerformActionValues>(key: K, value: PerformActionValues[K]) => {
    setValues(previous => ({ ...previous, [key]: value }));
  }, []);
  const setActionType = useCallback((actionType: ActionType | "") => {
    setValues(previous => blankFor(actionType, previous.effectiveFrom));
  }, []);

  const setters: FieldSetters = {
    setActionType,
    setReason: value => update("reason", value),
    setEffectiveFrom: value => update("effectiveFrom", value),
    setPositionId: value => update("positionId", value),
    setAnnualCtc: value => update("annualCtc", value),
    setManagerId: value => update("managerId", value),
    setWorkLocation: value => update("workLocation", value),
    setMoveUnitId: value => update("moveUnitId", value),
    setSeparationType: value => update("separationType", value),
    setLastWorkingDay: value => update("lastWorkingDay", value),
    setSeparationConfirmed: value => update("separationConfirmed", value),
  };
  return { values, ...setters };
}

export type PerformActionForm = ReturnType<typeof usePerformActionForm>;

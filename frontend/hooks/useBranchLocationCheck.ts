"use client";

// Asks the server, while the admin types a branch's coordinates, whether they are valid and whether they look wrong
// for the chosen state / city. Saves nothing; the same rules run again when the branch is saved.

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

export interface LocationCheck {
  isValid: boolean;
  errors: Record<string, string>;
  warnings: string[];
}

const CHECK_DELAY_MS = 400;
const NO_RESULT: LocationCheck = { isValid: true, errors: {}, warnings: [] };

export function toCoordinate(raw: string): number | null {
  if (raw.trim() === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

export function useBranchLocationCheck(latitude: string, longitude: string, stateId: string, cityId: string) {
  const [result, setResult] = useState<LocationCheck>(NO_RESULT);
  const [isChecking, setIsChecking] = useState(false);

  useEffect(() => {
    const lat = toCoordinate(latitude);
    const lon = toCoordinate(longitude);
    if (lat === null || lon === null) {
      setResult(NO_RESULT);
      return;
    }
    let isCurrent = true;
    const timer = setTimeout(async () => {
      setIsChecking(true);
      try {
        const response = await clientApi.post<{ data: { is_valid: boolean; errors: Record<string, string>; warnings: string[] } }>(
          API.branches.checkLocation,
          { latitude: lat, longitude: lon, state: stateId || null, city: cityId || null },
        );
        if (isCurrent) {
          const data = response.data.data;
          setResult({ isValid: data.is_valid, errors: data.errors, warnings: data.warnings });
        }
      } catch {
        if (isCurrent) setResult(NO_RESULT); // the save itself still validates
      } finally {
        if (isCurrent) setIsChecking(false);
      }
    }, CHECK_DELAY_MS);
    return () => { isCurrent = false; clearTimeout(timer); };
  }, [latitude, longitude, stateId, cityId]);

  return { ...result, isChecking };
}

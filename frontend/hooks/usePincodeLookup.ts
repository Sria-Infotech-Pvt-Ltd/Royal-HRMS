"use client";

import { useCallback } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

export interface PincodeLocation {
  locality: string;
  district: string;
  state: string;
}

// On-demand PIN code -> District/State lookup, used by the onboarding
// wizard's address fields (DynamicStepFields.tsx) to auto-fill both once a
// valid 6-digit PIN code is typed, instead of asking for all three
// separately. Resolves to null on any failure (unknown PIN code, network
// error) — callers just leave District/State as manual entry in that case.
export function usePincodeLookup() {
  const lookup = useCallback(async (pincode: string): Promise<PincodeLocation | null> => {
    try {
      const res = await clientApi.get<{ data: PincodeLocation }>(API.onboarding.pincodeLookup(pincode));
      return res.data?.data ?? null;
    } catch {
      return null;
    }
  }, []);

  return { lookup };
}

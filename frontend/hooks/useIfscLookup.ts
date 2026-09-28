"use client";

import { useCallback } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

export interface IfscBankInfo {
  bank: string;
  branch: string;
  address: string;
  city: string;
  state: string;
}

// On-demand IFSC -> Bank/Branch lookup, mirroring usePincodeLookup.ts's own
// pattern exactly. Resolves to null on any failure (unknown code, network
// error) — callers just leave Bank/Branch as manual entry in that case.
export function useIfscLookup() {
  const lookup = useCallback(async (ifsc: string): Promise<IfscBankInfo | null> => {
    try {
      const res = await clientApi.get<{ data: IfscBankInfo }>(API.onboarding.ifscLookup(ifsc));
      return res.data?.data ?? null;
    } catch {
      return null;
    }
  }, []);

  return { lookup };
}

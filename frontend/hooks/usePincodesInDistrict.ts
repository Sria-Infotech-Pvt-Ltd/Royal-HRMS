import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { PincodeOption } from "@/components/PincodeSelect";

/** Every PIN code in a district, for the PIN code drop-down. Nothing is asked until both a state and a district are chosen. */
export function usePincodesInDistrict(state: string, district: string) {
  const isReady = state.trim() !== "" && district.trim() !== "";
  const { data, loading } = useFetch<{ pincodes: PincodeOption[] }>(isReady ? API.onboarding.pincodesInDistrict(state, district) : null, { cache: true });
  // While a district's list is on its way the previous district's list must not show, so nothing is offered until it arrives.
  return { options: isReady && !loading ? data?.pincodes ?? [] : [], isLoading: isReady && loading };
}

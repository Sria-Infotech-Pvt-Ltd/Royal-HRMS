import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

/** Live address lists from the server: the same data (and spelling) the PIN code lookup uses, so a chosen state or district always matches it. */
export function useStates() {
  const { data, loading } = useFetch<{ states: string[] }>(API.onboarding.locationStates, { cache: true });
  return { options: data?.states ?? [], isLoading: loading };
}

/** The districts of one state. Nothing is asked until a state is chosen, and the previous state's list never shows for a new one. */
export function useDistricts(state: string) {
  const isReady = state.trim() !== "";
  const { data, loading } = useFetch<{ districts: string[] }>(isReady ? API.onboarding.locationDistricts(state) : null, { cache: true });
  return { options: isReady && !loading ? data?.districts ?? [] : [], isLoading: isReady && loading };
}

export function useCountries() {
  const { data, loading } = useFetch<{ countries: string[] }>(API.onboarding.locationCountries, { cache: true });
  return { options: data?.countries ?? [], isLoading: loading };
}

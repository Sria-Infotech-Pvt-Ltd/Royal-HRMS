import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { DashboardOverview } from "@/types/dashboard";

/** KPI row + "Dashboard overview" panel data for the Workforce Dashboard. */
export function useDashboardOverview() {
  return useFetch<DashboardOverview>(API.dashboard.overview);
}

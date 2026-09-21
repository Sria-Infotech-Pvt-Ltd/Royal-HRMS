import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { OrganizationOverview } from "@/types/organization";

/** KPI row + "Organization overview" panel data for the Organization Structure landing page. */
export function useOrganizationOverview() {
  return useFetch<OrganizationOverview>(API.orgStructure.overview);
}

"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { OrgChartData } from "@/types/orgChart";

export function useOrgChart(branch?: string) {
  const { data, loading, error, refetch } = useFetch<OrgChartData>(API.orgChart.get(branch));
  return { orgChart: data, loading, error, refetch };
}

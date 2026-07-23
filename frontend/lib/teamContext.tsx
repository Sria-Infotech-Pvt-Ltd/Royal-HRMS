"use client";

import { createContext, useContext } from "react";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { ManagerDashboardData } from "@/types/managerDashboard";

// ── Shape ──────────────────────────────────────────────────────────────────────

interface TeamContextValue {
  data:    ManagerDashboardData | null;
  loading: boolean;
  error:   string | null;
  refetch: () => void;
}

// ── Context ───────────────────────────────────────────────────────────────────

const TeamContext = createContext<TeamContextValue>({
  data:    null,
  loading: false,
  error:   null,
  refetch: () => {},
});

// ── Provider ──────────────────────────────────────────────────────────────────

export function TeamProvider({ children }: { children: React.ReactNode }) {
  const { data, loading, error, refetch } = useFetch<ManagerDashboardData>(
    API.dashboard.manager
  );

  return (
    <TeamContext.Provider value={{ data, loading, error, refetch }}>
      {children}
    </TeamContext.Provider>
  );
}

// ── Consumer hook ─────────────────────────────────────────────────────────────

export function useTeam(): TeamContextValue {
  return useContext(TeamContext);
}

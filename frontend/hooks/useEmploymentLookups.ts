"use client";

// Dropdown data for the Edit record > Employment section: positions, people and the policy lists. Every call is
// independent, so one failing lookup leaves only its own dropdown empty. Cached for the session like EmploymentStep.

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

export interface PositionOption { id: string; title: string; org_unit_name: string; grade: string; job_template_name: string | null; is_active: boolean }
export interface PersonOption { id: string; full_name: string; employee_id: string; work_location?: string }
export interface NamedOption { id: string; name: string }

export interface EmploymentLookups {
  positions: PositionOption[];
  people: PersonOption[];
  weeklyPolicies: NamedOption[];
  shiftPolicies: NamedOption[];
  structures: NamedOption[];
}

const EMPTY: EmploymentLookups = { positions: [], people: [], weeklyPolicies: [], shiftPolicies: [], structures: [] };
const CACHE_TTL_MS = 5 * 60 * 1000;
let cached: { data: EmploymentLookups; expiresAt: number } | null = null;

type Paged<T> = { data: { results: T[] } };

export function useEmploymentLookups(): EmploymentLookups {
  const [lookups, setLookups] = useState<EmploymentLookups>(EMPTY);

  useEffect(() => {
    if (cached && cached.expiresAt > Date.now()) { setLookups(cached.data); return; }
    const params = { page_size: 200 };
    Promise.allSettled([
      clientApi.get<Paged<PositionOption>>(API.orgStructure.positions.list, { params }),
      clientApi.get<Paged<PersonOption>>(API.employees.list, { params }),
      clientApi.get<Paged<NamedOption>>(API.attendance.weeklyDayPolicies, { params }),
      clientApi.get<Paged<NamedOption>>(API.attendance.workingHoursPolicies, { params }),
      clientApi.get<Paged<NamedOption>>(API.payroll.structures, { params }),
    ]).then(([positions, people, weekly, shifts, structures]) => {
      const rows = <T,>(result: PromiseSettledResult<{ data: Paged<T> }>): T[] =>
        result.status === "fulfilled" ? (result.value.data.data.results ?? []) : [];
      const resolved: EmploymentLookups = {
        positions: rows(positions).filter(position => position.is_active),
        people: rows(people),
        weeklyPolicies: rows(weekly),
        shiftPolicies: rows(shifts),
        structures: rows(structures),
      };
      setLookups(resolved);
      if ([positions, people, weekly, shifts, structures].every(result => result.status === "fulfilled")) {
        cached = { data: resolved, expiresAt: Date.now() + CACHE_TTL_MS };
      }
    });
  }, []);

  return lookups;
}

import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { ApiEmployeeOption, BranchAdminSeat, CurrentBranchAdmin } from "./_data";

export interface BranchAdminOptions {
  seats:     BranchAdminSeat[];
  employees: ApiEmployeeOption[];
  /** Edit only: the current admin of this Company Code, or null when none is assigned. */
  currentAdmin: CurrentBranchAdmin | null;
}

/**
 * The app's own rule (core.access.can_manage_branch): an admin is whoever holds, today, an active
 * position with can_manage_branch, and works in this Company Code. `holders` are those seat holders'
 * employee records; a seat's `holder` is the User pk, which is the employee record's `uuid`.
 */
export function findCurrentAdmin(seats: BranchAdminSeat[], holders: ApiEmployeeOption[], branchName: string): CurrentBranchAdmin | null {
  for (const seat of seats) {
    const employee = holders.find(candidate => candidate.uuid === seat.holder && candidate.branch === branchName);
    if (employee) return { employee, positionId: seat.id, positionTitle: `${seat.title} — ${seat.org_unit_name}` };
  }
  return null;
}

// Starts from the (few) branch-wide seats rather than the employee list: that list is capped at
// 50 rows per page, so an admin past the first page would otherwise be missed.
async function loadSeatHolders(seats: BranchAdminSeat[]): Promise<ApiEmployeeOption[]> {
  const codes = [...new Set(seats.map(seat => seat.holder_employee_id).filter((code): code is string => !!code))];
  const results = await Promise.allSettled(
    codes.map(code => clientApi.get<{ data: ApiEmployeeOption }>(API.employees.detail(code))),
  );
  return results.flatMap(result => (result.status === "fulfilled" && result.value.data.data ? [result.value.data.data] : []));
}

/**
 * Options for the "Assign Company Code Admin" section, from existing endpoints only.
 * Never rejects: a failed request just leaves that list empty, the same as the Add form always did.
 */
export async function loadBranchAdminOptions(branchName?: string): Promise<BranchAdminOptions> {
  const [seatsResult, employeesResult] = await Promise.allSettled([
    clientApi.get<{ data: { results: BranchAdminSeat[] } }>(API.orgStructure.positions.list, { params: { page_size: 500, can_manage_branch: "true" } }),
    // No ?status=active: that filter means "fully onboarded, activated and not on probation", which
    // left out most real employees (1 of 14 in practice). Deactivated accounts are dropped below.
    clientApi.get<{ data: { results: ApiEmployeeOption[] } }>(API.employees.list, { params: { page_size: 50 } }),
  ]);
  const seats = seatsResult.status === "fulfilled" ? (seatsResult.value.data.data?.results ?? []) : [];
  const listed = employeesResult.status === "fulfilled" ? (employeesResult.value.data.data?.results ?? []) : [];
  const employees = listed.filter(employee => employee.is_active !== false);
  const currentAdmin = branchName ? findCurrentAdmin(seats, await loadSeatHolders(seats), branchName) : null;
  // Make sure the current admin is selectable in the employee dropdown even if not in the first page.
  const admin = currentAdmin?.employee;
  const withAdmin = admin && !employees.some(employee => employee.id === admin.id) ? [admin, ...employees] : employees;
  return { seats, employees: withAdmin, currentAdmin };
}

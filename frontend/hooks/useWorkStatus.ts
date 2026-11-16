import { useFetch } from "@/hooks/useFetch";
import { useDelayedRefetchOnce } from "@/hooks/useDelayedRefetchOnce";
import { API } from "@/lib/api/endpoints";
import type { ProjectSyncStatus, WorkStatusResponse } from "@/types/workStatus";

// employeeId omitted → the signed-in employee's own Work Status. The history is paginated (20 per page).
//
// When nothing is stored for the employee yet, the server answers at once and pulls from Project Budgeting in the
// background, flagging the response `sync_pending`. This then refetches ONCE shortly afterwards to pick up what arrived
// (no polling; see useDelayedRefetchOnce). It is always false for someone else's Work Status.
export const useWorkStatus = (employeeId?: string, page: number = 1) => {
  const result = useFetch<WorkStatusResponse>(
    `${employeeId ? API.workStatus.employee(employeeId) : API.workStatus.me}?page=${page}`
  );
  useDelayedRefetchOnce(result.data?.sync_pending === true, result.refetch);
  return result;
};

export const useProjectSyncStatus = (page: number = 1) =>
  useFetch<ProjectSyncStatus>(`${API.projectSync.status}?page=${page}`);

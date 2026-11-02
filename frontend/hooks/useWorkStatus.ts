import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import type { ProjectSyncStatus, WorkStatusResponse } from "@/types/workStatus";

// employeeId omitted → the signed-in employee's own Work Status. The history is paginated (20 per page).
export const useWorkStatus = (employeeId?: string, page: number = 1) =>
  useFetch<WorkStatusResponse>(
    `${employeeId ? API.workStatus.employee(employeeId) : API.workStatus.me}?page=${page}`
  );

export const useProjectSyncStatus = (page: number = 1) =>
  useFetch<ProjectSyncStatus>(`${API.projectSync.status}?page=${page}`);

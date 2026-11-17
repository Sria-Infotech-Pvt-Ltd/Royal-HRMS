import { useCallback, useState } from "react"
import { useFetch } from "@/hooks/useFetch"
import clientApi from "@/lib/clientApi"
import { API } from "@/lib/api/endpoints"
import type { ApiCycle, HrQueueData } from "@/types/performanceHub"

function messageFrom(error: unknown, fallback: string): string {
  return (error as { response?: { data?: { message?: string } } })?.response?.data?.message ?? fallback
}

/**
 * Everything the HR Performance hub shows: the active cycle's review queue and every review cycle, plus activating and
 * closing a cycle. A refused change (for example "another cycle is already active") is reported, not swallowed.
 */
export function usePerformanceHub() {
  const queue = useFetch<HrQueueData>(API.performance.hrQueue)
  const cycles = useFetch<ApiCycle[]>(API.performance.cycles)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [actionError, setActionError] = useState("")

  const { refetch: refetchQueue } = queue
  const { refetch: refetchCycles } = cycles
  const reload = useCallback(() => { refetchQueue(); refetchCycles() }, [refetchQueue, refetchCycles])

  const changeStatus = useCallback(async (id: string, status: "active" | "closed") => {
    setBusyId(id)
    setActionError("")
    try {
      await clientApi.patch(API.performance.cycleDetail(id), { status })
      reload()
    } catch (error: unknown) {
      setActionError(messageFrom(error, status === "active" ? "Could not activate the cycle." : "Could not close the cycle."))
    } finally {
      setBusyId(null)
    }
  }, [reload])

  return {
    data: queue.data,
    cycles: cycles.data ?? [],
    isLoading: queue.loading || cycles.loading,
    error: queue.error || cycles.error || "",
    actionError,
    clearActionError: () => setActionError(""),
    busyId,
    activate: (id: string) => changeStatus(id, "active"),
    close: (id: string) => changeStatus(id, "closed"),
    reload,
  }
}

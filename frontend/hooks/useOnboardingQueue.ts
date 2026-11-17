import { useCallback, useEffect, useRef, useState } from "react"
import clientApi from "@/lib/clientApi"
import { API } from "@/lib/api/endpoints"
import { useDebouncedValue } from "@/hooks/useDebouncedValue"
import type { ApprovalUser } from "@/app/dashboard/candidate-review/_components/OnboardingDrawer"
import type { QueueCounts, QueuePage, QueueStatusFilter } from "@/types/onboardingQueue"

const SEARCH_DELAY_MS = 300
const DEFAULT_PAGE_SIZE = 20 // only until the first response says what the server uses

export const EMPTY_COUNTS: QueueCounts = { total: 0, submitted: 0, rejected: 0, approved: 0 }

/** Counts from the server, with anything missing or not a number treated as zero. */
export function readCounts(raw: Partial<QueueCounts> | undefined): QueueCounts {
  const read = (value: unknown) => (typeof value === "number" && Number.isFinite(value) ? value : 0)
  return { total: read(raw?.total), submitted: read(raw?.submitted), rejected: read(raw?.rejected), approved: read(raw?.approved) }
}

/**
 * The onboarding approvals queue, one page at a time. Search and status are applied by the server, so every page and every
 * total covers the whole queue, not just what was loaded. Changing a filter returns to page 1; an out-of-date response is dropped.
 */
export function useOnboardingQueue() {
  const [searchText, setSearchText] = useState("")
  const [status, setStatusValue]    = useState<QueueStatusFilter>("")
  const [page, setPage]             = useState(1)
  const [rows, setRows]             = useState<ApprovalUser[]>([])
  const [counts, setCounts]         = useState<QueueCounts>(EMPTY_COUNTS)
  const [totalPages, setTotalPages] = useState(1)
  const [matching, setMatching]     = useState(0)
  const [pageSize, setPageSize]     = useState(DEFAULT_PAGE_SIZE)
  const [isLoading, setIsLoading]   = useState(true)
  const [error, setError]           = useState("")
  const [reloadKey, setReloadKey]   = useState(0)
  const latestRequest               = useRef(0)

  const search = useDebouncedValue(searchText.trim(), SEARCH_DELAY_MS)

  useEffect(() => {
    const requestId = ++latestRequest.current
    setIsLoading(true)
    setError("")
    clientApi
      .get<{ data: QueuePage<ApprovalUser> }>(API.onboarding.approvals, { params: { page, status: status || undefined, search: search || undefined } })
      .then(response => {
        if (requestId !== latestRequest.current) return
        const body = response.data?.data
        setRows(Array.isArray(body?.results) ? body.results : [])
        setCounts(readCounts(body?.counts))
        setTotalPages(body?.total_pages ?? 1)
        setMatching(body?.count ?? 0)
        if (body?.page_size) setPageSize(body.page_size)
        if (body?.page && body.page !== page) setPage(body.page) // the server moved us back to the last page
      })
      .catch(() => {
        if (requestId !== latestRequest.current) return
        setError("Failed to load onboarding submissions.")
        setRows([])
      })
      .finally(() => {
        if (requestId === latestRequest.current) setIsLoading(false)
      })
  }, [page, status, search, reloadKey])

  const setSearch = useCallback((text: string) => { setSearchText(text); setPage(1) }, [])
  const setStatus = useCallback((value: QueueStatusFilter) => { setStatusValue(value); setPage(1) }, [])
  const clearFilters = useCallback(() => { setSearchText(""); setStatusValue(""); setPage(1) }, [])
  const reload = useCallback(() => setReloadKey(key => key + 1), [])

  return {
    rows, counts, matching, page, pageSize, totalPages, isLoading, error,
    searchText, setSearch, status, setStatus, clearFilters, setPage, reload,
    hasFilters: searchText.trim() !== "" || status !== "",
  }
}

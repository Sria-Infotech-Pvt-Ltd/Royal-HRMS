"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { NavItem } from "@/lib/navConfig";

interface EmployeeResult {
  id:          string;
  employee_id: string;
  full_name:   string;
  department:  string;
  designation: string;
}

interface Props {
  navItems:           NavItem[]; // already permission-filtered, sections/comingSoon excluded
  canSearchEmployees: boolean;
}

/** Header "Search anything…" box — live results across the employee
 *  directory and the sidebar's own pages, so it doubles as a command
 *  palette. Employee results are skipped entirely (no request fired) for
 *  viewers without employees.view, rather than surfacing an empty section
 *  from a 403. */
export default function GlobalSearch({ navItems, canSearchEmployees }: Props) {
  const router = useRouter();
  const [query,     setQuery]     = useState("");
  const [open,       setOpen]      = useState(false);
  const [employees, setEmployees] = useState<EmployeeResult[]>([]);
  const [loading,   setLoading]   = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, []);

  function handleChange(value: string) {
    setQuery(value);
    setOpen(true);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (!canSearchEmployees || !value.trim()) { setEmployees([]); return; }
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await clientApi.get<{ data: { results: EmployeeResult[] } }>(
          API.employees.list, { params: { search: value.trim(), page_size: 5 } },
        );
        setEmployees(data.data?.results ?? []);
      } catch {
        setEmployees([]);
      } finally {
        setLoading(false);
      }
    }, 300);
  }

  function goTo(path: string) {
    setOpen(false);
    setQuery("");
    setEmployees([]);
    router.push(path);
  }

  const trimmed = query.trim();
  const matchingPages = trimmed
    ? navItems.filter(item => item.label.toLowerCase().includes(trimmed.toLowerCase())).slice(0, 5)
    : [];
  const showResults = open && trimmed.length > 0;
  const hasResults = employees.length > 0 || matchingPages.length > 0;

  return (
    <div ref={boxRef} className="hidden md:block relative min-w-[240px]">
      <div className="flex items-center gap-2 px-3 py-2 border-[1.5px] border-[var(--outline-v)] rounded-lg bg-[var(--bg)]">
        <i className="ti ti-search text-base text-[var(--outline)]" />
        <input
          type="text"
          placeholder="Search anything..."
          className="border-none bg-transparent text-[var(--on-bg)] text-[13px] flex-1 outline-none"
          value={query}
          onChange={e => handleChange(e.target.value)}
          onFocus={() => trimmed && setOpen(true)}
          onKeyDown={e => { if (e.key === "Escape") setOpen(false); }}
          suppressHydrationWarning
        />
      </div>

      {showResults && (
        <div style={{
          position: "absolute", top: "calc(100% + 6px)", left: 0, right: 0, zIndex: 300,
          background: "#fff", border: "1px solid var(--outline-v)", borderRadius: 8,
          boxShadow: "var(--shadow-md)", maxHeight: 320, overflowY: "auto",
        }}>
          {loading ? (
            <div style={{ padding: 12, fontSize: 13, color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 spin" /> Searching…
            </div>
          ) : !hasResults ? (
            <div style={{ padding: 12, fontSize: 13, color: "var(--on-variant)" }}>No results for &ldquo;{trimmed}&rdquo;.</div>
          ) : (
            <>
              {employees.length > 0 && (
                <div>
                  <div style={{ padding: "8px 12px 4px", fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", color: "var(--outline)", textTransform: "uppercase" }}>
                    Employees
                  </div>
                  {employees.map(emp => (
                    <button
                      key={emp.id} type="button" onClick={() => goTo(`/dashboard/employees/${emp.id}`)}
                      style={{ display: "block", width: "100%", textAlign: "left", padding: "8px 12px", border: "none", background: "none", cursor: "pointer" }}
                    >
                      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{emp.full_name}</div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{emp.employee_id} · {emp.department} · {emp.designation}</div>
                    </button>
                  ))}
                </div>
              )}
              {matchingPages.length > 0 && (
                <div>
                  <div style={{ padding: "8px 12px 4px", fontSize: 11, fontWeight: 700, letterSpacing: "0.04em", color: "var(--outline)", textTransform: "uppercase" }}>
                    Pages
                  </div>
                  {matchingPages.map(item => (
                    <button
                      key={item.id} type="button" onClick={() => goTo(item.path)}
                      style={{ display: "flex", alignItems: "center", gap: 8, width: "100%", textAlign: "left", padding: "8px 12px", border: "none", background: "none", cursor: "pointer" }}
                    >
                      <i className={`ti ${item.icon}`} style={{ color: "var(--outline)" }} />
                      <span style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{item.label}</span>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

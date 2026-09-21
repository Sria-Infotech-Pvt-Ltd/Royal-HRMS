"use client";

import { useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

export interface PickedEmployee {
  code:        string; // employee code (e.g. RSS000198) — sent as employee_id on separation requests
  uuid:        string; // User UUID — sent as assigned_to on KT/handover tasks
  name:        string;
  department:  string;
  designation: string;
}

interface ApiEmployeeRow {
  id: string; uuid?: string; employee_id: string; full_name: string; department: string; designation: string;
}

interface Props {
  value:     PickedEmployee | null;
  onChange:  (emp: PickedEmployee | null) => void;
  disabled?: boolean;
}

/** Search-to-pick employee field, backed by the real /employees/ directory
 *  (already scoped server-side: managers only ever get their own reports
 *  back, HR/admin get everyone). Only rendered for users with employees.view
 *  — leaving it unselected means the request is filed for the logged-in
 *  employee themselves (the backend defaults employee_id to self). */
export default function EmployeePickerField({ value, onChange, disabled }: Props) {
  const [query,   setQuery]   = useState("");
  const [open,    setOpen]    = useState(false);
  const [results, setResults] = useState<ApiEmployeeRow[]>([]);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onOutside(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onOutside);
    return () => document.removeEventListener("mousedown", onOutside);
  }, []);

  function search(q: string) {
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await clientApi.get<{ data: { results: ApiEmployeeRow[] } }>(
          API.employees.list, { params: { search: q, page_size: 8 } },
        );
        setResults(data.data?.results ?? []);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 300);
  }

  function pick(row: ApiEmployeeRow) {
    setOpen(false);
    onChange({
      code: row.employee_id || row.id, uuid: row.uuid ?? "", name: row.full_name,
      department: row.department, designation: row.designation,
    });
  }

  if (value) {
    return (
      <div className="field-input" style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          <strong>{value.name}</strong>
          <span style={{ color: "var(--on-variant)" }}> · {value.code} · {value.department}</span>
        </span>
        {!disabled && (
          <button type="button" className="btn btn-ghost btn-sm" style={{ flexShrink: 0 }} onClick={() => onChange(null)}>
            <i className="ti ti-x" />
          </button>
        )}
      </div>
    );
  }

  return (
    <div ref={boxRef} style={{ position: "relative" }}>
      <input
        className="field-input"
        placeholder="Leave blank to file for yourself, or search an employee…"
        value={query}
        disabled={disabled}
        onChange={e => { search(e.target.value); setOpen(true); }}
        onFocus={() => query && setOpen(true)}
        suppressHydrationWarning
      />
      {open && query && (
        <div style={{
          position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 60,
          background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: 8,
          boxShadow: "var(--shadow-md)", maxHeight: 220, overflowY: "auto",
        }}>
          {loading ? (
            <div style={{ padding: 12, fontSize: 13, color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 spin" /> Searching…
            </div>
          ) : results.length === 0 ? (
            <div style={{ padding: 12, fontSize: 13, color: "var(--on-variant)" }}>No employees found.</div>
          ) : (
            results.map(r => (
              <button
                key={r.id} type="button" onClick={() => pick(r)}
                style={{ display: "block", width: "100%", textAlign: "left", padding: "8px 12px", border: "none", borderBottom: "1px solid var(--outline-v)", background: "none", cursor: "pointer" }}
              >
                <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{r.full_name}</div>
                <div style={{ fontSize: 11, color: "var(--on-variant)" }}>{r.employee_id} · {r.department} · {r.designation}</div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

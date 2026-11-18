"use client";

// Shown before an employee is chosen in the Employee Month View: every employee as a card, with a search bar on top. Typing narrows the
// list (by name, ID, department or designation), and one click opens that person's month. It replaces the empty page.

import { useMemo, useState } from "react";
import { PALETTE, tint } from "./attendancePalette";
import { filterEmployees, type EmployeeOption } from "./monthView";

interface Props {
  employees: EmployeeOption[];
  loading: boolean;
  onSelect: (employee: EmployeeOption) => void;
}

const initialsOf = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0].toUpperCase()).join("") || "?";
const SHIMMER: React.CSSProperties = { background: "linear-gradient(90deg, #eceff6 25%, #f7f8fc 50%, #eceff6 75%)", backgroundSize: "300% 100%", animation: "ann-shimmer 1.4s linear infinite" };

function EmployeeCard({ employee, onSelect }: { employee: EmployeeOption; onSelect: (employee: EmployeeOption) => void }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      type="button" onClick={() => onSelect(employee)} aria-label={`Open ${employee.full_name}`}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)} onFocus={() => setHover(true)} onBlur={() => setHover(false)}
      style={{
        display: "flex", alignItems: "center", gap: 12, padding: "12px 14px", textAlign: "left", cursor: "pointer", borderRadius: 14, background: "var(--surface)",
        border: `1px solid ${hover ? tint(PALETTE.brand, 0.5) : "var(--outline-v)"}`, transform: hover ? "translateY(-1px)" : "none",
        boxShadow: hover ? `0 6px 16px ${tint(PALETTE.brand, 0.14)}` : "none", transition: "transform .14s ease, box-shadow .14s ease, border-color .14s ease",
      }}
    >
      <span aria-hidden="true" style={{ width: 42, height: 42, borderRadius: "50%", flexShrink: 0, display: "grid", placeItems: "center", fontWeight: 800, fontSize: 14, color: "#fff", background: `linear-gradient(135deg, ${PALETTE.brand}, #A78BFA)` }}>{initialsOf(employee.full_name)}</span>
      <span style={{ minWidth: 0, flex: 1 }}>
        <span style={{ display: "block", fontWeight: 700, fontSize: 14, color: "var(--on-bg)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{employee.full_name}</span>
        <span style={{ display: "block", fontSize: 12, color: "var(--on-variant)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
          {[employee.employee_id, employee.designation].filter(Boolean).join(" · ")}
        </span>
        {employee.department && <span style={{ display: "inline-block", marginTop: 4, fontSize: 11, fontWeight: 600, padding: "1px 8px", borderRadius: 999, background: tint(PALETTE.brand, 0.09), color: PALETTE.brand }}>{employee.department}</span>}
      </span>
      <i className="ti ti-chevron-right" aria-hidden="true" style={{ color: hover ? PALETTE.brand : "var(--outline)", transition: "color .14s" }} />
    </button>
  );
}

export default function MonthEmployeeDirectory({ employees, loading, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const shown = useMemo(() => filterEmployees(employees, query), [employees, query]);
  return (
    <section aria-label="All employees" className="card" style={{ padding: 0, overflow: "hidden" }}>
      <header style={{ padding: "16px 20px", display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", borderBottom: "1px solid var(--outline-v)", background: `linear-gradient(135deg, ${tint(PALETTE.brand, 0.07)} 0%, var(--surface) 60%)` }}>
        <div style={{ flex: "1 1 240px" }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "var(--on-bg)", display: "flex", alignItems: "center", gap: 8 }}>
            All employees
            {!loading && <span style={{ fontSize: 12, fontWeight: 700, padding: "2px 10px", borderRadius: 999, background: tint(PALETTE.brand, 0.12), color: PALETTE.brand }}>{query.trim() ? `${shown.length} of ${employees.length}` : employees.length}</span>}
          </h3>
          <p style={{ margin: "3px 0 0", fontSize: 12.5, color: "var(--on-variant)" }}>Select an employee to view their monthly attendance.</p>
        </div>
        <div style={{ position: "relative", flex: "0 1 340px", minWidth: 220 }}>
          <i className="ti ti-search" aria-hidden="true" style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "var(--on-variant)", fontSize: 15, pointerEvents: "none" }} />
          <input
            type="search" aria-label="Search employees" className="field-input" placeholder="Search by name, ID, department…" value={query}
            onChange={event => setQuery(event.target.value)} style={{ width: "100%", paddingLeft: 36 }}
          />
        </div>
      </header>

      <div style={{ padding: 16 }}>
        {loading ? (
          <div role="status" aria-label="Loading employees" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 10 }}>
            {Array.from({ length: 9 }, (_, index) => <div key={index} aria-hidden="true" style={{ ...SHIMMER, height: 70, borderRadius: 14 }} />)}
          </div>
        ) : shown.length === 0 ? (
          <div style={{ textAlign: "center", padding: "36px 12px", color: "var(--on-variant)" }}>
            <i className="ti ti-user-search" aria-hidden="true" style={{ fontSize: 34, color: "var(--outline)" }} />
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 8 }}>{employees.length === 0 ? "No employees found." : `No employee matches “${query.trim()}”.`}</div>
            {employees.length > 0 && <button className="btn btn-ghost btn-sm" style={{ marginTop: 10 }} onClick={() => setQuery("")}>Clear search</button>}
          </div>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 10 }}>
            {shown.map(employee => <EmployeeCard key={employee.id} employee={employee} onSelect={onSelect} />)}
          </div>
        )}
      </div>
    </section>
  );
}

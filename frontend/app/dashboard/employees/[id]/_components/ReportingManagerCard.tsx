"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";

interface EmployeeResult {
  id:          string;
  full_name:   string;
  employee_id: string;
  department:  string;
  branch:      string;
}

interface Props {
  label:        string;
  value:        string;   // display name
  selectedId:   string;   // current UUID
  disabled:     boolean;  // true = view mode
  listEndpoint: string;
  onSelect:     (uuid: string | null, name: string | null) => void;
}

const BORDER   = "#d3dae8";
const LABEL_W  = "140px";
const BASE_CLS =
  "w-full px-3.5 py-[7px] rounded-md border text-[13px] outline-none transition-all";

export function EmployeePickerInline({
  label, value, selectedId, disabled, listEndpoint, onSelect,
}: Props) {
  const [open, setOpen] = useState(false);

  // Fetch options only when dropdown is open — avoids double-fetch in StrictMode
  const { data: optionsRaw, loading } = useFetch<EmployeeResult[]>(
    disabled || !open ? null : listEndpoint
  );
  const options = optionsRaw ?? [];

  function handlePick(emp: EmployeeResult) {
    onSelect(emp.id, emp.full_name);
    setOpen(false);
  }

  return (
    <div className="flex items-center gap-3">
      <label
        className="text-right text-[12.5px] font-medium shrink-0 leading-tight"
        style={{ width: LABEL_W, color: "var(--on-variant)" }}
      >
        {label}
      </label>

      <div className="flex-1 min-w-0" style={{ position: "relative" }}>
        {/* ── Shared display button — readonly in view mode, clickable in edit mode ── */}
        <button
          type="button"
          disabled={disabled}
          onClick={() => !disabled && setOpen(o => !o)}
          className={BASE_CLS + " text-left appearance-none flex items-center justify-between pr-9"}
          style={{
            borderColor: open ? "var(--primary)" : BORDER,
            background: "#eff2f8",
            color: value ? "#1e4e8c" : "var(--on-variant)",
            fontWeight: value ? 600 : 400,
            cursor: disabled ? "default" : "pointer",
            boxShadow: open ? "0 0 0 2px rgba(30,78,140,0.10)" : undefined,
            // show chevron only in edit mode
            backgroundImage: disabled ? undefined : `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>")`,
            backgroundRepeat: "no-repeat",
            backgroundPosition: "right 10px center",
            backgroundSize: "15px",
          }}
        >
          {value || "—"}
        </button>

        {/* ── Dropdown panel ── */}
        {open && (
          <div style={{
            position: "absolute", top: "calc(100% + 4px)", left: 0, right: 0, zIndex: 60,
            background: "#fff", border: "1px solid var(--outline-v)", borderRadius: 8,
            boxShadow: "0 4px 20px rgba(0,0,0,0.12)", overflow: "hidden", maxHeight: 240, overflowY: "auto",
          }}>
            {loading ? (
              <div style={{ padding: "12px 14px", fontSize: 13, color: "var(--on-variant)", textAlign: "center" }}>
                <i className="ti ti-loader-2 spin" style={{ marginRight: 6 }} />Loading…
              </div>
            ) : options.length === 0 ? (
              <div style={{ padding: "12px 14px", fontSize: 13, color: "var(--on-variant)" }}>
                No options available.
              </div>
            ) : (
              options.map(emp => {
                const isActive = emp.id === selectedId;
                return (
                  <button
                    key={emp.id}
                    type="button"
                    style={{
                      display: "flex", alignItems: "center", gap: 10,
                      width: "100%", padding: "9px 14px",
                      background: isActive ? "rgba(30,78,140,0.06)" : "none",
                      border: "none", borderBottom: "1px solid var(--outline-v)",
                      cursor: "pointer", textAlign: "left",
                    }}
                    onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = "var(--bg-mid)"; }}
                    onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = "none"; }}
                    onClick={() => handlePick(emp)}
                  >
                    <Initials name={emp.full_name} />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: isActive ? 600 : 500, color: isActive ? "var(--primary)" : "var(--on-bg)" }}>
                        {emp.full_name}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--on-variant)" }}>
                        {emp.employee_id} · {emp.department}
                      </div>
                    </div>
                    {isActive && (
                      <i className="ti ti-check" style={{ marginLeft: "auto", color: "var(--primary)", fontSize: 14 }} />
                    )}
                  </button>
                );
              })
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Initials({ name }: { name: string }) {
  const letters = name.split(" ").map(w => w[0] ?? "").join("").toUpperCase().slice(0, 2);
  return (
    <div style={{
      width: 28, height: 28, borderRadius: "50%",
      background: "var(--primary)", color: "#fff",
      display: "flex", alignItems: "center", justifyContent: "center",
      fontSize: 11, fontWeight: 700, flexShrink: 0,
    }}>
      {letters}
    </div>
  );
}

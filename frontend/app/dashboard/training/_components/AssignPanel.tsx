"use client";

import { useMemo, useState } from "react";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { useToast } from "@/components/ToastProvider";
import { apiError, type Course, type PersonRef } from "@/lib/training";

interface Picker { employees: PersonRef[]; departments: string[]; branches: string[] }
type Mode = "people" | "groups" | "all";

const MODES: { key: Mode; icon: string; title: string; desc: string }[] = [
  { key: "people", icon: "ti-user-check", title: "Selected employees", desc: "Pick individual people" },
  { key: "groups", icon: "ti-building", title: "Departments / branches", desc: "Everyone in the chosen groups" },
  { key: "all", icon: "ti-users-group", title: "All eligible employees", desc: "Everyone you manage" },
];

function plural(n: number, word: string) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

export default function AssignPanel({ course, onDone, onClose }: {
  course: Course;
  /** After "Assign & View Progress" — the Progress tab. */
  onDone?: () => void;
  /** After "Assign & Close" — back to the course list. */
  onClose?: () => void;
}) {
  const [mode, setMode] = useState<Mode>("people");
  const [search, setSearch] = useState("");
  const { data, loading } = useFetch<Picker>(
    `${API.training.employees}${search.trim() ? `?search=${encodeURIComponent(search.trim())}` : ""}`);
  const [picked, setPicked] = useState<Record<string, PersonRef>>({});
  const [departments, setDepartments] = useState<string[]>([]);
  const [branches, setBranches] = useState<string[]>([]);
  const [due, setDue] = useState(course.deadline ?? "");
  const [busy, setBusy] = useState(false);
  const { showToast } = useToast();

  const employees = useMemo(() => data?.employees ?? [], [data]);
  const pickedCount = Object.keys(picked).length;
  const allShownPicked = employees.length > 0 && employees.every(e => picked[e.id]);

  const summary = mode === "all"
    ? "Every eligible employee in your scope"
    : mode === "people"
      ? (pickedCount ? `${plural(pickedCount, "employee")} selected` : "No employees selected")
      : ([departments.length && plural(departments.length, "department"), branches.length && plural(branches.length, "branch")]
          .filter(Boolean).join(" · ").replace("branchs", "branches") || "No departments or branches selected");
  const ready = mode === "all" || (mode === "people" ? pickedCount > 0 : departments.length + branches.length > 0);

  function togglePerson(p: PersonRef, on: boolean) {
    setPicked(prev => {
      const next = { ...prev };
      if (on) next[p.id] = p; else delete next[p.id];
      return next;
    });
  }

  function toggleShown(on: boolean) {
    setPicked(prev => {
      const next = { ...prev };
      for (const e of employees) { if (on) next[e.id] = e; else delete next[e.id]; }
      return next;
    });
  }

  function toggle(list: string[], set: (v: string[]) => void, v: string) {
    set(list.includes(v) ? list.filter(x => x !== v) : [...list, v]);
  }

  async function assign(next: "progress" | "close") {
    if (!ready) return;
    if (mode === "all" && !window.confirm(`Assign "${course.title}" to every eligible employee you manage?`)) return;
    setBusy(true);
    try {
      const body = {
        employee_ids: mode === "people" ? Object.keys(picked) : [],
        departments: mode === "groups" ? departments : [],
        branches: mode === "groups" ? branches : [],
        all: mode === "all",
        due_date: due || null,
      };
      const res = await clientApi.post<{ message: string }>(API.training.assign(course.id), body);
      showToast(res.data.message, "success");
      setPicked({}); setDepartments([]); setBranches([]);
      if (next === "progress") onDone?.();
      else onClose?.();
    } catch (e) {
      showToast(apiError(e, "Failed to assign the course."), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" data-testid="assign-panel">
      <div className="card-header">
        <div className="card-title"><i className="ti ti-user-plus" /> Assign this course</div>
        <span className="text-[12px] text-[var(--on-variant)]">Employees who already have it are skipped automatically</span>
      </div>

      <div className="card-body">
        {!course.is_active && (
          <div className="alert alert-warn mb-16"><i className="ti ti-alert-triangle" /> Activate the course (Details tab) before assigning it.</div>
        )}

        <div className="field-label" style={{ marginBottom: 8 }}>Assign to</div>
        <div role="radiogroup" aria-label="Assign to"
             style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10, marginBottom: 20 }}>
          {MODES.map(m => {
            const active = mode === m.key;
            return (
              <button key={m.key} type="button" role="radio" aria-checked={active} onClick={() => setMode(m.key)}
                      style={{
                        display: "flex", gap: 12, alignItems: "center", textAlign: "left", padding: "12px 14px",
                        borderRadius: 10, cursor: "pointer", background: active ? "rgba(30,78,140,0.06)" : "#fff",
                        border: `1.5px solid ${active ? "var(--primary)" : "var(--outline-v)"}`,
                      }}>
                <i className={`ti ${m.icon}`} style={{ fontSize: 20, color: active ? "var(--primary)" : "var(--on-variant)" }} />
                <span>
                  <span style={{ display: "block", fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{m.title}</span>
                  <span className="text-[12px] text-[var(--on-variant)]">{m.desc}</span>
                </span>
              </button>
            );
          })}
        </div>

        {mode === "people" && (
          <div>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
              <div style={{ position: "relative", flex: "1 1 260px", maxWidth: 380 }}>
                <i className="ti ti-search" style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)",
                                                      color: "var(--on-variant)" }} />
                <input className="field-input" style={{ paddingLeft: 34 }} placeholder="Search by name or employee ID"
                       value={search} onChange={e => setSearch(e.target.value)} aria-label="Search employees" />
              </div>
              <div style={{ flex: 1 }} />
              {pickedCount > 0 && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPicked({})}>Clear selection</button>
              )}
            </div>
            <div style={{ border: "1px solid var(--outline-v)", borderRadius: 10, overflow: "hidden" }}>
              <div className="table-wrap" style={{ maxHeight: 340, overflowY: "auto" }}>
                <table>
                  <thead style={{ position: "sticky", top: 0, background: "var(--bg-low, #f7f8fa)", zIndex: 1 }}>
                    <tr>
                      <th style={{ width: 44 }}>
                        <input type="checkbox" aria-label="Select all shown" checked={allShownPicked}
                               disabled={!employees.length} onChange={e => toggleShown(e.target.checked)} />
                      </th>
                      <th>Employee</th>
                      <th>Employee ID</th>
                      <th>Department</th>
                      <th>Branch</th>
                    </tr>
                  </thead>
                  <tbody>
                    {loading && !employees.length && (
                      <tr><td colSpan={5} className="text-[var(--on-variant)]">Loading employees…</td></tr>
                    )}
                    {!loading && !employees.length && (
                      <tr><td colSpan={5} className="text-[var(--on-variant)]">No employees match your search.</td></tr>
                    )}
                    {employees.map(p => (
                      <tr key={p.id} onClick={() => togglePerson(p, !picked[p.id])} style={{ cursor: "pointer",
                          background: picked[p.id] ? "rgba(30,78,140,0.05)" : undefined }}>
                        <td onClick={e => e.stopPropagation()}>
                          <input type="checkbox" aria-label={`Select ${p.name}`} checked={!!picked[p.id]}
                                 onChange={e => togglePerson(p, e.target.checked)} />
                        </td>
                        <td style={{ fontWeight: 500 }}>{p.name}</td>
                        <td className="text-[var(--on-variant)]">{p.employee_id || "—"}</td>
                        <td>{p.department || "—"}</td>
                        <td>{p.branch || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            {pickedCount > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
                {Object.values(picked).map(p => (
                  <span key={p.id} className="badge badge-primary" style={{ gap: 6 }}>
                    {p.name}
                    <button type="button" aria-label={`Remove ${p.name}`} onClick={() => togglePerson(p, false)}
                            style={{ background: "none", border: 0, cursor: "pointer", color: "inherit", padding: 0 }}>
                      <i className="ti ti-x" />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {mode === "groups" && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))", gap: 20 }}>
            {([["Departments", data?.departments ?? [], departments, setDepartments, "ti-briefcase"],
               ["Branches", data?.branches ?? [], branches, setBranches, "ti-building-skyscraper"]] as const).map(
              ([label, options, chosen, setChosen, icon]) => (
                <div key={label}>
                  <div className="field-label" style={{ marginBottom: 8 }}>{label}</div>
                  {options.length === 0 && <div className="text-[13px] text-[var(--on-variant)]">None available in your scope.</div>}
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {options.map(o => {
                      const on = chosen.includes(o);
                      return (
                        <button key={o} type="button" aria-pressed={on}
                                className={`btn btn-sm ${on ? "btn-filled" : "btn-outline"}`}
                                onClick={() => toggle([...chosen], v => setChosen(v), o)}>
                          <i className={`ti ${on ? "ti-check" : icon}`} /> {o}
                        </button>
                      );
                    })}
                  </div>
                </div>
              ))}
          </div>
        )}

        {mode === "all" && (
          <div className="alert alert-info">
            <i className="ti ti-info-circle" /> The course will be assigned to every active employee you manage who
            doesn&apos;t already have it. New joiners are covered by the &quot;Assign automatically to new joiners&quot;
            option on the Details tab.
          </div>
        )}
      </div>

      <div style={{ display: "flex", alignItems: "flex-end", gap: 16, flexWrap: "wrap", padding: "14px 20px",
                    borderTop: "1px solid var(--outline-v)", background: "var(--bg-low, #f7f8fa)" }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <div className="text-[11px] text-[var(--on-variant)]" style={{ textTransform: "uppercase", letterSpacing: "0.04em" }}>Selection</div>
          <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)" }}>{summary}</div>
        </div>
        <div className="field-group" style={{ margin: 0 }}>
          <label className="field-label" htmlFor="as-due">Due date</label>
          <input id="as-due" type="date" className="field-input" value={due} onChange={e => setDue(e.target.value)} />
        </div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <button className="btn btn-outline" onClick={() => assign("close")} disabled={busy || !ready || !course.is_active}>
            <i className="ti ti-send" /> Assign &amp; Close
          </button>
          <button className="btn btn-filled" onClick={() => assign("progress")} disabled={busy || !ready || !course.is_active}>
            {busy ? "Assigning…" : <>Assign &amp; View Progress <i className="ti ti-arrow-right" /></>}
          </button>
        </div>
      </div>
    </div>
  );
}

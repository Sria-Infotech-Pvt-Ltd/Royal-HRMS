"use client";

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useOrgUnitsAndPositions } from "@/hooks/useOrgUnitsAndPositions";

// Shown at the top of the onboarding wizard's first step — the "basic
// details" captured back at Add Employee time (name, contact, employment
// info) that the wizard otherwise never surfaces or lets anyone touch again
// outside the separate Edit Employee screen.
//
// Read-only in self-service onboarding (an employee must never be able to
// change their own Role or Company Code — a real privilege-escalation risk,
// not just a cosmetic one — so for consistency every field here is
// view-only for them, not just those two). Fully editable in HR-assisted
// onboarding, reusing the exact same PUT /employees/<id>/ request shape
// Edit Employee's own page already sends — no new backend capability, just
// a more convenient place to use the one that already exists.

interface ApiRole   { id: number; name: string; display_name: string; permissions: string[] }
interface ApiBranch { id: number; branch_name: string }

export interface BasicDetails {
  full_name:       string;
  email:           string;
  phone:           string;
  employee_type:   string;
  date_of_joining: string;
  role:            string; // Role.name (internal)
  role_display:    string;
  branch:          string; // Branch name string, matches User.branch's own convention
  department:      string;
  designation:     string;
  /** The real Org Unit/Position assigned at hire time (Placement) — kept
   * separate from `department` (the nearest is_department-level ancestor,
   * legitimately blank when the org chart has no such ancestor). Shown in
   * preference to `department` so this row never looks blank/unfilled for
   * an employee HR already placed into a real seat during hiring. */
  org_unit_name:   string | null;
}

interface Props {
  employeeId: string; // employee_id code — same identifier Edit Employee's page uses
  details:    BasicDetails;
  editable:   boolean;
  onSaved:    (updated: BasicDetails) => void;
}

const EMP_TYPES = ["Permanent", "Contract", "Freelancer", "Consultant", "Part-Time", "Temporary", "Intern"];

// .field-static is this codebase's existing "read-only value" box (see
// globals.css) — same height/padding as a real .field-input so read-only
// and editable mode line up identically, just a flat tinted fill instead of
// a border. overflow-wrap/minWidth guard against a long value (an email
// address in particular) overflowing its grid column into the next one.
function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="field-group" style={{ minWidth: 0 }}>
      <label className="field-label">{label}</label>
      <div className="field-static" style={{ overflowWrap: "anywhere", wordBreak: "break-word" }}>
        {value || "—"}
      </div>
    </div>
  );
}

export default function BasicDetailsCard({ employeeId, details, editable, onSaved }: Props) {
  const [editing, setEditing] = useState(false);
  const [form,    setForm]    = useState<BasicDetails>(details);
  const [saving,  setSaving]  = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  const [roles,    setRoles]    = useState<ApiRole[]>([]);
  const [branches, setBranches] = useState<ApiBranch[]>([]);
  const [orgUnitId, setOrgUnitId] = useState("");
  const [positionId, setPositionId] = useState("");
  const { units, positionsForUnit } = useOrgUnitsAndPositions();

  useEffect(() => { setForm(details); }, [details]);

  useEffect(() => {
    if (!editing) return;
    Promise.allSettled([
      clientApi.get<{ data: { results: ApiRole[] } }>(API.roles.list, { params: { page_size: 100 } }),
      clientApi.get<{ data: { results: ApiBranch[] } }>(API.branches.list, { params: { page_size: 100 } }),
    ]).then(([r, b]) => {
      if (r.status === "fulfilled") {
        setRoles(r.value.data.data.results.filter(x => !x.permissions.includes("settings.edit")));
      }
      if (b.status === "fulfilled") setBranches(b.value.data.data.results);
    });
  }, [editing]);

  const selectedBranchId = branches.find(b => b.branch_name === form.branch)?.id ?? null;
  // vacantOnly=false — this is a *reassignment* (they may already hold a
  // seat), matching the same convention Edit Employee's own "Reassign
  // Position" already uses, not Create Employee's vacant-only one.
  const positionOptions = orgUnitId ? positionsForUnit(orgUnitId, false, selectedBranchId) : [];

  function set<K extends keyof BasicDetails>(k: K, v: BasicDetails[K]) {
    setForm(f => ({ ...f, [k]: v }));
  }

  function cancel() {
    setForm(details);
    setOrgUnitId("");
    setPositionId("");
    setError(null);
    setEditing(false);
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      const payload: Record<string, string> = {
        full_name:       form.full_name,
        phone:           form.phone,
        employee_type:   form.employee_type,
        date_of_joining: form.date_of_joining,
        role:            form.role,
        branch:          form.branch,
      };
      if (positionId) payload.position = positionId;

      const res = await clientApi.put<{ data: Record<string, unknown> }>(API.employees.detail(employeeId), payload);
      const u = res.data.data;
      onSaved({
        full_name:       String(u.full_name ?? form.full_name),
        email:           String(u.email ?? form.email),
        phone:           String(u.phone ?? form.phone),
        employee_type:   String(u.employee_type ?? form.employee_type),
        date_of_joining: String(u.date_of_joining ?? form.date_of_joining),
        role:            String(u.role ?? form.role),
        role_display:    String(u.role_display ?? form.role_display),
        branch:          String(u.branch ?? form.branch),
        department:      String(u.department ?? form.department),
        designation:     String(u.designation ?? form.designation),
        org_unit_name:   u.org_unit_name != null ? String(u.org_unit_name) : form.org_unit_name,
      });
      setOrgUnitId("");
      setPositionId("");
      setEditing(false);
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Failed to save basic details.");
    } finally {
      setSaving(false);
    }
  }

  return (
    // A subtly tinted surface (var(--bg-mid)), not flat var(--bg) — the old
    // fill was the exact same grey as the page background sitting behind
    // the wizard card, so this whole section visually blurred into one
    // undifferentiated grey mass instead of reading as a distinct grouped
    // panel. .field-static's own var(--bg-low) fill is lighter still, so the
    // two remain visually distinct from each other, just less washed-out
    // overall.
    <div style={{
      background: "var(--bg-mid)",
      border: "1px solid var(--outline-v)",
      borderRadius: "var(--radius-lg, 12px)",
      padding: "18px 20px",
      marginBottom: 24,
      boxShadow: "0 1px 3px rgba(20, 21, 31, 0.04)",
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <div style={{ fontSize: "1.05rem", fontWeight: 700, color: "var(--on-bg)" }}>Basic Details</div>
        {editable && !editing && (
          <button className="btn btn-ghost btn-sm" onClick={() => setEditing(true)} type="button">
            <i className="ti ti-edit" style={{ fontSize: 13 }} /> Edit
          </button>
        )}
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 14 }}>{error}</div>}

      {!editing ? (
        <div className="form-row cols-4" style={{ marginBottom: 0 }}>
          <Row label="Full Name" value={form.full_name} />
          <Row label="Email" value={form.email} />
          <Row label="Phone" value={form.phone} />
          <Row label="Employee Type" value={form.employee_type} />
          <Row label="Date of Joining" value={form.date_of_joining} />
          <Row label="Role" value={form.role_display} />
          <Row label="Company Code" value={form.branch} />
          <Row label="Org Unit" value={form.org_unit_name || form.department} />
          <Row label="Designation" value={form.designation} />
        </div>
      ) : (
        <>
          <div className="form-row cols-2">
            <div className="field-group">
              <label className="field-label">Full Name</label>
              <input className="field-input" value={form.full_name} onChange={e => set("full_name", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Email <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(locked — login identity)</span></label>
              <input className="field-input" value={form.email} disabled style={{ background: "var(--bg-low)", color: "var(--on-variant)" }} />
            </div>
            <div className="field-group">
              <label className="field-label">Phone</label>
              <input className="field-input" value={form.phone} onChange={e => set("phone", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Employee Type</label>
              <select className="field-input field-select" value={form.employee_type} onChange={e => set("employee_type", e.target.value)}>
                {EMP_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Date of Joining</label>
              <input className="field-input" type="date" value={form.date_of_joining} onChange={e => set("date_of_joining", e.target.value)} />
            </div>
            <div className="field-group">
              <label className="field-label">Role</label>
              <select className="field-input field-select" value={form.role} onChange={e => set("role", e.target.value)}>
                <option value={form.role}>{form.role_display || "— current —"}</option>
                {roles.filter(r => r.name !== form.role).map(r => (
                  <option key={r.id} value={r.name}>{r.display_name}</option>
                ))}
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Company Code</label>
              <select className="field-input field-select" value={form.branch} onChange={e => set("branch", e.target.value)}>
                <option value={form.branch}>{form.branch || "— current —"}</option>
                {branches.filter(b => b.branch_name !== form.branch).map(b => (
                  <option key={b.id} value={b.branch_name}>{b.branch_name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-row cols-2" style={{ marginTop: 4 }}>
            <div className="field-group">
              <label className="field-label">Org Unit <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(only if reassigning)</span></label>
              <select className="field-input field-select" value={orgUnitId} onChange={e => { setOrgUnitId(e.target.value); setPositionId(""); }}>
                <option value="">— Keep current: {form.department || "none"} —</option>
                {units.filter(u => u.is_active).map(u => <option key={u.id} value={u.id}>{u.name}</option>)}
              </select>
            </div>
            <div className="field-group">
              <label className="field-label">Position</label>
              <select className="field-input field-select" value={positionId} onChange={e => setPositionId(e.target.value)} disabled={!orgUnitId}>
                <option value="">{orgUnitId ? "— Select position —" : "Pick an org unit first"}</option>
                {positionOptions.map(p => <option key={p.id} value={p.id}>{p.title}{p.default_role_name ? ` — ${p.default_role_name}` : ""}</option>)}
              </select>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
            <button className="btn btn-filled" onClick={save} disabled={saving} type="button">
              {saving ? "Saving…" : "Save"}
            </button>
            <button className="btn btn-ghost" onClick={cancel} disabled={saving} type="button">Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}

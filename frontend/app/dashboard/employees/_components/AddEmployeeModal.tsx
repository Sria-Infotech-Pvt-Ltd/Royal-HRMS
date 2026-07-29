"use client";

import { useEffect, useState, type ReactNode } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { usePermission } from "@/hooks/usePermission";
import { getEffectiveBranch, isUnrestrictedUser } from "@/lib/auth";

/* ── Types ────────────────────────────────────────────────────── */
interface ApiRole   { id: number; name: string; display_name: string }
interface ApiDept   { id: number; name: string }
interface ApiDesig  { id: number; name: string; department_name: string }
interface ApiBranch { id: number; branch_name: string; branch_code: string }

interface Form {
  first_name: string; last_name: string; email: string; phone: string;
  role: string; department: string; designation: string; branch: string;
  employee_type: string; date_of_joining: string;
}
type Errs = Partial<Record<keyof Form, string>>;

const EMP_TYPES = ["Permanent", "Contract", "Intern", "Probation"];

const EMPTY: Form = {
  first_name: "", last_name: "", email: "", phone: "",
  role: "", department: "", designation: "", branch: "",
  employee_type: "Permanent", date_of_joining: "",
};

/* ── Shared input style (matches app globals) ─────────────────── */
const INP = "w-full px-3.5 py-2.5 rounded-lg border text-[13px] bg-white text-[var(--on-bg)] placeholder:text-[#a5b0c2] focus:outline-none focus:ring-2 focus:ring-[rgba(30,78,140,0.12)] transition-colors";
const OK  = "border-[var(--outline-v)] focus:border-[var(--primary)]";
const ERR = "border-[var(--error)] focus:border-[var(--error)]";
const SEL_BG = {
  backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='16' height='16' fill='none' stroke='%234f5d75' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>\")",
  backgroundRepeat:   "no-repeat" as const,
  backgroundPosition: "right 10px center" as const,
  backgroundSize:     "14px" as const,
};

/* ── Atoms ────────────────────────────────────────────────────── */
function Field({ label, required, error, children }: { label: string; required?: boolean; error?: string; children: ReactNode }) {
  return (
    <div>
      <label className="block text-[12.5px] font-semibold text-[var(--on-bg)] mb-1.5">
        {label}{required && <span className="ml-0.5" style={{ color: "var(--error)" }}>*</span>}
      </label>
      {children}
      {error && <p className="text-[11.5px] mt-1 font-medium" style={{ color: "var(--error)" }}>{error}</p>}
    </div>
  );
}

function Inp({ v, set, ph, type = "text", err }: { v: string; set: (x: string) => void; ph?: string; type?: string; err?: boolean }) {
  return (
    <input type={type} value={v} onChange={e => set(e.target.value)} placeholder={ph}
      suppressHydrationWarning className={`${INP} ${err ? ERR : OK}`} />
  );
}

function Sel({ v, set, children, err, disabled }: { v: string; set: (x: string) => void; children: ReactNode; err?: boolean; disabled?: boolean }) {
  return (
    <select value={v} onChange={e => set(e.target.value)} disabled={disabled}
      suppressHydrationWarning
      className={`${INP} ${err ? ERR : OK} appearance-none pr-9 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed`}
      style={SEL_BG}>
      {children}
    </select>
  );
}

function SectionHead({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="flex items-center gap-2 pt-1 mb-4">
      <div className="w-6 h-6 rounded-md flex items-center justify-center flex-shrink-0"
        style={{ background: "rgba(30,78,140,0.10)" }}>
        <i className={`ti ${icon} text-[13px]`} style={{ color: "var(--primary)" }} />
      </div>
      <span className="text-[12px] font-bold uppercase tracking-wide" style={{ color: "var(--primary)" }}>{title}</span>
      <div className="flex-1 h-px" style={{ background: "var(--outline-v)" }} />
    </div>
  );
}

/* ── Component ────────────────────────────────────────────────── */
export default function AddEmployeeModal({
  onClose,
  onCreated,
}: {
  onClose:   () => void;
  onCreated: (emp: Record<string, unknown>) => void;
}) {
  const user            = useCurrentUser();
  const unrestricted    = isUnrestrictedUser(user);
  const effectiveBranch = getEffectiveBranch(user);
  // /roles/ is gated server-side to settings.edit holders — skip the call
  // entirely for everyone else instead of firing a request that always 403s.
  const canViewRoles    = usePermission("settings.edit");

  const [form,   setForm]   = useState<Form>(EMPTY);
  const [errs,   setErrs]   = useState<Errs>({});
  const [saving, setSaving] = useState(false);
  const [apiErr, setApiErr] = useState("");
  const [done,   setDone]   = useState<string>("");

  /* dropdown data */
  const [roles,    setRoles]    = useState<ApiRole[]>([]);
  const [depts,    setDepts]    = useState<ApiDept[]>([]);
  const [desigs,   setDesigs]   = useState<ApiDesig[]>([]);
  const [branches, setBranches] = useState<ApiBranch[]>([]);
  const [loading,     setLoading]     = useState(true);
  const [desigLoading, setDesigLoading] = useState(false);

  /* fetch roles, departments, branches on mount */
  useEffect(() => {
    // allSettled, not all — a permission-denied roles fetch (see canViewRoles)
    // must not also wipe out the departments/branches dropdowns.
    Promise.allSettled([
      canViewRoles
        ? clientApi.get<{ data: { results: ApiRole[]   } }>(API.roles.list,          { params: { page_size: 100 } })
        : Promise.resolve(null),
      clientApi.get<{ data: { results: ApiDept[]   } }>(API.departments.list,     { params: { page_size: 100 } }),
      clientApi.get<{ data: { results: ApiBranch[] } }>(API.employees.branches,   { params: { page_size: 100 } }),
    ])
      .then(([r, d, b]) => {
        if (r.status === "fulfilled" && r.value) {
          setRoles(r.value.data.data.results.filter(x => x.name !== "system_admin"));
        }
        if (d.status === "fulfilled") setDepts(d.value.data.data?.results ?? []);
        if (b.status === "fulfilled") setBranches(b.value.data.data.results);
      })
      .finally(() => setLoading(false));
  }, [canViewRoles]);

  // Branch-restricted users (everyone except system_admin) always add employees
  // to their own branch — lock the field instead of offering every branch.
  useEffect(() => {
    if (!unrestricted && effectiveBranch) {
      setForm(f => (f.branch ? f : { ...f, branch: effectiveBranch }));
    }
  }, [unrestricted, effectiveBranch]);

  /* fetch designations whenever department changes */
  useEffect(() => {
    if (!form.department) { setDesigs([]); return; }
    const dept = depts.find(d => d.name === form.department);
    if (!dept) { setDesigs([]); return; }
    setDesigLoading(true);
    clientApi.get(API.designations.list, { params: { department: dept.id, page_size: 100 } })
      .then(r => setDesigs(r.data?.data?.results ?? []))
      .catch(() => setDesigs([]))
      .finally(() => setDesigLoading(false));
  }, [form.department, depts]);

  function set(k: keyof Form, v: string) {
    setForm(f => {
      const next = { ...f, [k]: v };
      if (k === "department") next.designation = "";
      return next;
    });
    setErrs(e => ({ ...e, [k]: undefined }));
    setApiErr("");
  }

  function validate(): boolean {
    const e: Errs = {};
    if (!form.first_name.trim())    e.first_name    = "Required";
    if (!form.last_name.trim())     e.last_name     = "Required";
    if (!form.email.trim())         e.email         = "Required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email)) e.email = "Enter a valid email";
    if (!form.role)                 e.role          = "Required";
    if (!form.department)           e.department    = "Required";
    if (!form.designation.trim())   e.designation   = "Required";
    if (!form.branch)               e.branch        = "Required";
    if (!form.date_of_joining)      e.date_of_joining = "Required";
    setErrs(e);
    return Object.keys(e).length === 0;
  }

  async function submit() {
    if (!validate()) return;
    setSaving(true);
    setApiErr("");
    try {
      const { data } = await clientApi.post<{ message: string; data: Record<string, unknown> }>(
        API.employees.list,
        { ...form, role: Number(form.role) },
      );
      setDone(data.message || "Employee added successfully.");
      onCreated(data.data);
    } catch (err) {
      const e = err as { message?: string; data?: Errs };
      if (e?.data && typeof e.data === "object") {
        setErrs(prev => ({ ...prev, ...(e.data as Errs) }));
      }
      setApiErr(e?.message || "Something went wrong. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay open" onClick={e => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="modal modal-lg flex flex-col" style={{ maxHeight: "92vh" }}>

        {/* ── Header ── */}
        <div className="modal-header sticky top-0 flex-shrink-0">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
              style={{ background: "rgba(30,78,140,0.10)" }}>
              <i className="ti ti-user-plus text-[16px]" style={{ color: "var(--primary)" }} />
            </div>
            <h2 className="modal-title">Add New Employee</h2>
          </div>
          <button onClick={onClose} suppressHydrationWarning className="modal-close">
            <i className="ti ti-x text-[18px]" />
          </button>
        </div>

        {/* ── Success state ── */}
        {done ? (
          <div className="modal-body flex flex-col items-center justify-center py-10 text-center">
            <div className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
              style={{ background: "rgba(22,163,74,0.12)" }}>
              <i className="ti ti-circle-check text-[36px]" style={{ color: "var(--success)" }} />
            </div>
            <h3 className="text-[16px] font-bold text-[var(--on-bg)] mb-2">Employee Added!</h3>
            <p className="text-[13px] text-[var(--on-variant)] max-w-xs">{done}</p>
            <button onClick={onClose} suppressHydrationWarning
              className="mt-6 flex items-center gap-2 px-6 py-2.5 rounded-lg text-[13.5px] font-semibold text-white"
              style={{ background: "var(--primary)" }}>
              <i className="ti ti-check text-[14px]" /> Done
            </button>
          </div>
        ) : (
          <>
            {/* ── Body ── */}
            <div className="modal-body overflow-y-auto flex-1 space-y-5">

              {loading && (
                <div className="flex items-center justify-center py-8 gap-2 text-[13px] text-[var(--on-variant)]">
                  <i className="ti ti-loader-2 animate-spin text-[18px]" style={{ color: "var(--primary)" }} />
                  Loading...
                </div>
              )}

              {!loading && (
                <>
                  {apiErr && (
                    <div className="flex items-start gap-2 px-3.5 py-2.5 rounded-lg border border-[var(--error-c)]"
                      style={{ background: "var(--error-c)", color: "var(--error)" }}>
                      <i className="ti ti-alert-circle text-[14px] mt-0.5 flex-shrink-0" />
                      <span className="text-[13px]">{apiErr}</span>
                    </div>
                  )}

                  {/* ── Personal ── */}
                  <SectionHead icon="ti-user" title="Personal Information" />
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="First Name" required error={errs.first_name}>
                      <Inp v={form.first_name} set={v => set("first_name", v)} ph="e.g. Anjali" err={!!errs.first_name} />
                    </Field>
                    <Field label="Last Name" required error={errs.last_name}>
                      <Inp v={form.last_name} set={v => set("last_name", v)} ph="e.g. Sharma" err={!!errs.last_name} />
                    </Field>
                    <Field label="Work Email" required error={errs.email}>
                      <Inp v={form.email} set={v => set("email", v)} ph="anjali@royal.com" type="email" err={!!errs.email} />
                    </Field>
                    <Field label="Phone">
                      <Inp v={form.phone} set={v => set("phone", v)} ph="+91 98765 43210" type="tel" />
                    </Field>
                  </div>

                  {/* ── Employment ── */}
                  <SectionHead icon="ti-id" title="Employment Details" />
                  <div className="grid grid-cols-2 gap-4">
                    <Field label="Role" required error={errs.role}>
                      <Sel v={form.role} set={v => set("role", v)} err={!!errs.role}>
                        <option value="">— Select Role —</option>
                        {roles.map(r => (
                          <option key={r.id} value={r.id}>{r.display_name}</option>
                        ))}
                      </Sel>
                    </Field>
                    <Field label="Department" required error={errs.department}>
                      <Sel v={form.department} set={v => set("department", v)} err={!!errs.department}>
                        <option value="">— Select Department —</option>
                        {depts.map(d => (
                          <option key={d.id} value={d.name}>{d.name}</option>
                        ))}
                      </Sel>
                    </Field>
                    <Field label="Designation" required error={errs.designation}>
                      <Sel
                        v={form.designation}
                        set={v => set("designation", v)}
                        err={!!errs.designation}
                        disabled={!form.department || desigLoading}
                      >
                        <option value="">
                          {!form.department ? "Select department first" : desigLoading ? "Loading…" : desigs.length === 0 ? "No designations available" : "— Select Designation —"}
                        </option>
                        {desigs.map(d => (
                          <option key={d.id} value={d.name}>{d.name}</option>
                        ))}
                      </Sel>
                    </Field>
                    <Field label="Branch" required error={errs.branch}>
                      {unrestricted ? (
                        <Sel v={form.branch} set={v => set("branch", v)} err={!!errs.branch}>
                          <option value="">— Select Branch —</option>
                          {branches.map(b => (
                            <option key={b.id} value={b.branch_name}>{b.branch_name}</option>
                          ))}
                        </Sel>
                      ) : (
                        <div className={`${INP} ${OK} flex items-center gap-2 bg-[var(--bg-low)] cursor-not-allowed`}
                          title="Scoped to your branch">
                          <i className="ti ti-lock text-[12px]" style={{ color: "var(--on-variant)" }} />
                          {effectiveBranch}
                        </div>
                      )}
                    </Field>
                    <Field label="Employee Type">
                      <Sel v={form.employee_type} set={v => set("employee_type", v)}>
                        {EMP_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                      </Sel>
                    </Field>
                    <Field label="Date of Joining" required error={errs.date_of_joining}>
                      <Inp v={form.date_of_joining} set={v => set("date_of_joining", v)} type="date" err={!!errs.date_of_joining} />
                    </Field>
                  </div>

                  {/* Info banner */}
                  <div className="flex items-start gap-2.5 px-3.5 py-3 rounded-lg"
                    style={{ background: "rgba(30,78,140,0.06)", border: "1px solid rgba(30,78,140,0.14)" }}>
                    <i className="ti ti-info-circle text-[14px] mt-0.5 flex-shrink-0" style={{ color: "var(--primary)" }} />
                    <p className="text-[12.5px]" style={{ color: "var(--primary)" }}>
                      A temporary password will be emailed to the employee. They will be prompted to change it on first login.
                    </p>
                  </div>
                </>
              )}
            </div>

            {/* ── Footer ── */}
            <div className="modal-footer flex-shrink-0">
              <button onClick={onClose} disabled={saving} suppressHydrationWarning
                className="px-5 py-2.5 rounded-lg text-[13px] font-medium border border-[var(--outline-v)] text-[var(--on-bg)] bg-white hover:bg-[var(--bg-low)] transition-colors disabled:opacity-50">
                Cancel
              </button>
              <button onClick={submit} disabled={saving || loading} suppressHydrationWarning
                className="flex items-center gap-2 px-5 py-2.5 rounded-lg text-[13px] font-semibold text-white transition-colors disabled:opacity-60"
                style={{ background: "var(--primary)" }}>
                {saving
                  ? <><i className="ti ti-loader-2 animate-spin text-[14px]" /> Adding…</>
                  : <><i className="ti ti-user-plus text-[14px]" /> Add Employee</>}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import { isUnrestrictedUser } from "@/lib/auth";
import Modal from "@/components/Modal";
import ToggleSwitch from "@/components/ToggleSwitch";
import type { GSTRegistration } from "@/types/company";

interface StateObj {
  id: number;
  name: string;
}

interface CityObj {
  id: number;
  name: string;
}

interface Branch {
  id:             number;
  branch_code:    string;
  branch_name:    string;
  is_headquarter: boolean;
  address:        string;
  state:          number;
  state_name:     string;
  city:           number;
  city_name:      string;
  gst_registration:       string | null;
  gst_registration_gstin: string | null;
  employees_count: number;
  status:         string;
  geofencing_enabled:    boolean;
  latitude:              number | null;
  longitude:             number | null;
  allowed_radius_meters: number | null;
  has_coordinates:       boolean;
}

function geofenceBadge(branch: Branch): { label: string; cls: string } {
  if (!branch.geofencing_enabled) return { label: "Disabled", cls: "badge-neutral" };
  if (!branch.has_coordinates)    return { label: "No Coordinates", cls: "badge-warn" };
  return { label: "Active", cls: "badge-success" };
}

function LeaderFields({
  label, form, setForm, employees, errors, prefix,
}: {
  label: string;
  form: LeaderForm;
  setForm: (updater: (f: LeaderForm) => LeaderForm) => void;
  employees: ApiEmployeeOption[];
  errors: Record<string, string>;
  prefix: string;
}) {
  function set<K extends keyof LeaderForm>(k: K, v: LeaderForm[K]) {
    setForm(f => ({ ...f, [k]: v }));
  }

  const filtered = form.search.trim()
    ? employees.filter(e =>
        e.full_name.toLowerCase().includes(form.search.trim().toLowerCase()) ||
        e.email.toLowerCase().includes(form.search.trim().toLowerCase()) ||
        e.employee_id.toLowerCase().includes(form.search.trim().toLowerCase()),
      )
    : employees;

  return (
    <div style={{ marginBottom: "18px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "10px" }}>
        <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--primary)" }}>{label}</div>
        {employees.length > 0 && (
          <label className="module-check" style={{ fontSize: "12px", fontWeight: 400 }}>
            <input
              type="checkbox"
              checked={form.mode === "existing"}
              onChange={e => set("mode", e.target.checked ? "existing" : "new")}
            />
            <span>Assign an existing employee instead</span>
          </label>
        )}
      </div>

      {form.mode === "existing" ? (
        <div className="field-group">
          <input
            type="text"
            className="field-input"
            value={form.search}
            onChange={e => set("search", e.target.value)}
            placeholder="Search by name, email, or employee ID…"
            style={{ marginBottom: "8px" }}
          />
          <select
            className={`field-input field-select${errors[`${prefix}Employee`] ? " field-error" : ""}`}
            value={form.employeeId}
            onChange={e => set("employeeId", e.target.value)}
          >
            <option value="">— Select employee —</option>
            {filtered.map(e => (
              <option key={e.id} value={e.id}>
                {e.full_name} ({e.employee_id}) — {e.branch || "no branch"}
              </option>
            ))}
          </select>
          {errors[`${prefix}Employee`] && <p className="field-error-msg">{errors[`${prefix}Employee`]}</p>}
        </div>
      ) : (
        <>
          <div className="form-row cols-2" style={{ marginBottom: "8px" }}>
            <div className="field-group">
              <input
                type="text"
                className={`field-input${errors[`${prefix}Name`] ? " field-error" : ""}`}
                value={form.name}
                onChange={e => set("name", e.target.value)}
                placeholder="Full name"
              />
              {errors[`${prefix}Name`] && <p className="field-error-msg">{errors[`${prefix}Name`]}</p>}
            </div>
            <div className="field-group">
              <input
                type="email"
                className={`field-input${errors[`${prefix}Email`] ? " field-error" : ""}`}
                value={form.email}
                onChange={e => set("email", e.target.value)}
                placeholder="Work email"
              />
              {errors[`${prefix}Email`] && <p className="field-error-msg">{errors[`${prefix}Email`]}</p>}
            </div>
          </div>
          <div className="field-group">
            <input
              type="text"
              className={`field-input${errors[`${prefix}Designation`] ? " field-error" : ""}`}
              value={form.designation}
              onChange={e => set("designation", e.target.value)}
              placeholder="Designation"
            />
            {errors[`${prefix}Designation`] && <p className="field-error-msg">{errors[`${prefix}Designation`]}</p>}
          </div>
        </>
      )}
    </div>
  );
}

interface BranchStats {
  total_branches:          number;
  total_employees:         number;
  total_active_branches:   number;
  total_inactive_branches: number;
  total_cities:            number;
}

interface BranchDistribution {
  branch:      string;
  branch_code: string;
  employees:   number;
}

type Envelope<T> = { status: string; message: string; data: T };
type Paginated<T> = { count: number; page: number; page_size: number; total_pages: number; results: T[] };

interface ApiRole {
  id: number; name: string; display_name: string;
  can_manage_branch: boolean; permissions: string[];
}
interface ApiEmployeeOption {
  id: string; uuid: string; employee_id: string; full_name: string; email: string; branch: string; role: string;
}

interface LeaderForm {
  // "new" invites a brand-new person via the same create-and-email-credentials
  // flow as the Employees page; "existing" instead re-roles/re-branches an
  // employee who's already in the company (a transfer, not a new hire).
  // No department field — a Branch Admin oversees every department in the
  // branch, not one, unlike every other role.
  mode: "new" | "existing";
  name: string; email: string; designation: string;
  employeeId: string; search: string;
}
const EMPTY_LEADER: LeaderForm = {
  mode: "new", name: "", email: "", designation: "Branch Manager",
  employeeId: "", search: "",
};

// A leader row counts as "in use" the moment it's touched — once it is,
// every field that mode needs becomes required together.
function isLeaderActive(f: LeaderForm): boolean {
  return f.mode === "existing"
    ? !!f.employeeId
    : !!(f.name.trim() || f.email.trim());
}

const EMAIL_RE = /^[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+$/;

const OTHER_CITY = "__other__";
const BRANCH_NAME_RE = /^[A-Za-z0-9](?:[A-Za-z0-9 &\-.]*[A-Za-z0-9])?$/;
const CITY_NAME_RE   = /^[A-Za-z]+(?:[ '-][A-Za-z]+)*$/;

export default function BranchManagement() {
  const user      = useCurrentUser();
  const canEdit   = usePermission("settings.edit");
  const isHrAdmin = !isUnrestrictedUser(user) && !!user?.branch;

  const [branches, setBranches] = useState<Branch[]>([]);
  const [stats, setStats] = useState<BranchStats>({ total_branches: 0, total_employees: 0, total_active_branches: 0, total_inactive_branches: 0, total_cities: 0 });
  const [distribution, setDistribution] = useState<BranchDistribution[]>([]);
  
  const [states, setStates] = useState<StateObj[]>([]);
  const [cities, setCities] = useState<CityObj[]>([]);
  // Full GST Registrations list (Company Profile) — used both to warn "no
  // GSTIN for this state yet" and, when a state has more than one, to let
  // the admin pick exactly which one this branch should use.
  const [gstRegistrations, setGstRegistrations] = useState<GSTRegistration[]>([]);
  const [newCityName, setNewCityName] = useState("");
  const newCityRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [isLoading,     setIsLoading]     = useState(true);
  const [error,         setError]         = useState<string | null>(null);
  const [saveError,     setSaveError]     = useState<string | null>(null);
  const [fieldErrors,   setFieldErrors]   = useState<Record<string, string>>({});
  const [codeLoading,   setCodeLoading]   = useState(false);
  const [citiesLoading, setCitiesLoading] = useState(false);
  const [saving,        setSaving]        = useState(false);
  const [hqConfirm,     setHqConfirm]     = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<Branch | null>(null);
  const [deleteError,   setDeleteError]   = useState<string | null>(null);
  const [deleting,      setDeleting]      = useState(false);

  const [modalMode, setModalMode] = useState<"add" | "edit" | null>(null);

  // Optional "assign leadership" field on the Add Branch form — a fresh
  // branch has no one in it, so this lets the admin assign its first Branch
  // Admin in the same step instead of having to find the new branch again
  // afterward on the Employees page. Optional — leaving it blank is fine.
  const [branchAdminForm, setBranchAdminForm] = useState<LeaderForm>(EMPTY_LEADER);
  const [leaderErrors,    setLeaderErrors]    = useState<Record<string, string>>({});
  const [roles, setRoles] = useState<ApiRole[]>([]);
  const [leaderEmployees, setLeaderEmployees] = useState<ApiEmployeeOption[]>([]);
  const [inviteAlert, setInviteAlert] = useState<{ type: "warn" | "success"; text: string } | null>(null);
  const [transferConfirm, setTransferConfirm] = useState<
    { employee: ApiEmployeeOption; reportsCount: number; hrForCount: number } | null
  >(null);
  const [transferChecking, setTransferChecking] = useState(false);

  const [editForm, setEditForm] = useState({
    id:             0,
    branch_code:    "",
    branch_name:    "",
    address:        "",
    state:          "",
    city:           "",
    gst_registration: "",
    status:         "Active",
    is_headquarter: false,
    geofencing_enabled:    false,
    latitude:              "",
    longitude:             "",
    allowed_radius_meters: "150",
  });

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [branchesRes, statsRes, distRes, statesRes] = await Promise.all([
        clientApi.get<Envelope<Paginated<Branch>>>(API.branches.list),
        clientApi.get<Envelope<BranchStats>>(API.branches.stats),
        clientApi.get<Envelope<BranchDistribution[]>>(API.branches.distribution),
        clientApi.get<Envelope<StateObj[]>>(API.branches.states),
      ]);
      setBranches(branchesRes.data.data?.results ?? []);
      setStats(statsRes.data.data ?? { total_branches: 0, total_employees: 0, total_active_branches: 0, total_inactive_branches: 0, total_cities: 0 });
      setDistribution(distRes.data.data ?? []);
      setStates(statesRes.data.data ?? []);

      // Best-effort only — a GST registration list issue must never block
      // the branches page itself, so this is fetched and failed silently
      // outside the critical Promise.all above.
      clientApi
        .get<Envelope<Paginated<GSTRegistration>>>(API.settings.gstRegistrations.list, { params: { page_size: 100 } })
        .then(res => setGstRegistrations(res.data.data?.results ?? []))
        .catch(() => {});
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e.message ?? "Failed to load branch data.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (editForm.state) {
      setCitiesLoading(true);
      setCities([]);
      clientApi.get(API.branches.cities(editForm.state))
        .then(res => setCities(res.data?.data ?? []))
        .catch(() => setCities([]))
        .finally(() => setCitiesLoading(false));
    } else {
      setCities([]);
    }
  }, [editForm.state]);

  // Auto-fill the GST Registration when the selected state has exactly one
  // match — no ambiguity, so no need to make the admin pick it explicitly.
  // Never overrides an existing explicit selection (checked inside the
  // updater, not the effect body, so it stays out of the dependency array).
  useEffect(() => {
    const stateName = states.find(s => String(s.id) === editForm.state)?.name;
    if (!stateName) return;
    const matches = gstRegistrations.filter(r => r.state === stateName);
    if (matches.length !== 1) return;
    setEditForm(prev => (prev.gst_registration ? prev : { ...prev, gst_registration: matches[0].id }));
  }, [editForm.state, gstRegistrations, states]);

  useEffect(() => {
    if (modalMode === "add" && editForm.city && editForm.city !== OTHER_CITY) {
      setCodeLoading(true);
      setEditForm(prev => ({ ...prev, branch_code: "" }));
      clientApi.get(API.branches.previewCode, { params: { city_id: editForm.city } })
        .then(res => {
          const d = res.data?.data ?? res.data;
          setEditForm(prev => ({ ...prev, branch_code: d?.branch_code ?? "" }));
        })
        .catch(() => {})
        .finally(() => setCodeLoading(false));
    }
  }, [editForm.city, modalMode]);

  // Preview the branch code for a not-yet-created city (debounced on the typed name).
  useEffect(() => {
    if (modalMode !== "add" || editForm.city !== OTHER_CITY) return;
    if (newCityRef.current) clearTimeout(newCityRef.current);
    const name = newCityName.trim();
    if (!CITY_NAME_RE.test(name)) {
      setCodeLoading(false);
      setEditForm(prev => ({ ...prev, branch_code: "" }));
      return;
    }
    setCodeLoading(true);
    newCityRef.current = setTimeout(() => {
      clientApi.get(API.branches.previewCode, { params: { city_name: name } })
        .then(res => {
          const d = res.data?.data ?? res.data;
          setEditForm(prev => ({ ...prev, branch_code: d?.branch_code ?? "" }));
        })
        .catch(() => {})
        .finally(() => setCodeLoading(false));
    }, 400);
  }, [editForm.city, newCityName, modalMode]);

  const validate = () => {
    const errs: Record<string, string> = {};
    const name = editForm.branch_name.trim();
    const addr = editForm.address.trim();

    if (!editForm.state)       errs.state       = "Please select a state.";
    if (!editForm.city)        errs.city        = "Please select a city.";
    else if (editForm.city === OTHER_CITY) {
      const cityName = newCityName.trim();
      if (!cityName)                       errs.new_city_name = "Please enter a city name.";
      else if (!CITY_NAME_RE.test(cityName)) errs.new_city_name = "City name may only contain letters, spaces, hyphens and apostrophes.";
    }
    if (!name)                 errs.branch_name = "Branch name is required.";
    else if (name.length > 200) errs.branch_name = "Branch name must be under 200 characters.";
    else if (!BRANCH_NAME_RE.test(name))
                                errs.branch_name = "Branch name may only contain letters, numbers, spaces, & - and . characters.";
    if (!addr)                 errs.address     = "Address is required.";
    if (codeLoading)           errs.branch_code = "Branch code is still generating, please wait.";

    if (editForm.state && !editForm.gst_registration) {
      const stateName = states.find(s => String(s.id) === editForm.state)?.name;
      const matchCount = stateName ? gstRegistrations.filter(r => r.state === stateName).length : 0;
      if (matchCount > 1) {
        errs.gst_registration = `${stateName} has ${matchCount} GST registrations on file — select which one this branch uses.`;
      }
    }
    if (modalMode === "add" && !editForm.branch_code && !codeLoading)
                               errs.branch_code = "Branch code could not be generated. Try re-selecting the city.";

    if (editForm.geofencing_enabled) {
      const lat = editForm.latitude.trim();
      const lon = editForm.longitude.trim();

      if (!lat && !lon) {
        errs.latitude = "Latitude and longitude are required to enable geofencing.";
      } else if (!lat || !lon) {
        if (!lat) errs.latitude  = "Both latitude and longitude must be provided together.";
        if (!lon) errs.longitude = "Both latitude and longitude must be provided together.";
      } else {
        if (isNaN(Number(lat))) errs.latitude  = "Latitude must be a valid number.";
        if (isNaN(Number(lon))) errs.longitude = "Longitude must be a valid number.";
      }

      const radius = editForm.allowed_radius_meters.trim();
      if (!radius) errs.allowed_radius_meters = "Allowed radius is required.";
      else if (isNaN(Number(radius)) || Number(radius) < 10 || Number(radius) > 5000)
                    errs.allowed_radius_meters = "Allowed radius must be between 10 and 5000 metres.";
    }

    return errs;
  };

  // Only validates a leader row if the admin actually started filling it in —
  // an untouched row is simply skipped, not an error.
  const validateLeaders = () => {
    const errs: Record<string, string> = {};
    const f = branchAdminForm;
    if (isLeaderActive(f)) {
      if (f.mode === "existing") {
        if (!f.employeeId) errs.branchAdminEmployee = "Select an employee.";
      } else {
        if (!f.name.trim())        errs.branchAdminName        = "Name is required.";
        if (!f.email.trim())       errs.branchAdminEmail       = "Email is required.";
        else if (!EMAIL_RE.test(f.email.trim())) errs.branchAdminEmail = "Enter a valid email.";
        if (!f.designation.trim()) errs.branchAdminDesignation = "Designation is required.";
      }
    }
    return errs;
  };

  // Two ways to fill the leadership slot:
  //  - "existing": re-roles/re-branches an employee who already works here —
  //    a transfer, not a new hire, so it only ever touches role + branch.
  //  - "new": reuses the same employee-creation endpoint/invite mechanism as
  //    the Employees page — same generated temp password, same
  //    must-change-password welcome email — pre-scoped to the branch that
  //    was just created. Designation is pre-filled with a sensible default
  //    but shown and editable, not decided silently. No department — a
  //    Branch Admin oversees every department in the branch, not one, so
  //    the backend doesn't require it for this role (see
  //    EmployeeListCreateView.post's department_required check).
  const applyLeaderRole = async (f: LeaderForm, branchName: string) => {
    // Found by capability, not by name — a role can be renamed from Settings
    // at any time, so matching a literal string like "branch_admin" would
    // silently break. Also excludes settings.edit roles: a role that happens
    // to carry both can_manage_branch and settings.edit is company-wide, not
    // branch-scoped, and this picker must never hand out that much access.
    const role = roles.find(r => r.can_manage_branch && !r.permissions.includes("settings.edit"));
    if (!role) throw new Error("No Company Code Admin role is set up for this company yet.");

    if (f.mode === "existing") {
      await clientApi.put(API.employees.detail(f.employeeId), {
        role: role.name,
        branch: branchName,
      });
      return;
    }

    const name = f.name.trim();
    const splitAt = name.indexOf(" ");
    const first_name = splitAt === -1 ? name : name.slice(0, splitAt);
    const last_name  = splitAt === -1 ? name : name.slice(splitAt + 1).trim() || name;
    await clientApi.post(API.employees.list, {
      first_name, last_name,
      email: f.email.trim(),
      role: role.id,
      designation: f.designation.trim(),
      branch: branchName,
      date_of_joining: new Date().toISOString().slice(0, 10),
    });
  };

  const doSave = async () => {
    setSaveError(null);
    setHqConfirm(false);
    const payload: Record<string, unknown> = {
      branch_name:    editForm.branch_name.trim(),
      address:        editForm.address.trim(),
      state:          editForm.state,
      gst_registration: editForm.gst_registration || null,
      status:         editForm.status,
      is_headquarter: editForm.is_headquarter,
      geofencing_enabled:    editForm.geofencing_enabled,
      latitude:              editForm.geofencing_enabled ? Number(editForm.latitude)  : null,
      longitude:             editForm.geofencing_enabled ? Number(editForm.longitude) : null,
      // allowed_radius_meters is a non-nullable field on the backend (default 150) —
      // unlike latitude/longitude, it can't be sent as null when geofencing is off.
      allowed_radius_meters: editForm.geofencing_enabled ? Number(editForm.allowed_radius_meters) : 150,
    };
    if (editForm.city === OTHER_CITY) {
      payload.new_city_name = newCityName.trim();
    } else {
      payload.city = editForm.city;
    }
    setSaving(true);
    try {
      if (modalMode === "edit") {
        await clientApi.patch(API.branches.detail(editForm.id), payload);
      } else {
        await clientApi.post(API.branches.list, payload);
      }
      const branchName = editForm.branch_name.trim();
      setModalMode(null);
      fetchData();

      // Leadership assignment runs after the branch is already saved and the
      // modal is closed — the branch itself must never be blocked or rolled
      // back by a problem with this optional, secondary step.
      if (modalMode === "add" && isLeaderActive(branchAdminForm)) {
        try {
          await applyLeaderRole(branchAdminForm, branchName);
          setInviteAlert({
            type: "success",
            text: branchAdminForm.mode === "new"
              ? `${branchName} was created and its Company Code Admin was invited by email.`
              : `${branchName} was created and its Company Code Admin was assigned.`,
          });
        } catch (e) {
          setInviteAlert({
            type: "warn",
            text: `${branchName} was created, but assigning its Company Code Admin failed: ${(e as { message?: string })?.message ?? "unknown error"} — use the Employees page instead.`,
          });
        }
        setBranchAdminForm(EMPTY_LEADER);
      }
    } catch (err: unknown) {
      const e = err as { message?: string };
      setSaveError(e.message ?? "Failed to save branch.");
    } finally {
      setSaving(false);
    }
  };

  const handleSave = async () => {
    setSaveError(null);
    const errs = validate();
    const leaderErrs = modalMode === "add" ? validateLeaders() : {};
    if (Object.keys(errs).length > 0 || Object.keys(leaderErrs).length > 0) {
      setFieldErrors(errs);
      setLeaderErrors(leaderErrs);
      return;
    }
    setFieldErrors({});
    setLeaderErrors({});
    const existingHq = branches.find(
      b => b.is_headquarter && b.id !== editForm.id
    );
    if (editForm.is_headquarter && existingHq) {
      setHqConfirm(true);
      return;
    }

    // Transferring a real, already-employed person is a bigger deal than
    // inviting someone new — confirm it explicitly, and warn if they
    // currently manage people or are someone's HR (those relationships
    // don't get reassigned automatically by this transfer).
    if (modalMode === "add" && branchAdminForm.mode === "existing" && branchAdminForm.employeeId) {
      const employee = leaderEmployees.find(e => e.id === branchAdminForm.employeeId);
      if (employee) {
        setTransferChecking(true);
        try {
          // reporting_manager_id / hr_id filter on the FK's real primary key
          // (a UUID), not the human-readable employee_id code used elsewhere.
          const [reportsRes, hrRes] = await Promise.all([
            clientApi.get<{ data: { count: number } }>(API.employees.list, {
              params: { reporting_manager_id: employee.uuid, page_size: 1 },
            }),
            clientApi.get<{ data: { count: number } }>(API.employees.list, {
              params: { hr_id: employee.uuid, page_size: 1 },
            }),
          ]);
          setTransferConfirm({
            employee,
            reportsCount: reportsRes.data.data?.count ?? 0,
            hrForCount: hrRes.data.data?.count ?? 0,
          });
        } catch {
          // The check itself failing shouldn't block the transfer — just
          // confirm without the relationship counts.
          setTransferConfirm({ employee, reportsCount: 0, hrForCount: 0 });
        } finally {
          setTransferChecking(false);
        }
        return;
      }
    }

    doSave();
  };

  const doDelete = async () => {
    if (!deleteConfirm) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await clientApi.delete(API.branches.detail(deleteConfirm.id));
      setDeleteConfirm(null);
      fetchData();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setDeleteError(e.message ?? "Failed to delete branch.");
    } finally {
      setDeleting(false);
    }
  };

  // Non-superusers are scoped to their assigned branch; system_admin sees all.
  const visibleBranches = isHrAdmin
    ? branches.filter(b => b.branch_name === user?.branch)
    : branches;

  const selectedStateName = states.find(s => String(s.id) === editForm.state)?.name;
  const gstOptionsForState = selectedStateName
    ? gstRegistrations.filter(r => r.state === selectedStateName)
    : [];
  const missingGstForState = !!selectedStateName && gstOptionsForState.length === 0;
  // Only force a choice when it's genuinely ambiguous — one match can be
  // used without making the admin pick it explicitly.
  const gstChoiceRequired = gstOptionsForState.length > 1;

  if (isLoading && branches.length === 0) {
    return <div className="p-8 text-center text-[var(--on-variant)]">Loading Company Codes...</div>;
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Company Codes</h1>
          <p className="page-sub">{isHrAdmin ? "Your Company Code details" : "Manage all Company Code locations"}</p>
        </div>
        {canEdit && (
          <div className="page-actions">
            <button className="btn btn-filled" onClick={() => {
              setSaveError(null);
              setModalMode("add");
              setFieldErrors({});
              setLeaderErrors({});
              setBranchAdminForm(EMPTY_LEADER);
              setTransferConfirm(null);
              setNewCityName("");
              setEditForm({
                id: 0, branch_code: "", branch_name: "", address: "", state: "", city: "", gst_registration: "", status: "active", is_headquarter: false,
                geofencing_enabled: false, latitude: "", longitude: "", allowed_radius_meters: "150",
              });
              Promise.allSettled([
                clientApi.get<{ data: { results: ApiRole[] } }>(API.roles.list,        { params: { page_size: 100 } }),
                clientApi.get<{ data: { results: ApiEmployeeOption[] } }>(API.employees.list, { params: { page_size: 50, status: "active" } }),
              ]).then(([r, e]) => {
                setRoles(r.status === "fulfilled" ? r.value.data.data.results : []);
                // Never offer the company's own system_admin(s) here — this
                // picker only ever re-roles someone into branch_admin, and a
                // system_admin must never be silently demoted by picking them
                // by accident (same exclusion AddEmployeeModal already
                // applies to the role dropdown itself).
                setLeaderEmployees(
                  e.status === "fulfilled"
                    ? (e.value.data.data?.results ?? []).filter(emp => emp.role !== "system_admin")
                    : [],
                );
              });
            }}>
              <i className="ti ti-plus" /> Add Company Code
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="alert alert-error mb-24">
          <i className="ti ti-alert-circle" /> {error}
        </div>
      )}

      {inviteAlert && (
        <div className={`alert ${inviteAlert.type === "warn" ? "alert-warn" : "alert-success"} mb-24`}>
          <i className={`ti ${inviteAlert.type === "warn" ? "ti-alert-triangle" : "ti-check"}`} />
          <span style={{ flex: 1 }}>{inviteAlert.text}</span>
          <button
            type="button"
            onClick={() => setInviteAlert(null)}
            style={{ background: "none", border: "none", cursor: "pointer", color: "inherit", padding: 0, marginLeft: 12 }}
            aria-label="Dismiss"
          >
            <i className="ti ti-x" />
          </button>
        </div>
      )}

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon si-primary"><i className="ti ti-building" /></div>
          <div className="stat-label">Total Company Codes</div>
          <div className="stat-value">{stats.total_branches}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-success"><i className="ti ti-users" /></div>
          <div className="stat-label">Total Workforce</div>
          <div className="stat-value">{stats.total_employees}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-info"><i className="ti ti-map-pin" /></div>
          <div className="stat-label">Cities Covered</div>
          <div className="stat-value">{stats.total_cities}</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon si-warn"><i className="ti ti-building-skyscraper" /></div>
          <div className="stat-label">Active Company Codes</div>
          <div className="stat-value">{stats.total_active_branches}</div>
        </div>
      </div>

      {visibleBranches.length > 0 ? (
        <div className="grid-2 mb-24">
          {visibleBranches.map(branch => (
            <div key={branch.id} className="card" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
              <div className="card-body" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "16px" }}>
                  <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                    <div style={{ width: "42px", height: "42px", borderRadius: "10px", background: "var(--primary)", color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "20px" }}>
                      <i className="ti ti-building-skyscraper" />
                    </div>
                    <div>
                      <div style={{ fontSize: "14px", fontWeight: 600, color: "var(--on-bg)" }}>{branch.branch_name}</div>
                      <div style={{ fontSize: "12px", color: "var(--on-variant)", marginTop: "2px" }}>{branch.branch_code}</div>
                    </div>
                  </div>
                  {branch.is_headquarter && (
                    <span className="badge" style={{ background: "var(--bg-high)", color: "var(--on-variant)", fontSize: "10px", fontWeight: 600, letterSpacing: "0.04em", padding: "4px 8px" }}>
                      <i className="ti ti-star-filled" style={{ fontSize: "10px", marginRight: "2px", color: "var(--on-variant)" }} /> HEADQUARTER
                    </span>
                  )}
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "8px", marginBottom: "20px", flex: 1 }}>
                  <div style={{ display: "flex", gap: "8px", fontSize: "12px", color: "var(--on-variant)", alignItems: "flex-start" }}>
                    <i className="ti ti-map-pin" style={{ fontSize: "14px", color: "var(--outline)", marginTop: "2px" }} />
                    <span>{branch.address}</span>
                  </div>
                  <div style={{ display: "flex", gap: "8px", fontSize: "12px", color: "var(--on-variant)", alignItems: "center" }}>
                    <i className="ti ti-flag" style={{ fontSize: "14px", color: "var(--outline)" }} />
                    <span>{branch.city_name}, {branch.state_name}</span>
                  </div>
                </div>

                <div style={{ display: "flex", gap: "16px", padding: "12px 16px", background: "var(--bg-low)", borderRadius: "var(--radius)", marginBottom: "16px" }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "11px", color: "var(--on-variant)", marginBottom: "2px" }}>Employees</div>
                    <div style={{ fontSize: "15px", fontWeight: 600, color: "var(--on-bg)" }}>{branch.employees_count}</div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "11px", color: "var(--on-variant)", marginBottom: "2px" }}>Status</div>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "13px", fontWeight: 500, color: branch.status === "active" ? "var(--success)" : "var(--on-variant)" }}>
                      <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: branch.status === "active" ? "var(--success)" : "var(--outline)" }} />
                      {branch.status.charAt(0).toUpperCase() + branch.status.slice(1)}
                    </div>
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: "11px", color: "var(--on-variant)", marginBottom: "2px" }}>Geofencing</div>
                    <span className={`badge ${geofenceBadge(branch).cls}`}>{geofenceBadge(branch).label}</span>
                    {branch.geofencing_enabled && branch.has_coordinates && (
                      <div style={{ fontSize: "11px", color: "var(--on-variant)", marginTop: "4px" }}>
                        {branch.allowed_radius_meters} m radius<br />
                        {branch.latitude}, {branch.longitude}
                      </div>
                    )}
                  </div>
                </div>

                {canEdit && (
                  <div style={{ display: "flex", gap: "8px", justifyContent: "center", width: "100%" }}>
                    <button
                      className="btn btn-ghost"
                      style={{ flex: 1, justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "8px 0" }}
                      onClick={() => {
                        setSaveError(null);
                        setFieldErrors({});
                        setLeaderErrors({});
                        setBranchAdminForm(EMPTY_LEADER);
                        setTransferConfirm(null);
                        setModalMode("edit");
                        setNewCityName("");
                        setEditForm({
                          id:             branch.id,
                          branch_code:    branch.branch_code,
                          branch_name:    branch.branch_name,
                          address:        branch.address,
                          state:          branch.state.toString(),
                          city:           branch.city.toString(),
                          gst_registration: branch.gst_registration ?? "",
                          status:         branch.status.toLowerCase(),
                          is_headquarter: branch.is_headquarter,
                          geofencing_enabled:    branch.geofencing_enabled ?? false,
                          latitude:              branch.latitude?.toString() ?? "",
                          longitude:             branch.longitude?.toString() ?? "",
                          allowed_radius_meters: branch.allowed_radius_meters?.toString() ?? "150",
                        });
                      }}
                    >
                      <i className="ti ti-edit" style={{ fontSize: "16px", marginRight: "6px" }} /> Edit
                    </button>
                    <button
                      className="btn btn-ghost"
                      style={{ width: "40px", justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "8px 0", color: "var(--error)" }}
                      onClick={() => { setDeleteError(null); setDeleteConfirm(branch); }}
                      title={`Delete ${branch.branch_name}`}
                      aria-label={`Delete ${branch.branch_name}`}
                    >
                      <i className="ti ti-trash" style={{ fontSize: "16px" }} />
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state mb-24 card">
          <i className="ti ti-building-skyscraper" />
          <h3>No Company Codes Found</h3>
          <p>You haven&apos;t added any Company Codes yet.</p>
        </div>
      )}

      {distribution.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <i className="ti ti-chart-bar" /> Employee Distribution by Company Code
            </div>
          </div>
          <div className="card-body">
            <div style={{ position: "relative", height: "260px", paddingLeft: "40px", paddingBottom: "40px", paddingTop: "20px" }}>
              {/* Y-axis grid lines */}
              <div style={{ position: "absolute", inset: "20px 0 40px 40px", display: "flex", flexDirection: "column-reverse", justifyContent: "space-between" }}>
                {[0, 2, 4, 6, 8].map(val => (
                  <div key={val} style={{ borderBottom: val === 0 ? "1px solid var(--outline)" : "1px dashed var(--outline-v)", position: "relative", width: "100%" }}>
                    <span style={{ position: "absolute", left: "-24px", top: "-8px", fontSize: "11px", color: "var(--on-variant)" }}>{val}</span>
                  </div>
                ))}
              </div>

              {/* Bars */}
              <div style={{ position: "absolute", inset: "20px 0 40px 40px", display: "flex", alignItems: "flex-end", justifyContent: "space-around" }}>
                {distribution.map((dist, i) => {
                  const maxEmp = Math.max(...distribution.map(d => d.employees), 8);
                  const heightPct = (dist.employees / maxEmp) * 100;
                  const colors = ["var(--primary)", "var(--info)", "var(--secondary)", "var(--warn)"];
                  return (
                    <div key={dist.branch_code} style={{ display: "flex", flexDirection: "column", alignItems: "center", height: "100%", justifyContent: "flex-end", zIndex: 1, position: "relative" }}>
                      <div style={{
                        width: "36px",
                        height: `${heightPct}%`,
                        background: colors[i % colors.length],
                        borderRadius: "6px 6px 0 0",
                        transition: "height 0.3s ease",
                        cursor: "pointer"
                      }} title={`${dist.branch}: ${dist.employees} Employees`} />
                      <div style={{ position: "absolute", bottom: "-30px", fontSize: "12px", color: "var(--on-variant)", whiteSpace: "nowrap", textAlign: "center" }}>
                        {dist.branch}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      )}

      {modalMode && (
        <Modal
          title={
            <>
              <i className="ti ti-building-skyscraper" style={{ marginRight: "8px" }} />
              {modalMode === "add" ? "Add New Company Code" : `Edit Company Code: ${editForm.branch_name}`}
            </>
          }
          onClose={() => setModalMode(null)}
          size="lg"
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setModalMode(null)}>Cancel</button>
              <button
                className="btn btn-filled"
                onClick={handleSave}
                disabled={saving || codeLoading || citiesLoading || transferChecking}
              >
                {saving ? (
                  <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite", marginRight: "6px" }} />{modalMode === "add" ? "Creating…" : "Saving…"}</>
                ) : transferChecking ? (
                  <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite", marginRight: "6px" }} />Checking…</>
                ) : codeLoading || citiesLoading ? (
                  <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite", marginRight: "6px" }} />Please wait…</>
                ) : modalMode === "add" ? "Create Branch" : "Save Changes"}
              </button>
            </>
          }
        >
              {saveError && (
                <div className="alert alert-error mb-16">
                  <i className="ti ti-alert-circle" /> {saveError}
                </div>
              )}
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">State/Region *</label>
                  <select
                    className={`field-input field-select${fieldErrors.state ? " field-error" : ""}`}
                    value={editForm.state}
                    onChange={e => {
                      setFieldErrors(prev => { const n = {...prev}; delete n.state; delete n.city; delete n.new_city_name; delete n.gst_registration; return n; });
                      setNewCityName("");
                      setEditForm({ ...editForm, state: e.target.value, city: "", gst_registration: "" });
                    }}
                  >
                    <option value="">Select State</option>
                    {states.map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                  {fieldErrors.state && <p className="field-error-msg">{fieldErrors.state}</p>}
                </div>
                <div className="field-group">
                  <label className="field-label">City *</label>
                  <select
                    className={`field-input field-select${fieldErrors.city ? " field-error" : ""}`}
                    value={editForm.city}
                    onChange={e => {
                      setFieldErrors(prev => { const n = {...prev}; delete n.city; delete n.branch_code; delete n.new_city_name; return n; });
                      if (e.target.value !== OTHER_CITY) setNewCityName("");
                      setEditForm({ ...editForm, city: e.target.value });
                    }}
                    disabled={!editForm.state || citiesLoading}
                  >
                    <option value="">
                      {!editForm.state ? "Select a state first" : citiesLoading ? "Loading cities…" : "Select City"}
                    </option>
                    {cities.map(c => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                    {editForm.state && <option value={OTHER_CITY}>Other (type city name)</option>}
                  </select>
                  {fieldErrors.city && <p className="field-error-msg">{fieldErrors.city}</p>}
                  {editForm.city === OTHER_CITY && (
                    <div style={{ marginTop: "8px" }}>
                      <input
                        type="text"
                        className={`field-input${fieldErrors.new_city_name ? " field-error" : ""}`}
                        value={newCityName}
                        onChange={e => {
                          setFieldErrors(prev => { const n = {...prev}; delete n.new_city_name; delete n.branch_code; return n; });
                          setNewCityName(e.target.value.replace(/[^A-Za-z '-]/g, ""));
                        }}
                        placeholder="Enter new city name"
                        maxLength={100}
                      />
                      {fieldErrors.new_city_name && <p className="field-error-msg">{fieldErrors.new_city_name}</p>}
                    </div>
                  )}
                </div>
              </div>

              {missingGstForState && (
                <div className="alert alert-warn mb-16" style={{ alignItems: "flex-start" }}>
                  <i className="ti ti-alert-triangle" />
                  <div>
                    No GST registration found for <strong>{selectedStateName}</strong> yet — GST registration is
                    state-wise, so this branch will need one on file.{" "}
                    <a href="/dashboard/settings/company" target="_blank" rel="noopener noreferrer" style={{ fontWeight: 600 }}>
                      Add one in Company Profile
                    </a>
                  </div>
                </div>
              )}

              {gstOptionsForState.length > 0 && (
                <div className="field-group mb-16">
                  <label className="field-label">
                    GST Registration {gstChoiceRequired && <span style={{ color: "var(--error)" }}>*</span>}
                  </label>
                  {gstOptionsForState.length === 1 ? (
                    <div style={{ fontSize: 13, color: "var(--on-variant)", display: "flex", alignItems: "center", gap: 6 }}>
                      <i className="ti ti-receipt-tax" style={{ fontSize: 14 }} />
                      <span style={{ fontFamily: "monospace" }}>{gstOptionsForState[0].gstin}</span>
                      <span>({selectedStateName}{gstOptionsForState[0].place_of_business ? ` — ${gstOptionsForState[0].place_of_business}` : ""}) — only one on file, used automatically</span>
                    </div>
                  ) : (
                    <>
                      <select
                        className={`field-input field-select${fieldErrors.gst_registration ? " field-error" : ""}`}
                        value={editForm.gst_registration}
                        onChange={e => {
                          setFieldErrors(prev => { const n = {...prev}; delete n.gst_registration; return n; });
                          setEditForm({ ...editForm, gst_registration: e.target.value });
                        }}
                      >
                        <option value="">Select which GST registration this Company Code uses…</option>
                        {gstOptionsForState.map(r => (
                          <option key={r.id} value={r.id}>
                            {r.gstin}{r.place_of_business ? ` — ${r.place_of_business}` : ""}
                          </option>
                        ))}
                      </select>
                      <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
                        <i className="ti ti-info-circle" style={{ marginRight: 4 }} />
                        {selectedStateName} has {gstOptionsForState.length} GST registrations on file — pick the one this branch&apos;s invoices/documents should use.
                      </div>
                      {fieldErrors.gst_registration && <p className="field-error-msg">{fieldErrors.gst_registration}</p>}
                    </>
                  )}
                </div>
              )}

              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Company Code <span style={{ fontSize: "11px", color: "var(--outline)", fontWeight: 400 }}>(auto-generated)</span></label>
                  <div style={{ position: "relative" }}>
                    <input
                      type="text"
                      className={`field-input${fieldErrors.branch_code ? " field-error" : ""}`}
                      value={codeLoading ? "" : editForm.branch_code}
                      readOnly
                      placeholder={!editForm.city ? "Select a city first" : codeLoading ? "Generating…" : ""}
                      style={{ background: "var(--bg-low)", cursor: "default", paddingRight: codeLoading ? "36px" : undefined }}
                    />
                    {codeLoading && (
                      <span style={{ position: "absolute", right: "10px", top: "50%", transform: "translateY(-50%)", fontSize: "15px", color: "var(--outline)" }}>
                        <i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite" }} />
                      </span>
                    )}
                  </div>
                  {fieldErrors.branch_code && <p className="field-error-msg">{fieldErrors.branch_code}</p>}
                  {editForm.branch_code && !codeLoading && !fieldErrors.branch_code && (
                    <div style={{ fontSize: "11px", color: "var(--on-variant)", marginTop: "4px" }}>
                      <i className="ti ti-info-circle" style={{ marginRight: "4px" }} />
                      Additional branches in the same city get suffixed automatically (e.g. MUM-01, MUM-02)
                    </div>
                  )}
                </div>
                <div className="field-group">
                  <label className="field-label">Company Code Name *</label>
                  <input
                    type="text"
                    className={`field-input${fieldErrors.branch_name ? " field-error" : ""}`}
                    value={editForm.branch_name}
                    onChange={e => {
                      setFieldErrors(prev => { const n = {...prev}; delete n.branch_name; return n; });
                      setEditForm({ ...editForm, branch_name: e.target.value.replace(/[^A-Za-z0-9 &.-]/g, "") });
                    }}
                    placeholder="e.g. Bengaluru HQ"
                    maxLength={200}
                  />
                  {fieldErrors.branch_name && <p className="field-error-msg">{fieldErrors.branch_name}</p>}
                </div>
              </div>
              <div className="form-row">
                <div className="field-group">
                  <label className="field-label">Address *</label>
                  <textarea
                    className={`field-input${fieldErrors.address ? " field-error" : ""}`}
                    value={editForm.address}
                    onChange={e => {
                      setFieldErrors(prev => { const n = {...prev}; delete n.address; return n; });
                      setEditForm({ ...editForm, address: e.target.value });
                    }}
                    placeholder="Full Company Code address"
                  />
                  {fieldErrors.address && <p className="field-error-msg">{fieldErrors.address}</p>}
                </div>
              </div>

              {modalMode === "add" && (
                <div style={{ marginTop: "4px", marginBottom: "20px", paddingTop: "18px", paddingBottom: "4px", borderTop: "1px solid var(--outline-v)" }}>
                  <div style={{ fontSize: "13px", fontWeight: 600, color: "var(--on-bg)", marginBottom: "14px" }}>
                    Assign Company Code Admin <span style={{ fontWeight: 400, color: "var(--on-variant)" }}>(optional)</span>
                  </div>
                  <LeaderFields
                    label="Company Code Admin" form={branchAdminForm} setForm={setBranchAdminForm}
                    employees={leaderEmployees} errors={leaderErrors} prefix="branchAdmin"
                  />
                </div>
              )}

              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Status *</label>
                  <select
                    className="field-input field-select"
                    value={editForm.status}
                    onChange={e => setEditForm({ ...editForm, status: e.target.value })}
                  >
                    <option value="active">Active</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </div>
                <div className="field-group" style={{ display: "flex", alignItems: "flex-end", paddingBottom: "2px" }}>
                  <label className="module-check">
                    <input
                      type="checkbox"
                      checked={editForm.is_headquarter}
                      onChange={e => setEditForm({ ...editForm, is_headquarter: e.target.checked })}
                    />
                    <span>Mark as Headquarter</span>
                  </label>
                </div>
              </div>

              <div className="form-row">
                <div className="field-group" style={{ paddingBottom: "2px" }}>
                  <ToggleSwitch
                    label="Enable Geofencing"
                    checked={editForm.geofencing_enabled}
                    onChange={checked => {
                      setFieldErrors(prev => { const n = {...prev}; delete n.latitude; delete n.longitude; delete n.allowed_radius_meters; return n; });
                      setEditForm({ ...editForm, geofencing_enabled: checked });
                    }}
                  />
                </div>
              </div>

              {editForm.geofencing_enabled && (
                <>
                  <div className="form-row cols-2">
                    <div className="field-group">
                      <label className="field-label">Latitude *</label>
                      <input
                        type="number"
                        step="any"
                        className={`field-input${fieldErrors.latitude ? " field-error" : ""}`}
                        value={editForm.latitude}
                        onChange={e => {
                          setFieldErrors(prev => { const n = {...prev}; delete n.latitude; return n; });
                          setEditForm({ ...editForm, latitude: e.target.value });
                        }}
                        placeholder="e.g. 19.0760"
                      />
                      {fieldErrors.latitude && <p className="field-error-msg">{fieldErrors.latitude}</p>}
                    </div>
                    <div className="field-group">
                      <label className="field-label">Longitude *</label>
                      <input
                        type="number"
                        step="any"
                        className={`field-input${fieldErrors.longitude ? " field-error" : ""}`}
                        value={editForm.longitude}
                        onChange={e => {
                          setFieldErrors(prev => { const n = {...prev}; delete n.longitude; return n; });
                          setEditForm({ ...editForm, longitude: e.target.value });
                        }}
                        placeholder="e.g. 72.8777"
                      />
                      {fieldErrors.longitude && <p className="field-error-msg">{fieldErrors.longitude}</p>}
                    </div>
                  </div>
                  <div style={{ fontSize: "11px", color: "var(--on-variant)", marginTop: "-8px", marginBottom: "16px" }}>
                    <i className="ti ti-info-circle" style={{ marginRight: "4px" }} />
                    Enter the GPS coordinates of the office entrance. Use Google Maps — right-click the location and copy the coordinates.
                  </div>

                  <div className="form-row">
                    <div className="field-group">
                      <label className="field-label">Allowed Radius (metres) *</label>
                      <input
                        type="number"
                        min={10}
                        max={5000}
                        className={`field-input${fieldErrors.allowed_radius_meters ? " field-error" : ""}`}
                        value={editForm.allowed_radius_meters}
                        onChange={e => {
                          setFieldErrors(prev => { const n = {...prev}; delete n.allowed_radius_meters; return n; });
                          setEditForm({ ...editForm, allowed_radius_meters: e.target.value });
                        }}
                      />
                      {fieldErrors.allowed_radius_meters && <p className="field-error-msg">{fieldErrors.allowed_radius_meters}</p>}
                    </div>
                  </div>
                </>
              )}
        </Modal>
      )}

      {transferConfirm && (
        <Modal
          title={
            <>
              <i className="ti ti-arrows-right-left" style={{ marginRight: "8px", color: "var(--primary)" }} />
              Move {transferConfirm.employee.full_name}?
            </>
          }
          onClose={() => setTransferConfirm(null)}
          maxWidth="440px"
          zIndex={1010}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setTransferConfirm(null)}>Cancel</button>
              <button
                className="btn btn-filled"
                onClick={() => { setTransferConfirm(null); doSave(); }}
              >
                Yes, Move Them
              </button>
            </>
          }
        >
          <p style={{ fontSize: "14px", color: "var(--on-variant)", lineHeight: 1.6, marginBottom: (transferConfirm.reportsCount > 0 || transferConfirm.hrForCount > 0) ? "14px" : 0 }}>
            <strong>{transferConfirm.employee.full_name}</strong> currently belongs to{" "}
            <strong>{transferConfirm.employee.branch || "no Company Code"}</strong>. This will move them to the new Company Code
            and change their role to Company Code Admin.
          </p>
          {(transferConfirm.reportsCount > 0 || transferConfirm.hrForCount > 0) && (
            <div className="alert alert-warn">
              <i className="ti ti-alert-triangle" />
              <div>
                {transferConfirm.reportsCount > 0 && (
                  <div>They currently manage {transferConfirm.reportsCount} {transferConfirm.reportsCount === 1 ? "employee" : "employees"} — that reporting line won&apos;t be reassigned automatically.</div>
                )}
                {transferConfirm.hrForCount > 0 && (
                  <div>They&apos;re the assigned HR for {transferConfirm.hrForCount} {transferConfirm.hrForCount === 1 ? "employee" : "employees"} — that assignment won&apos;t be reassigned automatically.</div>
                )}
              </div>
            </div>
          )}
        </Modal>
      )}

      {hqConfirm && (
        <Modal
          title={
            <>
              <i className="ti ti-alert-triangle" style={{ marginRight: "8px", color: "var(--warn)" }} />
              Change Headquarter?
            </>
          }
          onClose={() => setHqConfirm(false)}
          maxWidth="420px"
          zIndex={1010}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setHqConfirm(false)}>Cancel</button>
              <button className="btn btn-filled" onClick={doSave}>Yes, Change HQ</button>
            </>
          }
        >
          <p style={{ fontSize: "14px", color: "var(--on-variant)", lineHeight: 1.6 }}>
            Another branch is already marked as the headquarter. Setting this branch as HQ will remove the HQ status from the existing one. Do you want to continue?
          </p>
        </Modal>
      )}

      {deleteConfirm && (
        <Modal
          title={
            <>
              <i className="ti ti-alert-triangle" style={{ marginRight: "8px", color: "var(--error)" }} />
              Delete Company Code?
            </>
          }
          onClose={() => setDeleteConfirm(null)}
          closeDisabled={deleting}
          maxWidth="420px"
          zIndex={1010}
          footer={
            <>
              <button className="btn btn-ghost" onClick={() => setDeleteConfirm(null)} disabled={deleting}>Cancel</button>
              <button
                className="btn btn-filled"
                style={{ background: "var(--error)" }}
                onClick={doDelete}
                disabled={deleting}
              >
                {deleting
                  ? <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite", marginRight: "6px" }} />Deleting…</>
                  : "Yes, Delete"}
              </button>
            </>
          }
        >
          {deleteError && (
            <div className="alert alert-error mb-16">
              <i className="ti ti-alert-circle" /> {deleteError}
            </div>
          )}
          <p style={{ fontSize: "14px", color: "var(--on-variant)", lineHeight: 1.6 }}>
            Are you sure you want to delete <strong>{deleteConfirm.branch_name}</strong>? This action cannot be undone.
          </p>
        </Modal>
      )}
    </>
  );
}

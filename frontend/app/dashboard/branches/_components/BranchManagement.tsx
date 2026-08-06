"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";

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

function ToggleSwitch({ checked, onChange, label }: { checked: boolean; onChange: (checked: boolean) => void; label: string }) {
  return (
    <label style={{ display: "inline-flex", alignItems: "center", gap: "10px", cursor: "pointer" }}>
      <span
        onClick={() => onChange(!checked)}
        style={{
          position: "relative", width: "38px", height: "22px", borderRadius: "11px", flexShrink: 0,
          background: checked ? "var(--primary)" : "var(--outline-v)", transition: "background 0.15s",
        }}
      >
        <span
          style={{
            position: "absolute", top: "2px", left: checked ? "18px" : "2px",
            width: "18px", height: "18px", borderRadius: "50%", background: "#fff",
            boxShadow: "0 1px 3px rgba(0,0,0,0.3)", transition: "left 0.15s",
          }}
        />
      </span>
      <span style={{ fontSize: "13px", fontWeight: 500, color: "var(--on-bg)" }}>{label}</span>
    </label>
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

const OTHER_CITY = "__other__";
const BRANCH_NAME_RE = /^[A-Za-z0-9](?:[A-Za-z0-9 &\-.]*[A-Za-z0-9])?$/;
const CITY_NAME_RE   = /^[A-Za-z]+(?:[ '-][A-Za-z]+)*$/;

export default function BranchManagement() {
  const user      = useCurrentUser();
  const canEdit   = usePermission("settings.edit");
  const isHrAdmin = !user?.is_superuser && !!user?.branch;

  const [branches, setBranches] = useState<Branch[]>([]);
  const [stats, setStats] = useState<BranchStats>({ total_branches: 0, total_employees: 0, total_active_branches: 0, total_inactive_branches: 0, total_cities: 0 });
  const [distribution, setDistribution] = useState<BranchDistribution[]>([]);
  
  const [states, setStates] = useState<StateObj[]>([]);
  const [cities, setCities] = useState<CityObj[]>([]);
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

  const [editForm, setEditForm] = useState({
    id:             0,
    branch_code:    "",
    branch_name:    "",
    address:        "",
    state:          "",
    city:           "",
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

  const doSave = async () => {
    setSaveError(null);
    setHqConfirm(false);
    const payload: Record<string, unknown> = {
      branch_name:    editForm.branch_name.trim(),
      address:        editForm.address.trim(),
      state:          editForm.state,
      status:         editForm.status,
      is_headquarter: editForm.is_headquarter,
      geofencing_enabled:    editForm.geofencing_enabled,
      latitude:              editForm.geofencing_enabled ? Number(editForm.latitude)  : null,
      longitude:             editForm.geofencing_enabled ? Number(editForm.longitude) : null,
      allowed_radius_meters: editForm.geofencing_enabled ? Number(editForm.allowed_radius_meters) : null,
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
      setModalMode(null);
      fetchData();
    } catch (err: unknown) {
      const e = err as { message?: string };
      setSaveError(e.message ?? "Failed to save branch.");
    } finally {
      setSaving(false);
    }
  };

  const handleSave = () => {
    setSaveError(null);
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setFieldErrors(errs);
      return;
    }
    setFieldErrors({});
    const existingHq = branches.find(
      b => b.is_headquarter && b.id !== editForm.id
    );
    if (editForm.is_headquarter && existingHq) {
      setHqConfirm(true);
      return;
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

  if (isLoading && branches.length === 0) {
    return <div className="p-8 text-center text-[var(--on-variant)]">Loading branches...</div>;
  }

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">Branches</h1>
          <p className="page-sub">{isHrAdmin ? "Your branch details" : "Manage all company branch locations"}</p>
        </div>
        {canEdit && (
          <div className="page-actions">
            <button className="btn btn-filled" onClick={() => {
              setSaveError(null);
              setModalMode("add");
              setFieldErrors({});
              setNewCityName("");
              setEditForm({
                id: 0, branch_code: "", branch_name: "", address: "", state: "", city: "", status: "active", is_headquarter: false,
                geofencing_enabled: false, latitude: "", longitude: "", allowed_radius_meters: "150",
              });
            }}>
              <i className="ti ti-plus" /> Add Branch
            </button>
          </div>
        )}
      </div>

      {error && (
        <div className="alert alert-error mb-24">
          <i className="ti ti-alert-circle" /> {error}
        </div>
      )}

      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon si-primary"><i className="ti ti-building" /></div>
          <div className="stat-label">Total Branches</div>
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
          <div className="stat-label">Active Branches</div>
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
                        setModalMode("edit");
                        setNewCityName("");
                        setEditForm({
                          id:             branch.id,
                          branch_code:    branch.branch_code,
                          branch_name:    branch.branch_name,
                          address:        branch.address,
                          state:          branch.state.toString(),
                          city:           branch.city.toString(),
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
          <h3>No Branches Found</h3>
          <p>You haven&apos;t added any branches yet.</p>
        </div>
      )}

      {distribution.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">
              <i className="ti ti-chart-bar" /> Employee Distribution by Branch
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
        <div className="modal-overlay open">
          <div className="modal modal-lg">
            <div className="modal-header">
              <div className="modal-title">
                <i className="ti ti-building-skyscraper" style={{ marginRight: "8px" }} />
                {modalMode === "add" ? "Add New Branch" : `Edit Branch: ${editForm.branch_name}`}
              </div>
              <button className="modal-close" onClick={() => setModalMode(null)}>
                <i className="ti ti-x" />
              </button>
            </div>
            <div className="modal-body">
              {saveError && (
                <div className="alert alert-error mb-16">
                  <i className="ti ti-alert-circle" /> {saveError}
                </div>
              )}
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">State/Region *</label>
                  <select
                    className={`field-input${fieldErrors.state ? " field-error" : ""}`}
                    value={editForm.state}
                    onChange={e => {
                      setFieldErrors(prev => { const n = {...prev}; delete n.state; delete n.city; delete n.new_city_name; return n; });
                      setNewCityName("");
                      setEditForm({ ...editForm, state: e.target.value, city: "" });
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
                    className={`field-input${fieldErrors.city ? " field-error" : ""}`}
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
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Branch Code <span style={{ fontSize: "11px", color: "var(--outline)", fontWeight: 400 }}>(auto-generated)</span></label>
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
                  <label className="field-label">Branch Name *</label>
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
                    placeholder="Full branch address"
                  />
                  {fieldErrors.address && <p className="field-error-msg">{fieldErrors.address}</p>}
                </div>
              </div>
              <div className="form-row cols-2">
                <div className="field-group">
                  <label className="field-label">Status *</label>
                  <select
                    className="field-input"
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
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setModalMode(null)}>Cancel</button>
              <button
                className="btn btn-filled"
                onClick={handleSave}
                disabled={saving || codeLoading || citiesLoading}
              >
                {saving ? (
                  <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite", marginRight: "6px" }} />{modalMode === "add" ? "Creating…" : "Saving…"}</>
                ) : codeLoading || citiesLoading ? (
                  <><i className="ti ti-loader-2" style={{ animation: "spin 1s linear infinite", marginRight: "6px" }} />Please wait…</>
                ) : modalMode === "add" ? "Create Branch" : "Save Changes"}
              </button>
            </div>
          </div>
        </div>
      )}

      {hqConfirm && (
        <div className="modal-overlay open" style={{ zIndex: 1010 }}>
          <div className="modal" style={{ maxWidth: "420px" }}>
            <div className="modal-header">
              <div className="modal-title">
                <i className="ti ti-alert-triangle" style={{ marginRight: "8px", color: "var(--warn)" }} />
                Change Headquarter?
              </div>
            </div>
            <div className="modal-body">
              <p style={{ fontSize: "14px", color: "var(--on-variant)", lineHeight: 1.6 }}>
                Another branch is already marked as the headquarter. Setting this branch as HQ will remove the HQ status from the existing one. Do you want to continue?
              </p>
            </div>
            <div className="modal-footer">
              <button className="btn btn-ghost" onClick={() => setHqConfirm(false)}>Cancel</button>
              <button className="btn btn-filled" onClick={doSave}>Yes, Change HQ</button>
            </div>
          </div>
        </div>
      )}

      {deleteConfirm && (
        <div className="modal-overlay open" style={{ zIndex: 1010 }}>
          <div className="modal" style={{ maxWidth: "420px" }}>
            <div className="modal-header">
              <div className="modal-title">
                <i className="ti ti-alert-triangle" style={{ marginRight: "8px", color: "var(--error)" }} />
                Delete Branch?
              </div>
              <button className="modal-close" onClick={() => setDeleteConfirm(null)} disabled={deleting}>
                <i className="ti ti-x" />
              </button>
            </div>
            <div className="modal-body">
              {deleteError && (
                <div className="alert alert-error mb-16">
                  <i className="ti ti-alert-circle" /> {deleteError}
                </div>
              )}
              <p style={{ fontSize: "14px", color: "var(--on-variant)", lineHeight: 1.6 }}>
                Are you sure you want to delete <strong>{deleteConfirm.branch_name}</strong>? This action cannot be undone.
              </p>
            </div>
            <div className="modal-footer">
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
            </div>
          </div>
        </div>
      )}
    </>
  );
}

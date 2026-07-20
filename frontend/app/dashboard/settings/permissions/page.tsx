"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { usePermission } from "@/hooks/usePermission";
import AddRoleModal  from "./_components/AddRoleModal";
import EditRoleModal from "./_components/EditRoleModal";
import {
  actionsForModule, moduleDisplayName, slugifyName,
  type ApiRole, type PermissionsMap, type RoleForm,
} from "./_data";

export default function RolesPermissionsPage() {
  const router   = useRouter();
  const canEdit  = usePermission("settings.edit");

  const [roles,          setRoles]          = useState<ApiRole[]>([]);
  const [permissionsMap, setPermissionsMap] = useState<PermissionsMap>({});
  const [loading,        setLoading]        = useState(true);
  const [error,          setError]          = useState<string | null>(null);
  const [showAddModal,   setShowAddModal]   = useState(false);
  const [editingRole,    setEditingRole]    = useState<ApiRole | null>(null);
  const [saving,         setSaving]         = useState(false);
  const [togglingId,     setTogglingId]     = useState<number | null>(null);
  const [saveMsg,        setSaveMsg]        = useState<string | null>(null);

  const modules = Object.keys(permissionsMap);

  function apiErr(err: unknown): string {
    const e = err as { response?: { data?: { message?: string } }; message?: string };
    return e.response?.data?.message ?? e.message ?? "Action failed.";
  }

  // ─── Data loading ──────────────────────────────────────────────────────────

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    setError(null);
    try {
      const [rolesRes, permsRes] = await Promise.all([
        clientApi.get(API.roles.list),
        clientApi.get(API.permissions.list),
      ]);
      setRoles(rolesRes.data.data?.results ?? []);
      setPermissionsMap(permsRes.data.data?.results ?? {});
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e.message ?? "Failed to load data");
    } finally {
      setLoading(false);
    }
  }

  // ─── Add role ──────────────────────────────────────────────────────────────

  async function addRole(form: RoleForm) {
    setSaving(true);
    try {
      await clientApi.post(API.roles.list, {
        name:                slugifyName(form.display_name),
        display_name:        form.display_name,
        is_active:           true,
        permission_codenames: form.permission_codenames,
      });
      const res = await clientApi.get(API.roles.list);
      setRoles(res.data.data?.results ?? []);
      setShowAddModal(false);
      setSaveMsg("Role created successfully.");
    } catch (err: unknown) {
      alert(apiErr(err));
    } finally {
      setSaving(false);
    }
  }

  // ─── Edit role ─────────────────────────────────────────────────────────────

  async function editRole(form: RoleForm) {
    if (!editingRole) return;
    setSaving(true);
    try {
      await clientApi.put(API.roles.detail(editingRole.id), {
        name:                editingRole.name,       // slug is immutable
        display_name:        form.display_name,
        is_active:           editingRole.is_active,  // toggle handles this separately
        permission_codenames: form.permission_codenames,
      });
      const res = await clientApi.get(API.roles.list);
      setRoles(res.data.data?.results ?? []);
      setEditingRole(null);
      setSaveMsg("Permissions saved. Users in this role must log out and back in for changes to take effect.");
    } catch (err: unknown) {
      alert(apiErr(err));
    } finally {
      setSaving(false);
    }
  }

  // ─── Toggle active ─────────────────────────────────────────────────────────

  async function toggleActive(role: ApiRole) {
    setTogglingId(role.id);
    try {
      await clientApi.patch(API.roles.detail(role.id), { is_active: !role.is_active });
      setRoles(prev =>
        prev.map(r => r.id === role.id ? { ...r, is_active: !r.is_active } : r)
      );
    } catch (err: unknown) {
      const e = err as { message?: string };
      alert(e.message ?? "Failed to update role");
    } finally {
      setTogglingId(null);
    }
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, gap: 10, color: "var(--on-variant)" }}>
        <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "spin 1s linear infinite" }} />
        Loading roles &amp; permissions…
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (error) {
    return (
      <div className="alert alert-error mb-24">
        <i className="ti ti-alert-circle" />
        <div>
          <strong>Failed to load</strong> — {error}
          <div style={{ marginTop: 8 }}>
            <button className="btn btn-ghost btn-sm" onClick={loadData}>Retry</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <div className="page-title">Roles &amp; Permissions</div>
          <div className="page-sub">Control what each role can access across all modules</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
          {canEdit && (
            <button className="btn btn-filled" onClick={() => setShowAddModal(true)}>
              <i className="ti ti-plus" /> Add Role
            </button>
          )}
        </div>
      </div>

      {/* ── Save confirmation banner ─────────────────────────────────────── */}
      {saveMsg && (
        <div className="alert alert-success mb-16" style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <i className="ti ti-circle-check" style={{ flexShrink: 0 }} />
          <div style={{ flex: 1 }}>{saveMsg}</div>
          <button
            onClick={() => setSaveMsg(null)}
            style={{ background: "none", border: "none", cursor: "pointer", padding: 4, color: "inherit" }}
          >
            <i className="ti ti-x" style={{ fontSize: 14 }} />
          </button>
        </div>
      )}

      {/* ── Roles table ──────────────────────────────────────────────────── */}
      <div className="card mb-24">
        <div className="card-header">
          <div className="card-title">
            <i className="ti ti-shield-check" /> All Roles
          </div>
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{roles.length} roles</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Role Name</th>
                <th>Slug</th>
                <th>Permissions</th>
                <th>Users</th>
                <th style={{ width: 120, textAlign: "center" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {roles.map(role => (
                <tr key={role.id}>
                  <td style={{ fontWeight: 600 }}>{role.display_name}</td>
                  <td>
                    <code style={{ fontSize: 11, background: "var(--bg-low)", padding: "2px 6px", borderRadius: 4, color: "var(--on-variant)" }}>
                      {role.name}
                    </code>
                  </td>
                  <td style={{ fontSize: 13, color: "var(--on-variant)" }}>
                    {role.permissions.length} permission{role.permissions.length !== 1 ? "s" : ""}
                  </td>
                  <td>
                    <span className="badge badge-info">{role.user_count} user{role.user_count !== 1 ? "s" : ""}</span>
                  </td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 2 }}>
                      {canEdit ? (
                        <>
                          <button
                            className="btn btn-ghost btn-sm icon-tooltip"
                            onClick={() => setEditingRole(role)}
                            data-tip="Edit role"
                            style={{ padding: "5px 8px" }}
                          >
                            <i className="ti ti-pencil" style={{ fontSize: 16 }} />
                          </button>
                          <button
                            className="btn btn-ghost btn-sm icon-tooltip"
                            onClick={() => toggleActive(role)}
                            disabled={togglingId === role.id}
                            data-tip={role.is_active ? "Active" : "Inactive"}
                            style={{ padding: "5px 8px" }}
                          >
                            {togglingId === role.id ? (
                              <i className="ti ti-loader-2" style={{ fontSize: 20, animation: "spin 1s linear infinite", color: "var(--outline)" }} />
                            ) : (
                              <i
                                className={`ti ${role.is_active ? "ti-toggle-right" : "ti-toggle-left"}`}
                                style={{ fontSize: 20, color: role.is_active ? "var(--success)" : "var(--outline)" }}
                              />
                            )}
                          </button>
                        </>
                      ) : (
                        <span style={{ fontSize: 12, color: "var(--on-variant)" }}>View only</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Permission Matrix ─────────────────────────────────────────────── */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">
            <i className="ti ti-shield-lock" /> Permission Matrix
          </div>
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>
            {modules.length} modules · {roles.length} roles
          </span>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th style={{ minWidth: 160 }}>Module</th>
                {roles.map(role => (
                  <th key={role.id} style={{ textAlign: "center", minWidth: 130 }}>
                    <div>{role.display_name}</div>
                    <div style={{ fontSize: 10, fontWeight: 400, color: "var(--outline)", textTransform: "none", letterSpacing: 0 }}>
                      {role.permissions.length} perms
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {modules.map(module => {
                const totalActions = (permissionsMap[module] ?? []).length;
                return (
                  <tr key={module}>
                    <td style={{ fontWeight: 600, fontSize: 13 }}>
                      <i className="ti ti-cube" style={{ fontSize: 14, color: "var(--primary)", marginRight: 6 }} />
                      {moduleDisplayName(module)}
                    </td>
                    {roles.map(role => {
                      const actions = actionsForModule(role, module);
                      return (
                        <td key={role.id} style={{ textAlign: "center", verticalAlign: "middle" }}>
                          {actions.length === 0 ? (
                            <span className="badge badge-neutral">—</span>
                          ) : actions.length === totalActions ? (
                            <span className="badge badge-success">Full ({actions.length})</span>
                          ) : (
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 3, justifyContent: "center" }}>
                              {actions.map(a => (
                                <span key={a} className="badge badge-info" style={{ fontSize: 10 }}>{a}</span>
                              ))}
                            </div>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Spinner keyframe */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* ── Modals ───────────────────────────────────────────────────────── */}
      {showAddModal && (
        <AddRoleModal
          permissionsMap={permissionsMap}
          saving={saving}
          onClose={() => setShowAddModal(false)}
          onAdd={addRole}
        />
      )}

      {editingRole && (
        <EditRoleModal
          role={editingRole}
          permissionsMap={permissionsMap}
          saving={saving}
          onClose={() => setEditingRole(null)}
          onEdit={editRole}
        />
      )}
    </>
  );
}

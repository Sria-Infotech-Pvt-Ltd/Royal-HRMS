"use client";

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import platformAdminApi from "@/lib/platformAdminApi";
import { API } from "@/lib/api/endpoints";
import type { PlatformAdminAccountListResponse, PlatformAdminInfo } from "@/types/platformAdmin";
import InviteAdminModal from "./_components/InviteAdminModal";

export default function PlatformAdminsPage() {
  const { data: me } = useFetch<PlatformAdminInfo>(API.platformAdmin.me, platformAdminApi);
  const { data: adminList, loading, error, refetch } =
    useFetch<PlatformAdminAccountListResponse>(API.platformAdmin.admins.list, platformAdminApi);
  const [showInvite, setShowInvite] = useState(false);
  const [togglingId, setTogglingId] = useState<string | null>(null);
  const [toggleError, setToggleError] = useState("");

  async function toggleActive(id: string, nextActive: boolean) {
    setTogglingId(id);
    setToggleError("");
    try {
      await platformAdminApi.patch(API.platformAdmin.admins.detail(id), { is_active: nextActive });
      refetch();
    } catch (err) {
      const message = (err as { response?: { data?: { message?: string } } })
        ?.response?.data?.message ?? "Failed to update platform admin.";
      setToggleError(message);
    } finally {
      setTogglingId(null);
    }
  }

  const admins = adminList?.results ?? [];

  return (
    <div style={{ padding: "32px 24px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ fontSize: 20, fontWeight: 700 }}>Platform Admins</h1>
        <button className="btn btn-filled" onClick={() => setShowInvite(true)} suppressHydrationWarning>
          <i className="ti ti-user-plus" /> Invite admin
        </button>
      </div>

      <div className="card">
        <div className="card-body" style={{ padding: 0 }}>
          {toggleError && (
            <div className="alert alert-warn" style={{ margin: 16 }}>
              <i className="ti ti-alert-triangle" /><div>{toggleError}</div>
            </div>
          )}
          {loading ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>
              <i className="ti ti-loader-2 spin" /> Loading platform admins…
            </div>
          ) : error ? (
            <div className="alert alert-warn" style={{ margin: 16 }}><i className="ti ti-alert-triangle" /><div>{error}</div></div>
          ) : admins.length === 0 ? (
            <div style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>No platform admins yet.</div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Status</th>
                    <th>Last login</th>
                    <th>Created</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {admins.map(a => {
                    const isSelf = a.id === me?.id;
                    return (
                      <tr key={a.id}>
                        <td>{a.full_name}</td>
                        <td>{a.email}</td>
                        <td>
                          <span className={`badge ${a.is_active ? "badge-success" : "badge-neutral"}`}>
                            {a.is_active ? "Active" : "Disabled"}
                          </span>
                          {isSelf && <span className="text-muted" style={{ marginLeft: 8, fontSize: 12 }}>(you)</span>}
                        </td>
                        <td>{a.last_login ? new Date(a.last_login).toLocaleString() : "Never"}</td>
                        <td>{new Date(a.created_at).toLocaleDateString()}</td>
                        <td>
                          <button
                            type="button"
                            className={`btn btn-sm ${a.is_active ? "btn-ghost" : "btn-outline"}`}
                            disabled={togglingId === a.id || isSelf}
                            title={isSelf ? "You cannot deactivate your own account" : undefined}
                            onClick={() => toggleActive(a.id, !a.is_active)}
                            suppressHydrationWarning
                          >
                            {togglingId === a.id ? "…" : a.is_active ? "Disable" : "Enable"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showInvite && <InviteAdminModal onClose={() => setShowInvite(false)} onCreated={refetch} />}
    </div>
  );
}

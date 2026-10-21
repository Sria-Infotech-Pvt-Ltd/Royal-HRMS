"use client";

// What the person holding this seat is allowed to do. Access follows the position, not a role: whoever is placed
// here inherits every permission ticked below for as long as they hold the seat.

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import Modal from "@/components/Modal";
import ToggleSwitch from "@/components/ToggleSwitch";
import type { PermissionCatalogueItem, Position, PositionPermissions } from "@/types/orgStructure";

interface Props {
  position: Position | null;
  onClose: () => void;
  onSaved: () => void;
}

export default function PositionPermissionsModal({ position, onClose, onSaved }: Props) {
  const [catalogue, setCatalogue] = useState<Record<string, PermissionCatalogueItem[]>>({});
  const [granted, setGranted] = useState<Set<string>>(new Set());
  const [canManageTeam, setCanManageTeam] = useState(false);
  const [canManageBranch, setCanManageBranch] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const positionId = position?.id;
  useEffect(() => {
    if (!positionId) return;
    Promise.all([
      clientApi.get<{ data: { results: Record<string, PermissionCatalogueItem[]> } }>(API.permissions.list, { params: { page_size: 500 } }),
      clientApi.get<{ data: PositionPermissions }>(API.orgStructure.positions.permissions(positionId)),
    ])
      .then(([catalogueResponse, seatResponse]) => {
        setCatalogue(catalogueResponse.data.data.results ?? {});
        setGranted(new Set(seatResponse.data.data.codenames));
        setCanManageTeam(seatResponse.data.data.can_manage_team);
        setCanManageBranch(seatResponse.data.data.can_manage_branch);
      })
      .catch((err: unknown) => setError((err as { message?: string })?.message ?? "Could not load this position's permissions."))
      .finally(() => setIsLoading(false));
  }, [positionId]);

  function toggle(codename: string) {
    setGranted(previous => {
      const next = new Set(previous);
      if (next.has(codename)) next.delete(codename); else next.add(codename);
      return next;
    });
  }

  async function save() {
    if (!position) return;
    setIsSaving(true);
    setError(null);
    try {
      await clientApi.put(API.orgStructure.positions.permissions(position.id), {
        codenames: [...granted], can_manage_team: canManageTeam, can_manage_branch: canManageBranch,
      });
      onSaved();
    } catch (err: unknown) {
      setError((err as { message?: string })?.message ?? "Could not save these permissions.");
    } finally {
      setIsSaving(false);
    }
  }

  if (!position) return null;

  return (
    <Modal
      title={<><i className="ti ti-shield-lock" style={{ marginRight: 8 }} />Permissions — {position.title}</>}
      onClose={onClose}
      maxWidth={640}
      footer={
        <>
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          <button className="btn btn-filled" onClick={save} disabled={isSaving || isLoading}>
            {isSaving ? "Saving…" : "Save permissions"}
          </button>
        </>
      }
    >
      <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 14 }}>
        Whoever holds this position in {position.org_unit_name} gets exactly these permissions. They change automatically when the seat changes hands.
      </div>
      {error && <div className="alert alert-error" style={{ marginBottom: 12 }}><i className="ti ti-alert-circle" /><span>{error}</span></div>}
      {isLoading ? <div style={{ padding: 24, textAlign: "center", color: "var(--on-variant)" }}>Loading…</div> : (
        <>
          <div style={{ display: "grid", gap: 10, marginBottom: 16 }}>
            <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 }}>
              <span><b>Manages a team</b> — appears in manager dropdowns</span>
              <ToggleSwitch checked={canManageTeam} onChange={setCanManageTeam} />
            </label>
            <label style={{ display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 13 }}>
              <span><b>Branch-wide access</b> — every employee and record in their own branch</span>
              <ToggleSwitch checked={canManageBranch} onChange={setCanManageBranch} />
            </label>
          </div>
          {Object.entries(catalogue).map(([module, items]) => (
            <div key={module} style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase", color: "var(--on-variant)", marginBottom: 6 }}>
                {module.replace(/_/g, " ")}
              </div>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                {items.map(item => (
                  <label key={item.codename} className="chip" style={{ cursor: "pointer", display: "inline-flex", gap: 6, alignItems: "center" }}>
                    <input type="checkbox" checked={granted.has(item.codename)} onChange={() => toggle(item.codename)} />
                    {item.action}{item.is_sensitive ? " ⚠" : ""}
                  </label>
                ))}
              </div>
            </div>
          ))}
        </>
      )}
    </Modal>
  );
}

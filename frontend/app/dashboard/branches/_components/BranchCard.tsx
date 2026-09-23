"use client";

import { geofenceBadge, type Branch } from "./_data";

interface Props {
  branch: Branch;
  canEdit: boolean;
  onEdit: (branch: Branch) => void;
  onDelete: (branch: Branch) => void;
}

export default function BranchCard({ branch, canEdit, onEdit, onDelete }: Props) {
  return (
    <div className="card" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
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
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", justifyContent: "flex-end" }}>
            {branch.is_headquarter && (
              <span className="badge" style={{ background: "var(--bg-high)", color: "var(--on-variant)", fontSize: "10px", fontWeight: 600, letterSpacing: "0.04em", padding: "4px 8px" }}>
                <i className="ti ti-star-filled" style={{ fontSize: "10px", marginRight: "2px", color: "var(--on-variant)" }} /> HEADQUARTER
              </span>
            )}
            {branch.is_metro && (
              <span className="badge" style={{ background: "var(--bg-high)", color: "var(--on-variant)", fontSize: "10px", fontWeight: 600, letterSpacing: "0.04em", padding: "4px 8px" }}>
                <i className="ti ti-map-pin" style={{ fontSize: "10px", marginRight: "2px", color: "var(--on-variant)" }} /> METRO
              </span>
            )}
          </div>
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
              onClick={() => onEdit(branch)}
            >
              <i className="ti ti-edit" style={{ fontSize: "16px", marginRight: "6px" }} /> Edit
            </button>
            <button
              className="btn btn-ghost"
              style={{ width: "40px", justifyContent: "center", border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "8px 0", color: "var(--error)" }}
              onClick={() => onDelete(branch)}
              title={`Delete ${branch.branch_name}`}
              aria-label={`Delete ${branch.branch_name}`}
            >
              <i className="ti ti-trash" style={{ fontSize: "16px" }} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

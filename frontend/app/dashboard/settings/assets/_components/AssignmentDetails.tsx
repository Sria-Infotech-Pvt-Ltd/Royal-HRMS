"use client";

// Edit Asset → read-only "Assignment Details": who currently holds the asset.
// Re-reads the asset when opened so the holder is current; if that fails the
// list row's data is shown with a note. Nothing here changes assignments.

import { useEffect, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { fmtAssetDate, holderView } from "@/lib/assetHolder";
import type { Asset } from "@/types/assets";

export default function AssignmentDetails({ asset }: { asset: Asset }) {
  const [fresh, setFresh] = useState<Asset | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setFailed(false);
    clientApi.get(API.assets.detail(asset.id))
      .then(({ data }) => { if (alive) setFresh(data.data as Asset); })
      .catch(() => { if (alive) setFailed(true); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [asset.id]);

  const view = holderView(fresh ?? asset);

  return (
    <div className="mb-16" style={{ border: "1px solid var(--outline-v)", borderRadius: "var(--radius)", padding: "12px 14px", background: "var(--bg-low)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, display: "flex", alignItems: "center", gap: 6 }}>
          <i className="ti ti-user-check" style={{ color: "var(--primary)" }} /> Assignment Details
        </span>
        {loading
          ? <span style={{ fontSize: 11.5, color: "var(--on-variant)" }}><i className="ti ti-loader-2 animate-spin" /> Loading…</span>
          : view.kind === "assigned"
            ? <span className="badge badge-info">{view.status}</span>
            : <span className="badge badge-neutral">Not assigned</span>}
      </div>

      {view.kind === "assigned" ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "8px 16px", fontSize: 12.5 }}>
          <Item label="Assigned to" value={view.employee} muted={view.hidden} />
          <Item label="Employee ID" value={view.code ?? "—"} muted={!view.code} />
          <Item label="Assigned on" value={fmtAssetDate(view.assignedDate)} />
          <Item label="Expected return" value={view.expectedReturn ? fmtAssetDate(view.expectedReturn) : "Not set"} muted={!view.expectedReturn} />
        </div>
      ) : (
        <p style={{ margin: 0, fontSize: 12.5, color: "var(--on-variant)" }}>{view.message}</p>
      )}

      {failed && (
        <p style={{ margin: "8px 0 0", fontSize: 11.5, color: "var(--warn)" }}>
          <i className="ti ti-alert-triangle" /> Couldn&apos;t refresh the assignment; showing the details from the list.
        </p>
      )}
      <p style={{ margin: "8px 0 0", fontSize: 11.5, color: "var(--on-variant)" }}>
        Read-only. Assign or return assets from the employee&apos;s profile → Assets.
      </p>
    </div>
  );
}

function Item({ label, value, muted }: { label: string; value: string; muted?: boolean }) {
  return (
    <div>
      <div style={{ fontSize: 11, color: "var(--on-variant)", textTransform: "uppercase", letterSpacing: "0.04em" }}>{label}</div>
      <div style={{ fontWeight: muted ? 400 : 600, color: muted ? "var(--on-variant)" : "var(--on-bg)", marginTop: 2 }}>{value}</div>
    </div>
  );
}

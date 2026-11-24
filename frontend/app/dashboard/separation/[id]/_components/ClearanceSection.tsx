"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useFetch } from "@/hooks/useFetch";
import { useT } from "@/hooks/useI18n";
import { useToast } from "@/components/ToastProvider";
import type { ClearanceItem, SeparationRequest } from "@/types/separation";
import { fmtDateTime, statusBadgeClass } from "../../_workflow";

interface Props {
  r: SeparationRequest;
}

export default function ClearanceSection({ r }: Props) {
  const t = useT();
  const { showToast } = useToast();
  const { data: clearances, loading, refetch } = useFetch<ClearanceItem[]>(API.separation.clearances(r.id));
  const [rejecting, setRejecting] = useState<ClearanceItem | null>(null);
  const [remarks, setRemarks] = useState("");
  const [working, setWorking] = useState(false);

  const rows = clearances ?? [];
  const completedCount = rows.filter(c => c.status.toLowerCase().includes("approve") || c.status.toLowerCase().includes("clear")).length;

  function extractError(err: unknown, fallback: string): string {
    return (err as { response?: { data?: { message?: string } }; message?: string })
      ?.response?.data?.message ?? (err as { message?: string })?.message ?? fallback;
  }

  async function act(item: ClearanceItem, action: "approve" | "reject", note: string) {
    setWorking(true);
    try {
      await clientApi.post(API.separation.clearanceAction(r.id, item.id), { action, remarks: note });
      showToast(action === "approve" ? t("{name} approved.", { name: item.clearance_type_display }) : t("{name} rejected.", { name: item.clearance_type_display }), "success");
      setRejecting(null);
      setRemarks("");
      refetch();
    } catch (err: unknown) {
      showToast(extractError(err, t("Failed to submit the decision.")), "error");
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="card mb-16">
      <div className="card-header">
        <span className="card-title"><i className="ti ti-clipboard-check" /> {t("Clearance ({done}/{total})", { done: completedCount, total: rows.length })}</span>
      </div>
      <div className="card-body" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {loading ? (
          <p style={{ fontSize: 13, color: "var(--on-variant)", margin: 0 }}><i className="ti ti-loader-2 spin" /> {t("Loading…")}</p>
        ) : (
          rows.map(item => (
            <div key={item.id} style={{ border: "1px solid var(--outline-v)", borderRadius: 8, padding: "10px 14px" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <span style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)" }}>{item.clearance_type_display}</span>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className={`badge ${statusBadgeClass(item.status)}`}>{item.status_display}</span>
                  {item.can_action && rejecting?.id !== item.id && (
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="btn btn-danger btn-sm" onClick={() => setRejecting(item)} disabled={working} suppressHydrationWarning>
                        {t("Reject")}
                      </button>
                      <button className="btn btn-success btn-sm" onClick={() => act(item, "approve", "")} disabled={working} suppressHydrationWarning>
                        {t("Approve")}
                      </button>
                    </div>
                  )}
                </div>
              </div>
              <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
                {item.cleared_by_name || t("Not yet assigned")}{item.actioned_at ? ` · ${fmtDateTime(item.actioned_at)}` : ""}
              </div>
              {item.remarks && (
                <div style={{ fontSize: 12, color: "var(--on-variant)", background: "var(--bg-low)", borderRadius: 8, padding: "6px 10px", marginTop: 6 }}>
                  “{item.remarks}”
                </div>
              )}
              {rejecting?.id === item.id && (
                <div style={{ marginTop: 8, display: "flex", flexDirection: "column", gap: 6 }}>
                  <textarea
                    className="field-input" rows={2} placeholder={t("Reason for rejection (required)")}
                    value={remarks} onChange={e => setRemarks(e.target.value)} style={{ resize: "vertical" }}
                  />
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      className="btn btn-danger btn-sm" disabled={working || !remarks.trim()}
                      onClick={() => act(item, "reject", remarks.trim())} suppressHydrationWarning
                    >
                      {t("Confirm Reject")}
                    </button>
                    <button className="btn btn-ghost btn-sm" onClick={() => { setRejecting(null); setRemarks(""); }} disabled={working} suppressHydrationWarning>
                      {t("Cancel")}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

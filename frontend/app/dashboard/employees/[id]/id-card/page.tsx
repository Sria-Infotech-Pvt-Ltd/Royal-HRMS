"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { IdCardPreview, IdCardPrintSheet } from "@/components/idcard/IdCardFaces";
import type { IdCardData, PrintLayout } from "@/lib/idCard";

const LAYOUTS: { id: PrintLayout; label: string; hint: string }[] = [
  { id: "card", label: "Card size (50 × 85 mm)", hint: "One side per page, for card printers or pre-cut card stock." },
  { id: "a4",   label: "A4 sheet",               hint: "Front and back side by side at actual size, with cut guides." },
];

export default function EmployeeIdCardPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();

  const [data,    setData]    = useState<IdCardData | null>(null);
  const [error,   setError]   = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [layout,  setLayout]  = useState<PrintLayout>("card");

  useEffect(() => {
    clientApi
      .get<{ data: IdCardData }>(API.employees.idCard(id))
      .then(({ data }) => setData(data.data))
      .catch((err: { response?: { status?: number; data?: { message?: string } } }) => {
        const status = err?.response?.status;
        setError(
          status === 403 ? "You don't have permission to generate ID cards."
          : status === 404 ? "Employee not found."
          : err?.response?.data?.message ?? "Could not load the ID card.",
        );
      })
      .finally(() => setLoading(false));
  }, [id]);

  const activeLayout = LAYOUTS.find(l => l.id === layout)!;

  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">ID Card</div>
          <div className="page-sub">
            {data ? `${data.employee.full_name ?? ""}${data.employee.employee_id ? ` · ${data.employee.employee_id}` : ""}` : "Preview and print"}
          </div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push(`/dashboard/employees/${encodeURIComponent(id)}`)}>
            <i className="ti ti-arrow-left" /> Back to profile
          </button>
          <button className="btn btn-filled" disabled={!data} onClick={() => window.print()}>
            <i className="ti ti-printer" /> Print
          </button>
        </div>
      </div>

      {loading && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 300, gap: 10, color: "var(--on-variant)" }}>
          <i className="ti ti-loader-2" style={{ fontSize: 24, animation: "spin 1s linear infinite" }} /> Loading ID card…
        </div>
      )}

      {error && (
        <div className="alert alert-error mb-16"><i className="ti ti-alert-circle" /><div>{error}</div></div>
      )}

      {data && (
        <>
          {data.missing.length > 0 && (
            <div className="alert alert-warning mb-16" style={{ background: "#fff8e6", border: "1px solid #f3d58a", color: "#7a5a00" }}>
              <i className="ti ti-alert-triangle" />
              <div>
                <strong>Not on record, so left off the card:</strong> {data.missing.join(", ")}.
                <div style={{ fontSize: 12, marginTop: 2 }}>
                  Add them to the employee profile, Company Info, or Settings → ID Card, then reload this page.
                </div>
              </div>
            </div>
          )}

          <div className="card mb-24">
            <div className="card-header" style={{ flexWrap: "wrap", gap: 12 }}>
              <div className="card-title"><i className="ti ti-eye" /> Preview</div>
              <div style={{ display: "flex", alignItems: "center", gap: 8, marginLeft: "auto" }}>
                <label htmlFor="idc-layout" style={{ fontSize: 12.5, color: "var(--on-variant)" }}>Print layout</label>
                <select id="idc-layout" className="field-input" style={{ width: "auto", padding: "6px 10px" }}
                  value={layout} onChange={e => setLayout(e.target.value as PrintLayout)}>
                  {LAYOUTS.map(l => <option key={l.id} value={l.id}>{l.label}</option>)}
                </select>
              </div>
            </div>
            <div style={{ padding: "24px 16px", overflowX: "auto" }}>
              <IdCardPreview data={data} />
            </div>
          </div>

          <div className="alert alert-info mb-24">
            <i className="ti ti-info-circle" />
            <div style={{ fontSize: 12.5, lineHeight: 1.6 }}>
              <strong>{activeLayout.label}:</strong> {activeLayout.hint} In the print dialog choose your printer,
              set scale to <strong>100% / Actual size</strong> (not &ldquo;Fit to page&rdquo;), and turn on
              <strong> Background graphics</strong> so the navy colours print. For a double-sided card, use the
              printer&apos;s two-sided option if it has one; otherwise print the front, re-feed the card and print the back.
            </div>
          </div>

          <IdCardPrintSheet data={data} layout={layout} />
        </>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>
  );
}

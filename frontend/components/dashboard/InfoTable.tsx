"use client";

// A titled table card for an information page (e.g. a retention schedule). Presentational only.

import type { InfoSection } from "@/components/dashboard/InfoPage";

export interface InfoTableData {
  icon: InfoSection["icon"];
  title: string;
  intro?: string;
  columns: string[];
  rows: string[][];
}

export default function InfoTable({ icon, title, intro, columns, rows }: InfoTableData) {
  return (
    <section aria-label={title} className="card" style={{ padding: "18px 20px", marginTop: 16 }}>
      <h2 style={{ margin: "0 0 4px", display: "flex", alignItems: "center", gap: 10, fontSize: 15, fontWeight: 800, color: "var(--on-bg)" }}>
        <span aria-hidden="true" style={{ width: 32, height: 32, borderRadius: 9, display: "grid", placeItems: "center", fontSize: 17, background: "var(--bg-low)", color: "var(--primary)" }}><i className={`ti ${icon}`} /></span>
        {title}
      </h2>
      {intro && <p style={{ margin: "6px 0 0", fontSize: 12.5, color: "var(--on-variant)" }}>{intro}</p>}
      <div style={{ overflowX: "auto", marginTop: 10 }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13, lineHeight: 1.5 }}>
          <thead>
            <tr>
              {columns.map(column => (
                <th key={column} scope="col" style={{ textAlign: "left", padding: "8px 12px", fontSize: 11, fontWeight: 700, letterSpacing: "0.05em", textTransform: "uppercase", color: "var(--on-variant)", borderBottom: "1px solid var(--outline-v)" }}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row[0]}>
                {row.map((cell, index) => (
                  <td key={index} style={{ padding: "9px 12px", verticalAlign: "top", color: "var(--on-bg)", fontWeight: index === 0 ? 700 : 400, borderBottom: "1px solid var(--outline-v)" }}>{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

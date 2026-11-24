"use client";

// The Audit Log entries: who did what and when, with an avatar, a coloured module and action, and "5 min ago" beside the exact time.
// Click a row to open the details (description, record, IP address, role). Shimmering rows while loading, an empty state, and paging.

import { Fragment, useState } from "react";
import { useT } from "@/hooks/useI18n";
import { formatDate } from "@/lib/formatDate";
import type { AuditLogPage } from "@/types/audit";
import { actionStyle, fmtAction, initialsOf, moduleColour, relativeTime, tint } from "./auditView";

interface Props { data: AuditLogPage | null; loading: boolean; error: string | null; page: number; onPage: (page: number) => void }

const SHIMMER = { background: "linear-gradient(90deg, #eceff6 25%, #f7f8fc 50%, #eceff6 75%)", backgroundSize: "300% 100%", animation: "ann-shimmer 1.4s linear infinite" } as const;
const MONO = { fontFamily: "Menlo, Consolas, monospace", fontSize: 12 } as const;

function Pill({ colour, icon, children }: { colour: string; icon?: string; children: React.ReactNode }) {
  return <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, fontWeight: 700, padding: "3px 11px", borderRadius: 999, whiteSpace: "nowrap", textTransform: "capitalize", background: tint(colour, 0.14), color: colour }}>{icon && <i className={`ti ${icon}`} aria-hidden="true" />}{children}</span>;
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><div style={{ fontSize: 10.5, fontWeight: 700, letterSpacing: ".05em", textTransform: "uppercase", color: "var(--on-variant)" }}>{label}</div><div style={{ fontSize: 13, color: "var(--on-bg)", marginTop: 2, wordBreak: "break-word" }}>{children}</div></div>;
}

export default function AuditTable({ data, loading, error, page, onPage }: Props) {
  const t = useT();
  const [openId, setOpenId] = useState<number | null>(null);
  const rows = data?.results ?? [];

  return (
    <section aria-label={t("Activity")} className="card" style={{ padding: 0, overflow: "hidden" }}>
      <header style={{ padding: "14px 20px", display: "flex", alignItems: "center", justifyContent: "space-between", borderBottom: "1px solid var(--outline-v)" }}>
        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 800, color: "var(--on-bg)", display: "flex", alignItems: "center", gap: 8 }}>
          <i className="ti ti-history" aria-hidden="true" style={{ color: "var(--brand)" }} /> {t("Activity")}
        </h3>
        {data && <span style={{ fontSize: 12, fontWeight: 700, padding: "2px 10px", borderRadius: 999, background: tint("var(--brand)", 0.12), color: "var(--brand)" }}>{t("{count} entries", { count: data.count.toLocaleString() })}</span>}
      </header>

      {error && <div role="alert" style={{ margin: 16, padding: "10px 14px", background: "rgba(220,38,38,0.06)", border: "1px solid rgba(220,38,38,0.2)", borderRadius: 10, color: "var(--error)", fontSize: 13 }}>{error}</div>}

      <div className="table-wrap">
        <table>
          <thead><tr><th>{t("When")}</th><th>{t("Actor")}</th><th>{t("Module")}</th><th>{t("Action")}</th><th>{t("IP Address")}</th><th aria-label={t("Details")} /></tr></thead>
          <tbody>
            {loading && [0, 1, 2, 3, 4].map(row => <tr key={row} aria-label={t("Loading")}>{Array.from({ length: 6 }, (_, cell) => <td key={cell}><div aria-hidden="true" style={{ ...SHIMMER, height: 14, borderRadius: 6 }} /></td>)}</tr>)}
            {!loading && rows.length === 0 && (
              <tr><td colSpan={6} style={{ padding: "40px 12px", textAlign: "center", color: "var(--on-variant)" }}>
                <i className="ti ti-history-off" aria-hidden="true" style={{ fontSize: 36, color: "var(--outline)" }} />
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 6 }}>{t("No audit entries found")}</div>
                <div style={{ fontSize: 12.5, marginTop: 2 }}>{t("Try another module or a wider date range.")}</div>
              </td></tr>
            )}
            {!loading && rows.map(log => {
              const created = new Date(log.created_at);
              const ago = relativeTime(log.created_at);
              const action = actionStyle(log.action);
              const isOpen = openId === log.id;
              return (
                <Fragment key={log.id}>
                  <tr onClick={() => setOpenId(isOpen ? null : log.id)} style={{ cursor: "pointer", background: isOpen ? tint("var(--brand)", 0.05) : undefined }}>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <div style={{ fontWeight: 700, fontSize: 13, color: "var(--on-bg)" }}>{ago ?? formatDate(created)}</div>
                      <div style={{ fontSize: 11.5, color: "var(--on-variant)" }}>{ago ? formatDate(created) + " · " : ""}{created.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: true })}</div>
                    </td>
                    <td>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <span aria-hidden="true" style={{ width: 34, height: 34, borderRadius: "50%", flexShrink: 0, display: "grid", placeItems: "center", fontSize: 12, fontWeight: 800, color: "#fff", background: "linear-gradient(135deg, var(--brand), #A78BFA)" }}>{initialsOf(log.actor_name)}</span>
                        <div>
                          <div style={{ fontWeight: 700, fontSize: 13, color: "var(--on-bg)" }}>{log.actor_name}</div>
                          {log.actor_email && <div style={{ fontSize: 11.5, color: "var(--on-variant)" }}>{log.actor_email}</div>}
                        </div>
                      </div>
                    </td>
                    <td><Pill colour={moduleColour(log.module)}>{log.module}</Pill></td>
                    <td><Pill colour={action.colour} icon={action.icon}>{fmtAction(log.action)}</Pill></td>
                    <td><code style={{ ...MONO, color: "var(--on-variant)", background: "var(--bg-low)", padding: "2px 7px", borderRadius: 6 }}>{log.ip_address ?? "—"}</code></td>
                    <td style={{ width: 36, textAlign: "center", color: "var(--on-variant)" }}>
                      <button type="button" className="btn btn-ghost" aria-expanded={isOpen} aria-label={isOpen ? t("Hide details") : t("Show details")} onClick={event => { event.stopPropagation(); setOpenId(isOpen ? null : log.id); }} style={{ width: 28, height: 28, padding: 0, justifyContent: "center" }}>
                        <i className={`ti ${isOpen ? "ti-chevron-up" : "ti-chevron-down"}`} />
                      </button>
                    </td>
                  </tr>
                  {isOpen && (
                    <tr>
                      <td colSpan={6} style={{ background: tint("var(--brand)", 0.04), padding: "14px 20px" }}>
                        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(190px, 1fr))", gap: 16 }}>
                          <Detail label={t("What happened")}>{log.description || fmtAction(log.action)}</Detail>
                          <Detail label={t("Record")}>{log.object_id ? <span style={MONO}>{log.object_id}</span> : "—"}</Detail>
                          <Detail label={t("Role")}>{log.actor_role || "—"}</Detail>
                          <Detail label={t("Exact time")}>{created.toLocaleString("en-IN")}</Detail>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {data && data.total_pages > 1 && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 8, padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
          <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{t("Page {page} of {total}", { page: data.page, total: data.total_pages })}</span>
          <div style={{ display: "flex", gap: 6 }}>
            <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => onPage(Math.max(page - 1, 1))}><i className="ti ti-chevron-left" /> {t("Prev")}</button>
            {Array.from({ length: data.total_pages }, (_, index) => index + 1).filter(number => Math.abs(number - data.page) <= 2).map(number => (
              <button key={number} className="btn btn-sm" aria-current={number === data.page ? "page" : undefined} onClick={() => onPage(number)}
                style={{ minWidth: 32, background: number === data.page ? "var(--primary)" : "transparent", color: number === data.page ? "#fff" : "var(--on-variant)", border: number === data.page ? "none" : "1.5px solid var(--outline-v)" }}>{number}</button>
            ))}
            <button className="btn btn-ghost btn-sm" disabled={page >= data.total_pages} onClick={() => onPage(Math.min(page + 1, data.total_pages))}>{t("Next")} <i className="ti ti-chevron-right" /></button>
          </div>
        </div>
      )}
    </section>
  );
}

"use client";

// Shared look for the inner tabs of Attendance & Time (Invalid Punches, Un-punches, Corrections, Weekly Off Assignment): a card with a
// coloured header (icon, title, what it is for, a count), an optional filter row and notice, shimmering loading rows, a friendly empty
// state, coloured pills, an employee avatar and paging. The tabs keep their own data and actions; this is only how they look.

import type { CSSProperties, ReactNode } from "react";
import { useT } from "@/hooks/useI18n";
import { PALETTE, tint } from "./attendancePalette";

export const MONO: CSSProperties = { fontFamily: "Menlo, Consolas, monospace", fontSize: 12.5 };
const SHIMMER: CSSProperties = { background: "linear-gradient(90deg, #eceff6 25%, #f7f8fc 50%, #eceff6 75%)", backgroundSize: "300% 100%", animation: "ann-shimmer 1.4s linear infinite" };

interface SectionCardProps {
  icon: string;
  colour: string;
  title: string;
  subtitle: string;
  /** The total to show beside the title; hidden while it is not known. */
  count?: number | null;
  /** Filters shown in a row under the header. */
  filters?: ReactNode;
  /** A button (or two) shown at the right of the header. */
  action?: ReactNode;
  children: ReactNode;
}

export function SectionCard({ icon, colour, title, subtitle, count, filters, action, children }: SectionCardProps) {
  const t = useT();
  return (
    <section aria-label={title} className="card" style={{ padding: 0, overflow: "hidden" }}>
      <header style={{ padding: "16px 20px", display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", borderBottom: "1px solid var(--outline-v)", background: `linear-gradient(135deg, ${tint(colour, 0.1)} 0%, var(--surface) 62%)` }}>
        <span aria-hidden="true" style={{ width: 42, height: 42, borderRadius: 12, display: "grid", placeItems: "center", background: colour, color: "#fff", fontSize: 21, boxShadow: `0 4px 12px ${tint(colour, 0.35)}` }}><i className={`ti ${icon}`} /></span>
        <div style={{ flex: "1 1 240px", minWidth: 0 }}>
          <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800, color: "var(--on-bg)", display: "flex", alignItems: "center", gap: 8 }}>
            {title}
            {typeof count === "number" && <span aria-label={t("{count} in total", { count })} style={{ fontSize: 12, fontWeight: 700, padding: "2px 10px", borderRadius: 999, background: tint(colour, 0.14), color: colour }}>{count}</span>}
          </h3>
          <p style={{ margin: "2px 0 0", fontSize: 12.5, color: "var(--on-variant)" }}>{subtitle}</p>
        </div>
        {action}
      </header>
      {filters && <div style={{ padding: "12px 20px", display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center", borderBottom: "1px solid var(--outline-v)", background: "var(--bg-low)" }}>{filters}</div>}
      {children}
    </section>
  );
}

/** A short line of context in the colour of its meaning (info, warning or error). */
export function Notice({ tone, icon, children }: { tone: "info" | "warn" | "error"; icon: string; children: ReactNode }) {
  const colour = tone === "error" ? PALETTE.absent : tone === "warn" ? PALETTE.late : PALETTE.brand;
  return (
    <div role={tone === "error" ? "alert" : undefined} style={{ margin: "14px 20px 0", display: "flex", gap: 10, alignItems: "flex-start", padding: "10px 14px", borderRadius: 12, fontSize: 13, color: "var(--on-bg)", background: tint(colour, 0.09), border: `1px solid ${tint(colour, 0.28)}` }}>
      <i className={`ti ${icon}`} aria-hidden="true" style={{ color: colour, fontSize: 18, marginTop: 1 }} />
      <span>{children}</span>
    </div>
  );
}

export function Pill({ colour, children }: { colour: string; children: ReactNode }) {
  return <span style={{ display: "inline-block", fontSize: 12, fontWeight: 700, padding: "3px 11px", borderRadius: 999, whiteSpace: "nowrap", background: tint(colour, 0.14), color: colour }}>{children}</span>;
}

const initialsOf = (name: string) => name.split(/\s+/).filter(Boolean).slice(0, 2).map(word => word[0].toUpperCase()).join("") || "?";

/** A round avatar with the person's initials, their name and their employee ID. */
export function PersonCell({ name, employeeId }: { name: string; employeeId: string }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span aria-hidden="true" style={{ width: 32, height: 32, borderRadius: "50%", flexShrink: 0, display: "grid", placeItems: "center", fontSize: 11, fontWeight: 800, color: "#fff", background: `linear-gradient(135deg, ${PALETTE.brand}, #A78BFA)` }}>{initialsOf(name)}</span>
      <div>
        <div style={{ fontWeight: 600, fontSize: 13, color: "var(--on-bg)" }}>{name}</div>
        <div style={{ ...MONO, fontSize: 11, color: "var(--on-variant)" }}>{employeeId}</div>
      </div>
    </div>
  );
}

/** Rows for a table body: three shimmering rows while loading, or a friendly message when there is nothing to show. */
export function TableStates({ columns, loading, empty, icon, title, hint }: { columns: number; loading: boolean; empty: boolean; icon: string; title: string; hint: string }) {
  const t = useT();
  if (loading) {
    return <>{Array.from({ length: 3 }, (_, row) => (
      <tr key={`loading-${row}`} aria-label={t("Loading")}>{Array.from({ length: columns }, (__, cell) => <td key={cell}><div aria-hidden="true" style={{ ...SHIMMER, height: 14, borderRadius: 6 }} /></td>)}</tr>
    ))}</>;
  }
  if (!empty) return null;
  return (
    <tr><td colSpan={columns} style={{ padding: "36px 12px", textAlign: "center", color: "var(--on-variant)" }}>
      <i className={`ti ${icon}`} aria-hidden="true" style={{ fontSize: 34, color: "var(--outline)" }} />
      <div style={{ fontSize: 14, fontWeight: 600, color: "var(--on-bg)", marginTop: 6 }}>{title}</div>
      <div style={{ fontSize: 12.5, marginTop: 2 }}>{hint}</div>
    </td></tr>
  );
}

interface PagerProps { data: { page: number; total_pages: number; count?: number } | null; page: number; onPage: (page: number) => void; noun?: string }

export function Pager({ data, page, onPage, noun }: PagerProps) {
  const t = useT();
  if (!data || data.total_pages <= 1) return null;
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 20px", borderTop: "1px solid var(--outline-v)" }}>
      <span style={{ fontSize: 12, color: "var(--on-variant)" }}>{t("Page {page} of {total}", { page: data.page, total: data.total_pages })}{noun && data.count !== undefined ? ` · ${data.count} ${noun}` : ""}</span>
      <div style={{ display: "flex", gap: 6 }}>
        <button className="btn btn-ghost btn-sm" disabled={page <= 1} onClick={() => onPage(Math.max(page - 1, 1))}><i className="ti ti-chevron-left" /> {t("Prev")}</button>
        <button className="btn btn-ghost btn-sm" disabled={page >= data.total_pages} onClick={() => onPage(Math.min(page + 1, data.total_pages))}>{t("Next")} <i className="ti ti-chevron-right" /></button>
      </div>
    </div>
  );
}

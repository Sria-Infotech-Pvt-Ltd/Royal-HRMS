"use client";

// A plain information page for the footer links (Privacy & retention, Security): a header with Back on the right, then titled sections
// of short facts. It states how the system works; it is not a legal document.

import { useRouter } from "next/navigation";
import { tr } from "@/lib/i18n/tr";

export interface InfoSection { icon: string; title: string; intro?: string; points: string[] }

interface Props { icon: string; title: string; subtitle: string; sections: InfoSection[]; footnote: string }

export default function InfoPage({ icon, title, subtitle, sections, footnote }: Props) {
  const router = useRouter();
  return (
    <>
      <div className="page-header">
        <div>
          <div className="page-title">{title}</div>
          <div className="page-sub">{subtitle}</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.back()}>
            <i className="ti ti-arrow-left" /> {tr("Back")}
          </button>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 16, alignItems: "start" }}>
        {sections.map(section => (
          <section key={section.title} aria-label={section.title} className="card" style={{ padding: "18px 20px" }}>
            <h2 style={{ margin: "0 0 4px", display: "flex", alignItems: "center", gap: 10, fontSize: 15, fontWeight: 800, color: "var(--on-bg)" }}>
              <span aria-hidden="true" style={{ width: 32, height: 32, borderRadius: 9, display: "grid", placeItems: "center", fontSize: 17, background: "var(--bg-low)", color: "var(--primary)" }}><i className={`ti ${section.icon}`} /></span>
              {section.title}
            </h2>
            {section.intro && <p style={{ margin: "6px 0 0", fontSize: 12.5, color: "var(--on-variant)" }}>{section.intro}</p>}
            <ul style={{ margin: "10px 0 0", paddingLeft: 18, display: "grid", gap: 7, fontSize: 13, lineHeight: 1.5, color: "var(--on-bg)" }}>
              {section.points.map(point => <li key={point}>{point}</li>)}
            </ul>
          </section>
        ))}
      </div>

      <p style={{ margin: "18px 2px 0", display: "flex", gap: 8, fontSize: 12.5, color: "var(--on-variant)" }}>
        <i className={`ti ${icon}`} aria-hidden="true" style={{ fontSize: 16 }} />
        <span>{footnote} <button type="button" className="btn btn-ghost btn-sm" onClick={() => router.push("/dashboard/ess?tab=hrHelp")}>{tr("Contact HR")}</button></span>
      </p>
    </>
  );
}

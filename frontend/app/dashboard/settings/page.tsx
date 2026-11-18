"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { useSettingsPrefs } from "@/hooks/useSettingsPrefs";
import { API } from "@/lib/api/endpoints";
import { KpiTile } from "@/components/dashboard/ModuleOverviewKit";
import SettingsSection from "./_components/SettingsSection";
import { CATEGORY_INFO, CATEGORY_ORDER, SETTINGS_ITEMS, countByCategory, filterSettings, type CatId } from "./_components/settingsItems";

interface OverviewData { access_seats: number; audit_events_30d: number }

const CATS: { id: CatId; icon: string; label: string }[] = [
  { id: "all", icon: "ti-grid-dots", label: "All Settings" },
  ...CATEGORY_ORDER.map(id => ({ id, icon: CATEGORY_INFO[id].icon, label: CATEGORY_INFO[id].label })),
];

export default function SettingsPage() {
  const router = useRouter();
  const [activeCat, setActiveCat] = useState<CatId>("all");
  const { data } = useFetch<OverviewData>(API.dashboard.settingsOverview);
  const { pinned, layout, togglePinned, setLayout } = useSettingsPrefs();

  const visible = filterSettings(SETTINGS_ITEMS, "", activeCat);
  const counts = countByCategory(SETTINGS_ITEMS, "");
  const byId = (ids: string[]) => ids.map(id => SETTINGS_ITEMS.find(item => item.id === id)).filter(item => item !== undefined);
  const sectionProps = { layout, pinned, onTogglePinned: togglePinned };

  return (
    <div className="plain-stack">
      <div style={{ fontSize: 12.5, color: "var(--muted)", marginBottom: 8 }}>Dashboard / Settings</div>
      <div className="pagehead">
        <div>
          <h1>HRMS <em>settings</em></h1>
          <p className="lede">
            Configure organization rules, permissions, workflows, payroll and statutory defaults.
          </p>
        </div>
        <button className="btn btn-filled" onClick={() => router.push("/dashboard/settings/audit")}>View audit log</button>
      </div>

      <div className="stats">
        <KpiTile label="CONFIGURED" value={SETTINGS_ITEMS.length} sub="Settings groups" tone="brand" />
        <KpiTile label="ACCESS SEATS" value={data?.access_seats ?? "—"} sub="Positions with extra access" tone="ok" />
        <KpiTile label="AUTOMATIONS" value="—" sub="Not yet configured" tone="warn" />
        <KpiTile label="AUDIT EVENTS" value={data?.audit_events_30d ?? "—"} sub="Last 30 days" tone="brand" />
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap", margin: "16px 0 20px" }}>
        <div className="settings-cats" role="group" aria-label="Setting categories" style={{ marginBottom: 0, padding: 5, flex: "1 1 520px" }}>
          {CATS.map(category => (
            <button
              key={category.id} type="button" aria-pressed={activeCat === category.id}
              className={`settings-cat-pill${activeCat === category.id ? " active" : ""}`} style={{ flex: 1, justifyContent: "center", padding: "10px 16px", fontSize: 13.5 }}
              onClick={() => setActiveCat(category.id)}
            >
              <i className={`ti ${category.icon}`} /> {category.label}
              <span style={{ fontSize: 11, fontWeight: 700, padding: "0 7px", borderRadius: 999, background: activeCat === category.id ? "rgba(255,255,255,.25)" : "var(--bg-mid)" }}>{counts[category.id]}</span>
            </button>
          ))}
        </div>
        <div className="settings-cats" role="group" aria-label="Layout" style={{ marginBottom: 0, padding: 4 }}>
          {([["grid", "ti-layout-grid", "Grid"], ["list", "ti-list", "List"]] as const).map(([id, icon, label]) => (
            <button key={id} type="button" aria-pressed={layout === id} aria-label={`${label} view`} title={`${label} view`} className={`settings-cat-pill${layout === id ? " active" : ""}`} style={{ padding: "7px 11px" }} onClick={() => setLayout(id)}>
              <i className={`ti ${icon}`} />
            </button>
          ))}
        </div>
      </div>

      {activeCat === "all" && <SettingsSection label="Pinned" blurb="Your shortcuts" items={byId(pinned)} {...sectionProps} />}

      {activeCat === "all"
        ? CATEGORY_ORDER.map(cat => <SettingsSection key={cat} label={CATEGORY_INFO[cat].label} blurb={CATEGORY_INFO[cat].blurb} items={visible.filter(item => item.cat === cat)} {...sectionProps} />)
        : <SettingsSection label={CATEGORY_INFO[activeCat].label} hideHeading items={visible} {...sectionProps} />}
    </div>
  );
}

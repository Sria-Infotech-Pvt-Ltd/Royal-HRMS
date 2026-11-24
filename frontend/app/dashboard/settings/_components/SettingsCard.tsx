"use client";

// One setting on the Settings landing page: a plain card with a grey icon, the name and what it is for. Purple appears only on hover
// (border, icon and arrow) and on a pinned star, so the page stays calm. The card is a real link (keyboard, open in a new tab); the star
// is a separate button beside it, because a button must not sit inside a link. In list view the card is one compact row.

import Link from "next/link";
import { useT } from "@/hooks/useI18n";
import type { SettingsLayout } from "@/hooks/useSettingsPrefs";
import type { SettingsItem } from "./settingsItems";

interface Props {
  item: SettingsItem;
  layout: SettingsLayout;
  isPinned: boolean;
  onTogglePinned: (id: string) => void;
}

export default function SettingsCard({ item, layout, isPinned, onTogglePinned }: Props) {
  const t = useT();
  const isList = layout === "list";
  return (
    <div style={{ position: "relative", height: "100%" }}>
      <Link
        href={item.route}
        className="settings-card-link"
        style={{ boxSizing: "border-box", height: "100%", display: "flex", gap: 14, alignItems: isList ? "center" : "flex-start", padding: isList ? "10px 50px 10px 16px" : "16px 48px 16px 16px", textDecoration: "none", color: "inherit", background: "var(--surface)", border: "1px solid var(--outline-v)", borderRadius: 12, transition: "border-color .15s ease, box-shadow .15s ease" }}
      >
        <span className="settings-card-icon-tile" aria-hidden="true" style={{ width: 40, height: 40, borderRadius: 10, flexShrink: 0, display: "grid", placeItems: "center", fontSize: 20, background: "var(--bg-low)", color: "var(--on-variant)", transition: "background .15s ease, color .15s ease" }}><i className={`ti ${item.icon}`} /></span>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ display: "block", fontSize: 14.5, fontWeight: 700, color: "var(--on-bg)" }}>{t(item.label)}</span>
          <span style={{ display: "block", marginTop: 3, fontSize: 12.5, lineHeight: 1.45, color: "var(--on-variant)", ...(isList ? { whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } : { display: "-webkit-box", WebkitLineClamp: 3, WebkitBoxOrient: "vertical", overflow: "hidden" }) }}>{t(item.desc)}</span>
        </span>
      </Link>
      <button
        type="button" aria-pressed={isPinned} aria-label={isPinned ? t("Unpin {label}", { label: t(item.label) }) : t("Pin {label}", { label: t(item.label) })} title={isPinned ? t("Unpin") : t("Pin to the top")}
        onClick={() => onTogglePinned(item.id)}
        style={{ position: "absolute", top: isList ? "50%" : 12, right: 12, transform: isList ? "translateY(-50%)" : undefined, width: 28, height: 28, borderRadius: 8, border: 0, cursor: "pointer", display: "grid", placeItems: "center", fontSize: 16, background: "transparent", color: isPinned ? "var(--primary)" : "var(--outline)", transition: "color .15s ease" }}
      >
        <i className={isPinned ? "ti ti-star-filled" : "ti ti-star"} aria-hidden="true" />
      </button>
    </div>
  );
}

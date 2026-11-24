"use client";

import { useState } from "react";
import Link from "next/link";
import { useSharedAnnouncement, useBirthdaysToday } from "@/hooks/useEmployeeDashboard";
import { formatDate } from "@/lib/formatDate";
import { announcementLinkHref } from "@/lib/announcementLink";
import { categoryLabel } from "@/lib/announcementCategories";
import { useT } from "@/hooks/useI18n";
import { tr } from "@/lib/i18n/tr";

function fmtDate(iso: string): string {
  return formatDate(iso);
}

function namesList(names: string[]): string {
  if (names.length === 1) return names[0];
  if (names.length === 2) return tr("{first} and {second}", { first: names[0], second: names[1] });
  return tr("{list}, and {last}", { list: names.slice(0, -1).join(", "), last: names[names.length - 1] });
}

// Combines the announcement banner and today's-birthdays banner into one card
// instead of two separately-boxed, differently-colored strips stacked on top
// of each other — same information, one consistent container.
export default function EmpUpdatesCard() {
  const t = useT();
  const { data: announcement, loading: loadingAnnouncement } = useSharedAnnouncement();
  const { data: birthdayData, loading: loadingBirthdays }    = useBirthdaysToday();

  const [announcementDismissed, setAnnouncementDismissed] = useState(false);
  const [birthdayDismissed,     setBirthdayDismissed]      = useState(false);

  const birthdaysToday = birthdayData?.birthdays ?? [];

  // The API answers an empty object when there is nothing to show, which is truthy: require a title.
  const showAnnouncement = !loadingAnnouncement && !!announcement?.title && !announcementDismissed;
  const showBirthdays    = !loadingBirthdays && birthdaysToday.length > 0 && !birthdayDismissed;

  if (!showAnnouncement && !showBirthdays) return null;

  return (
    <div className="card mb-20">
      {showAnnouncement && announcement && (
        <div
          style={{
            display: "flex", alignItems: "flex-start", gap: 12,
            padding: "14px 20px",
            borderBottom: showBirthdays ? "1px solid var(--outline-v)" : undefined,
          }}
        >
          {announcement.image_url ? (
            // eslint-disable-next-line @next/next/no-img-element -- a short-lived signed storage address, not a static asset
            <img src={announcement.image_url} alt="" style={{ width: 44, height: 44, borderRadius: 8, flexShrink: 0, objectFit: "cover" }} />
          ) : (
            <div style={{ width: 34, height: 34, borderRadius: 8, flexShrink: 0, background: "color-mix(in srgb, var(--brand) 12%, transparent)", color: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
              <i className={announcement.is_pinned ? "ti ti-pin" : "ti ti-speakerphone"} />
            </div>
          )}

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", marginBottom: 2 }}>
              <span style={{ fontSize: 11, fontWeight: 700, color: "var(--primary)", letterSpacing: "0.05em", textTransform: "uppercase" }}>
                {announcement.is_pinned ? t("Pinned Announcement") : t("Latest Announcement")}
              </span>
              {announcement.posted_by && (
                <span style={{ fontSize: 10, color: "var(--on-variant)" }}>
                  {fmtDate(announcement.created_at)} · {announcement.posted_by}
                </span>
              )}
              {announcement.category && announcement.category !== "general" && (
                <span style={{ fontSize: 10, fontWeight: 600, padding: "1px 7px", borderRadius: 10, background: "color-mix(in srgb, var(--brand) 12%, transparent)", color: "var(--primary)" }}>
                  {categoryLabel(announcement.category)}
                </span>
              )}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{announcement.title}</div>
            <div style={{ fontSize: 12, color: "var(--on-variant)", marginTop: 3, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {announcement.body}
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
            <Link href={announcementLinkHref(announcement.id)} style={{ fontSize: 12, color: "var(--primary)", fontWeight: 500, textDecoration: "none", whiteSpace: "nowrap" }}>
              {announcement.more_count ? t("+{count} more · View", { count: announcement.more_count }) : t("View")} <i className="ti ti-arrow-right" style={{ fontSize: 11 }} />
            </Link>
            <button
              onClick={() => setAnnouncementDismissed(true)}
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--on-variant)", fontSize: 14, padding: "2px 4px", lineHeight: 1 }}
              aria-label={t("Dismiss announcement")}
            >
              <i className="ti ti-x" />
            </button>
          </div>
        </div>
      )}

      {showBirthdays && (
        <div style={{ display: "flex", alignItems: "flex-start", gap: 12, padding: "14px 20px" }}>
          <div style={{ width: 34, height: 34, borderRadius: 8, flexShrink: 0, background: "rgba(37,99,235,0.12)", color: "var(--info)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16 }}>
            <i className="ti ti-cake" />
          </div>

          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: "var(--info)", letterSpacing: "0.05em", textTransform: "uppercase", marginBottom: 2 }}>
              {birthdaysToday.length === 1 ? t("Birthday Today") : t("Birthdays Today")}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>
              {birthdaysToday.length > 1
                ? t("Today is {names}'s birthdays. Wish them well.", { names: namesList(birthdaysToday.map(e => e.full_name)) })
                : t("Today is {names}'s birthday. Wish them well.", { names: namesList(birthdaysToday.map(e => e.full_name)) })}
            </div>
          </div>

          <button
            onClick={() => setBirthdayDismissed(true)}
            style={{ background: "none", border: "none", cursor: "pointer", color: "var(--on-variant)", fontSize: 14, padding: "2px 4px", lineHeight: 1, flexShrink: 0 }}
            aria-label={t("Dismiss birthday banner")}
          >
            <i className="ti ti-x" />
          </button>
        </div>
      )}
    </div>
  );
}

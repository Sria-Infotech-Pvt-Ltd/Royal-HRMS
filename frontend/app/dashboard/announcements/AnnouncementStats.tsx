"use client";

import { averagePerPost } from "./_filters";
import { useT } from "@/hooks/useI18n";

interface AnnouncementStatsProps {
  posts:     number
  pinned:    number
  reactions: number
  views:     number
}

interface StatCard { label: string; value: number; icon: string; tone: string; sub: string }

/** The four totals over the whole feed (not just the filtered view), each with one line of context. */
export default function AnnouncementStats({ posts, pinned, reactions, views }: AnnouncementStatsProps) {
  const t = useT();
  const cards: StatCard[] = [
    { label: "Total Posts",     value: posts,     icon: "ti-speakerphone", tone: "si-primary", sub: posts === 0 ? t("Nothing posted yet") : t("In your feed") },
    { label: "Pinned",          value: pinned,    icon: "ti-pin",          tone: "si-warn",    sub: pinned === 0 ? t("Nothing pinned") : t("{pinned} of {posts} stay on top", { pinned, posts }) },
    { label: "Total Reactions", value: reactions, icon: "ti-heart",        tone: "si-success", sub: averagePerPost(reactions, posts) ?? t("No posts to average yet") },
    { label: "Total Views",     value: views,     icon: "ti-eye",          tone: "si-info",    sub: averagePerPost(views, posts) ?? t("No posts to average yet") },
  ]

  return (
    <div className="stats-grid">
      {cards.map(card => (
        <div className="stat-card" key={card.label}>
          <div className={`stat-icon ${card.tone}`}><i className={`ti ${card.icon}`} /></div>
          <div className="stat-label">{t(card.label)}</div>
          <div className="stat-value">{card.value.toLocaleString()}</div>
          <div className="stat-sub">{card.sub}</div>
        </div>
      ))}
    </div>
  )
}

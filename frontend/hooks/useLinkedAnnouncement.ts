"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { ANNOUNCEMENTS_PATH, ANNOUNCEMENT_OPEN_PARAM, parseLinkedAnnouncementId } from "@/lib/announcementLink";
import type { Announcement } from "@/app/dashboard/announcements/_data";

export interface LinkedAnnouncement {
  /** The announcement the link asked for, once loaded. A new object each time a link is followed. */
  announcement: Announcement | null;
  /** True when the link pointed at an announcement that is gone or was not meant for this person. */
  unavailable: boolean;
}

/**
 * Reads `?open=<announcement id>` from the URL and loads that announcement so the page can show it, for the bell notification and
 * the dashboard card. The request also marks the announcement's bell notification read. The parameter is removed from the URL once
 * handled, so a refresh does not reopen it and following the same link again works.
 */
export function useLinkedAnnouncement(): LinkedAnnouncement {
  const router = useRouter();
  const linkedId = parseLinkedAnnouncementId(useSearchParams().get(ANNOUNCEMENT_OPEN_PARAM));
  const [linked, setLinked] = useState<LinkedAnnouncement>({ announcement: null, unavailable: false });

  useEffect(() => {
    if (linkedId === null) return;
    let isCancelled = false;
    clientApi.get(API.announcements.detail(linkedId))
      .then(response => {
        if (!isCancelled) setLinked({ announcement: (response.data?.data as Announcement | undefined) ?? null, unavailable: false });
      })
      .catch(() => {
        if (!isCancelled) setLinked({ announcement: null, unavailable: true });
      })
      .finally(() => {
        if (!isCancelled) router.replace(ANNOUNCEMENTS_PATH, { scroll: false });
      });
    return () => { isCancelled = true; };
  }, [linkedId, router]);

  return linked;
}

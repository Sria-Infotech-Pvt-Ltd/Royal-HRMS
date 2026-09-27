"use client";

import { useCallback, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

type NormalisedError = { message?: string };

interface UseProfilePhotoUpload {
  uploading: boolean;
  error:     string | null;
  upload:    (file: File) => Promise<string | null>;
  remove:    () => Promise<boolean>;
}

// Every place that shows the current user's avatar (DashboardShell's header,
// the ESS Home banner, the My Profile tab, the old standalone Profile page)
// fetches employees/me INDEPENDENTLY, with no shared cache — uploading a new
// photo in one of them updates only that component's own local state. From
// the header/sidebar avatar's point of view (the one visible on literally
// every page, so the one a user is most likely watching), nothing appears
// to happen at all. Dispatching this event lets every mounted avatar
// consumer refetch itself the moment any one of them succeeds, without
// wiring a shared data-fetching layer just for this. Same
// window.dispatchEvent convention this app already uses for cross-component
// signals (see clientApi.ts's "session:expired").
export const PROFILE_PHOTO_UPDATED_EVENT = "profile-photo:updated";

/** Self-service upload/remove of the caller's own profile photo. See
 *  apps.accounts.views_profile_photo.ProfilePhotoView on the backend —
 *  every authenticated user manages their own, no permission gate. */
export function useProfilePhotoUpload(): UseProfilePhotoUpload {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(async (file: File): Promise<string | null> => {
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("photo", file);
      const res = await clientApi.post(API.employees.myPhoto, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const envelope = res.data as { data?: { profile_photo_url?: string | null } };
      const url = envelope.data?.profile_photo_url ?? null;
      window.dispatchEvent(new CustomEvent(PROFILE_PHOTO_UPDATED_EVENT, { detail: { url } }));
      return url;
    } catch (err: unknown) {
      setError((err as NormalisedError)?.message ?? "Upload failed. Please try again.");
      return null;
    } finally {
      setUploading(false);
    }
  }, []);

  const remove = useCallback(async (): Promise<boolean> => {
    setUploading(true);
    setError(null);
    try {
      await clientApi.delete(API.employees.myPhoto);
      window.dispatchEvent(new CustomEvent(PROFILE_PHOTO_UPDATED_EVENT, { detail: { url: null } }));
      return true;
    } catch (err: unknown) {
      setError((err as NormalisedError)?.message ?? "Failed to remove photo. Please try again.");
      return false;
    } finally {
      setUploading(false);
    }
  }, []);

  return { uploading, error, upload, remove };
}

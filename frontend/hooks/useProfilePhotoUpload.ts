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
      return envelope.data?.profile_photo_url ?? null;
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

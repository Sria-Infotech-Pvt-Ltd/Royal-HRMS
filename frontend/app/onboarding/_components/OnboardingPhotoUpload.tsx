"use client";

// Self-service equivalent of the Hire wizard's own EmployeePhotoUpload —
// same visual language (.photorow/.photodrop/.filebtn), but hits the real
// post-hire upload endpoint (ProfilePhotoView, apps.accounts.User.profile_photo)
// since this employee already has a real account, not a draft HireAction.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

interface Props {
  photoUrl: string | null;
  onPhotoChange: (url: string | null) => void;
}

export default function OnboardingPhotoUpload({ photoUrl, onPhotoChange }: Props) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append("photo", file);
      const { data } = await clientApi.post<{ data: { profile_photo_url: string } }>(
        API.employees.myPhoto, formData,
        { headers: { "Content-Type": "multipart/form-data" } },
      );
      onPhotoChange(data.data.profile_photo_url);
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(msg ?? "Could not upload this photo.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="photorow" style={{ marginBottom: 16 }}>
      <div className="photodrop" style={photoUrl ? { backgroundImage: `url(${photoUrl})` } : undefined}>
        {!photoUrl && <>ADD<br />PHOTO</>}
      </div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 700 }}>Employee photo</div>
        <div className="hint" style={{ margin: "3px 0 8px" }}>
          JPG or PNG — resized automatically to fit. Cropped to a circle on ID cards and reports.
        </div>
        <label className="filebtn" style={{ cursor: uploading ? "not-allowed" : "pointer", opacity: uploading ? 0.6 : 1 }}>
          {uploading ? "Uploading…" : "Upload file"}
          <input
            type="file"
            accept=".jpg,.jpeg,.png,image/jpeg,image/png"
            disabled={uploading}
            onChange={e => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) handleFile(file);
            }}
          />
        </label>
        {error && <div className="hint" style={{ color: "var(--crit)", marginTop: 4 }}>{error}</div>}
      </div>
    </div>
  );
}

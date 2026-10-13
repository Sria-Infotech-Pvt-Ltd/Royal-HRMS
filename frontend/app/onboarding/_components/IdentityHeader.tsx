"use client";

// Personal step's "Identity" card — self-service equivalent of the Hire
// wizard's own hardcoded Identity section (HireWizardClient.tsx): employee
// photo upload, Salutation/First/Middle/Last name, Display name (auto-
// suggested, same as Hire), Employee number. Unlike Hire (which is
// collecting a brand-new person's name), First/Middle/Last here are
// strictly read-only — an employee must never be able to rename themselves
// post-hire (see Role/Company Code's own equally-locked precedent) — only
// Salutation and Display Name are actually editable.
import { useEffect, useRef, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import OnboardingPhotoUpload from "./OnboardingPhotoUpload";
import type { ProfileForm } from "../_types";

interface Props {
  form: ProfileForm;
  onChange: (field: keyof ProfileForm, value: string) => void;
}

interface MeData {
  full_name: string;
  employee_id: string;
  profile_photo_url: string | null;
}

export default function IdentityHeader({ form, onChange }: Props) {
  const [me, setMe] = useState<MeData | null>(null);
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);

  useEffect(() => {
    clientApi.get<{ data: Record<string, unknown> }>(API.employees.me).then(r => {
      const d = r.data?.data;
      if (!d) return;
      setMe({
        full_name: String(d.full_name ?? ""),
        employee_id: String(d.employee_id ?? ""),
        profile_photo_url: d.profile_photo_url != null ? String(d.profile_photo_url) : null,
      });
      setPhotoUrl(d.profile_photo_url != null ? String(d.profile_photo_url) : null);
    }).catch(() => {});
  }, []);

  const [firstName, ...restName] = (me?.full_name ?? "").trim().split(/\s+/);
  const lastName = restName.join(" ");

  // Auto-fills Display Name from Salutation + real name, same "only while
  // untouched" rule the Hire wizard's own +Suggest button follows — never
  // clobbers a value the employee already customized themselves. Starts
  // "touched" if a display name was already saved from an earlier session
  // (loaded into `form` before this component mounts) — otherwise this
  // effect would silently overwrite it with a fresh auto-generated value
  // the instant `me` finishes loading.
  const displayNameTouchedRef = useRef(!!form.display_name);
  useEffect(() => {
    if (displayNameTouchedRef.current || !me) return;
    onChange("display_name", [form.salutation, me.full_name].filter(Boolean).join(" "));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.salutation, me?.full_name]);

  return (
    <div className="bg-[var(--surface)] rounded-2xl border border-[var(--outline-v)] shadow-sm p-5 mb-4">
      <OnboardingPhotoUpload photoUrl={photoUrl} onPhotoChange={setPhotoUrl} />

      <div className="text-[11px] font-bold uppercase tracking-wide mb-2" style={{ color: "var(--on-variant)" }}>Identity</div>
      <div className="grid grid-cols-3 gap-3 mb-3">
        <div>
          <label className="block text-[12.5px] font-semibold mb-1.5">Salutation <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>OPTIONAL</span></label>
          <select value={form.salutation} onChange={e => onChange("salutation", e.target.value)} className="field-input field-select">
            <option value="">Select</option>
            {["Mr.", "Ms.", "Mrs.", "Dr."].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
        <div>
          <label className="block text-[12.5px] font-semibold mb-1.5">First name</label>
          <div className="field-input" style={{ background: "var(--bg-mid)", color: "var(--on-variant)" }}>{firstName || "—"}</div>
        </div>
        <div>
          <label className="block text-[12.5px] font-semibold mb-1.5">Last name</label>
          <div className="field-input" style={{ background: "var(--bg-mid)", color: "var(--on-variant)" }}>{lastName || "—"}</div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div>
          <label className="block text-[12.5px] font-semibold mb-1.5">Display name <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>auto</span></label>
          <div className="flex gap-2">
            <input
              value={form.display_name}
              onChange={e => { displayNameTouchedRef.current = true; onChange("display_name", e.target.value); }}
              placeholder="Generated from name" className="field-input"
            />
            <button
              type="button"
              onClick={() => { displayNameTouchedRef.current = false; onChange("display_name", [form.salutation, me?.full_name].filter(Boolean).join(" ")); }}
              className="btn btn-sm" style={{ whiteSpace: "nowrap", background: "#7c3aed", color: "#ffffff", border: "none" }}
            >+ Suggest</button>
          </div>
          <p className="text-[11px] mt-1" style={{ color: "var(--on-variant)" }}>Shown across the app and in approvals.</p>
        </div>
        <div>
          <label className="block text-[12.5px] font-semibold mb-1.5">Employee number <span style={{ color: "var(--on-variant)", fontWeight: 400 }}>auto</span></label>
          <div className="field-input" style={{ background: "var(--bg-mid)", color: "var(--on-variant)" }}>{me?.employee_id || "—"}</div>
        </div>
      </div>
    </div>
  );
}

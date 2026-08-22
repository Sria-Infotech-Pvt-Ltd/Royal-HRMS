"use client";

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import type { WorkFromHomeRequest } from "@/types/workFromHome";

interface Coords { latitude: number; longitude: number; accuracy: number }

function fmtDate(iso: string): string {
  if (!iso) return "";
  return new Date(iso + "T12:00:00").toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

const INPUT     = "w-full border border-[var(--outline-v)] rounded-xl px-3.5 py-2.5 text-sm text-[var(--on-bg)] bg-[var(--surface)] outline-none transition focus:border-[var(--primary)] focus:ring-2 focus:ring-[var(--primary-c)] placeholder:text-[var(--on-variant)]";
const INPUT_ERR = "w-full border border-red-400 rounded-xl px-3.5 py-2.5 text-sm text-[var(--on-bg)] bg-red-50 outline-none";

function Lbl({ text, required }: { text: string; required?: boolean }) {
  return (
    <label className="block text-xs font-semibold text-[var(--on-variant)] mb-1.5 uppercase tracking-wide">
      {text}{required && <span className="text-red-500 ml-0.5 normal-case">*</span>}
    </label>
  );
}

function Err({ msg }: { msg?: string }) {
  if (!msg) return null;
  return (
    <p className="text-xs text-red-500 mt-1 flex items-center gap-1">
      <i className="ti ti-alert-circle text-xs" /> {msg}
    </p>
  );
}

export default function RequestWfhForm({ onSubmitted }: { onSubmitted: () => void }) {
  const { showToast } = useToast();
  const [startDate,   setStartDate]   = useState("");
  const [endDate,      setEndDate]     = useState("");
  const [reason,       setReason]      = useState("");
  const [locationLabel, setLocationLabel] = useState("");
  const [coords,       setCoords]      = useState<Coords | null>(null);
  const [locating,     setLocating]    = useState(false);
  const [locationError, setLocationError] = useState("");
  const [errors,       setErrors]      = useState<Record<string, string>>({});
  const [submitting,   setSubmitting]  = useState(false);
  const [submitted,    setSubmitted]   = useState<WorkFromHomeRequest | null>(null);

  function captureLocation() {
    setLocationError("");
    if (!navigator.geolocation) {
      setLocationError("Your browser doesn't support location capture.");
      return;
    }
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      pos => {
        setCoords({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        });
        setLocating(false);
      },
      err => {
        setLocationError(err.message || "Couldn't capture your location. Please allow location access and try again.");
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  function validate(): boolean {
    const e: Record<string, string> = {};
    if (!startDate) e.startDate = "Start date is required.";
    if (!endDate) e.endDate = "End date is required.";
    if (startDate && endDate && endDate < startDate) e.endDate = "End date must be on or after start date.";
    if (!coords) e.coords = "Capture your current location before submitting — this is what your clock-in will be checked against on WFH days.";
    setErrors(e);
    return Object.keys(e).length === 0;
  }

  async function handleSubmit() {
    if (!validate() || !coords) return;
    setSubmitting(true);
    try {
      const res = await clientApi.post(API.workFromHome.requests, {
        start_date: startDate,
        end_date: endDate,
        reason,
        location_label: locationLabel,
        latitude: coords.latitude,
        longitude: coords.longitude,
      });
      setSubmitted(res.data.data as WorkFromHomeRequest);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      showToast(msg || "Failed to submit request. Please try again.", "error");
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setStartDate(""); setEndDate(""); setReason(""); setLocationLabel("");
    setCoords(null); setLocationError(""); setErrors({}); setSubmitted(null);
  }

  if (submitted) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center p-6">
        <div className="bg-[var(--surface)] rounded-3xl border border-[var(--outline-v)] shadow-lg p-10 text-center w-full max-w-md">
          <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-6">
            <i className="ti ti-circle-check text-4xl text-green-600" />
          </div>
          <h2 className="text-xl font-bold text-[var(--on-bg)] mb-2">Request Submitted!</h2>
          <p className="text-sm text-[var(--on-variant)] mb-1">
            Your work-from-home request has been sent for approval.
          </p>
          <p className="text-xs text-[var(--on-variant)] mb-8">
            {fmtDate(submitted.start_date)} → {fmtDate(submitted.end_date)}
          </p>
          <div className="flex gap-3 justify-center">
            <button onClick={reset}
              className="px-5 py-2.5 rounded-xl border border-[var(--outline-v)] text-sm font-medium text-[var(--on-variant)] hover:bg-[var(--bg-low)]">
              Request Another
            </button>
            <button onClick={onSubmitted}
              className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white"
              style={{ background: "var(--primary)" }}>
              View My Requests
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-[var(--surface)] rounded-2xl border border-[var(--outline-v)] p-6 max-w-2xl">
      <div className="flex flex-col gap-5">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Lbl text="Start Date" required />
            <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
              className={errors.startDate ? INPUT_ERR : INPUT} />
            <Err msg={errors.startDate} />
          </div>
          <div>
            <Lbl text="End Date" required />
            <input type="date" value={endDate} min={startDate} onChange={e => setEndDate(e.target.value)}
              className={errors.endDate ? INPUT_ERR : INPUT} />
            <Err msg={errors.endDate} />
          </div>
        </div>

        <div>
          <Lbl text="Location Label" />
          <input type="text" value={locationLabel} onChange={e => setLocationLabel(e.target.value)}
            placeholder="e.g. Home" className={INPUT} />
        </div>

        <div>
          <Lbl text="Reason" />
          <textarea value={reason} onChange={e => setReason(e.target.value)} rows={3}
            placeholder="Optional — add context for your approver" className={INPUT} />
        </div>

        <div>
          <Lbl text="Your Location" required />
          <p className="text-xs text-[var(--on-variant)] mb-2">
            Captured once, from where you are right now — this is what your clock-in on approved WFH days gets checked against.
          </p>
          <button
            type="button"
            onClick={captureLocation}
            disabled={locating}
            suppressHydrationWarning
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold border-2 transition-all"
            style={coords
              ? { borderColor: "var(--success)", color: "var(--success)", background: "var(--success-c)" }
              : { borderColor: "var(--outline-v)", color: "var(--on-variant)" }}
          >
            {locating ? (
              <><i className="ti ti-loader-2 animate-spin text-sm" /> Capturing…</>
            ) : coords ? (
              <><i className="ti ti-map-pin-check text-sm" /> Location captured</>
            ) : (
              <><i className="ti ti-map-pin text-sm" /> Capture my current location</>
            )}
          </button>
          {coords && (
            <p className="text-xs text-[var(--on-variant)] mt-1.5">
              {coords.latitude.toFixed(6)}, {coords.longitude.toFixed(6)} (±{Math.round(coords.accuracy)}m)
            </p>
          )}
          {locationError && <Err msg={locationError} />}
          <Err msg={errors.coords} />
        </div>

        <div className="flex justify-end pt-2">
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            suppressHydrationWarning
            className="px-6 py-2.5 rounded-xl text-sm font-semibold text-white disabled:opacity-60"
            style={{ background: "var(--primary)" }}
          >
            {submitting ? "Submitting…" : "Submit Request"}
          </button>
        </div>
      </div>
    </div>
  );
}

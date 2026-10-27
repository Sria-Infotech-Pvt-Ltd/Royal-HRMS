"use client";

// Under the latitude / longitude fields of the branch form: a map of where those coordinates are, the server's check
// of them (impossible values, or a place that does not match the branch's state / city), and a button that fills the
// fields from this device's location, for an admin standing at the office.

import { useState } from "react";
import { toCoordinate, useBranchLocationCheck } from "@/hooks/useBranchLocationCheck";

interface Props {
  latitude: string;
  longitude: string;
  stateId: string;
  cityId: string;
  radiusMeters: string;
  onUseLocation: (latitude: string, longitude: string) => void;
}

const MAP_SPAN_DEGREES = 0.004;
const DECIMALS = 6;

function mapAddress(lat: number, lon: number): string {
  const bbox = [lon - MAP_SPAN_DEGREES, lat - MAP_SPAN_DEGREES * 0.75, lon + MAP_SPAN_DEGREES, lat + MAP_SPAN_DEGREES * 0.75].join(",");
  return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat},${lon}`;
}

export default function BranchLocationPreview({ latitude, longitude, stateId, cityId, radiusMeters, onUseLocation }: Props) {
  const check = useBranchLocationCheck(latitude, longitude, stateId, cityId);
  const [locating, setLocating] = useState(false);
  const [locateError, setLocateError] = useState<string | null>(null);

  const lat = toCoordinate(latitude);
  const lon = toCoordinate(longitude);
  const canShowMap = lat !== null && lon !== null && check.isValid;

  function useMyLocation() {
    if (!navigator.geolocation) { setLocateError("This browser cannot share its location."); return; }
    setLocating(true);
    setLocateError(null);
    navigator.geolocation.getCurrentPosition(
      position => {
        setLocating(false);
        onUseLocation(position.coords.latitude.toFixed(DECIMALS), position.coords.longitude.toFixed(DECIMALS));
      },
      () => { setLocating(false); setLocateError("Could not read this device's location. Allow location access and try again."); },
      { enableHighAccuracy: true, timeout: 15000 },
    );
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <button type="button" className="btn btn-ghost btn-sm" onClick={useMyLocation} disabled={locating}>
          <i className={`ti ${locating ? "ti-loader-2 animate-spin" : "ti-current-location"}`} /> Use my current location
        </button>
        {canShowMap && lat !== null && lon !== null && (
          <a href={`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=17/${lat}/${lon}`} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: "var(--primary)" }}>
            Open in OpenStreetMap <i className="ti ti-external-link" />
          </a>
        )}
        {check.isChecking && <span style={{ fontSize: 11, color: "var(--on-variant)" }}>Checking…</span>}
      </div>
      {locateError && <p className="field-error-msg">{locateError}</p>}

      {Object.values(check.errors).map(message => (
        <p key={message} className="field-error-msg" role="alert">{message}</p>
      ))}
      {check.warnings.map(message => (
        <div key={message} className="alert alert-warn" role="status" style={{ marginBottom: 8 }}>
          <i className="ti ti-alert-triangle" /> {message}
        </div>
      ))}

      {canShowMap && lat !== null && lon !== null ? (
        <>
          <iframe
            title="Office location"
            src={mapAddress(lat, lon)}
            style={{ width: "100%", height: 220, border: "1px solid var(--outline-v)", borderRadius: 8 }}
            loading="lazy"
            referrerPolicy="no-referrer"
            sandbox="allow-scripts allow-same-origin"
          />
          <div style={{ fontSize: 11, color: "var(--on-variant)", marginTop: 4 }}>
            The pin is where punches are measured from. Employees must be within {radiusMeters || "the allowed"} m of it.
          </div>
        </>
      ) : (
        <div style={{ fontSize: 11, color: "var(--on-variant)" }}>Enter both coordinates to see the office on a map.</div>
      )}
    </div>
  );
}

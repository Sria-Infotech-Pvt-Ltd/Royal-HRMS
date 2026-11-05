"use client";

// A small, dismissible prompt on the dashboard home pages for anyone whose Face ID still needs attention, with a
// "Register My Face" action. It never decides policy: everything comes from the server's one Face ID answer
// (useFaceVerificationStatus), so it follows the organisation's registration mode and fallback automatically:
//   - Face ID not mandatory, or this person is approved  -> nothing is shown.
//   - Not registered / rejected, employees may self-register -> message + "Register My Face".
//   - HR-in-person mode (employees cannot self-register)     -> the server's message ("ask HR"), no button.
//   - Pending HR approval                                     -> the server's message, no button.
// While a fallback allows office punches without a Face ID, the server's message already says so.
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import FaceRegistrationModal from "@/components/FaceRegistrationModal";
import { useFaceVerificationStatus } from "@/hooks/useFaceVerificationStatus";

// Where the banner may appear (the dashboard "home" pages only - never inside other modules).
const HOME_PATHS = new Set(["/dashboard", "/dashboard/ess", "/dashboard/team"]);
const DISMISS_KEY = "aira_face_banner_dismissed";

export default function FaceRegistrationBanner() {
  const pathname = usePathname();
  const { isMandatory, state, canSelfRegister, message, loading, refetch } = useFaceVerificationStatus({ asSignedInUser: true });
  const [dismissed, setDismissed] = useState(false);
  const [showModal, setShowModal] = useState(false);

  // Restored after mount so server and first client render agree.
  useEffect(() => {
    try { setDismissed(window.sessionStorage.getItem(DISMISS_KEY) === state); } catch { /* storage blocked */ }
  }, [state]);

  const needsAttention = isMandatory && state !== "approved";
  if (loading || !needsAttention || !HOME_PATHS.has(pathname)) return null;
  if (dismissed && !showModal) return null;

  const canAct = canSelfRegister && state !== "pending";
  const headline =
    state === "pending" ? "Face ID waiting for approval"
    : state === "rejected" ? "Face ID registration was rejected"
    : "Register your Face ID";

  function dismiss() {
    setDismissed(true);
    // Remembered per state for this browser session only: if the state changes (e.g. rejected later), it can show again.
    try { window.sessionStorage.setItem(DISMISS_KEY, state); } catch { /* storage blocked */ }
  }

  return (
    <>
      <div
        role="status"
        className="mb-4 flex items-center gap-3 rounded-lg px-4 py-2.5"
        style={{ background: "var(--primary-c, rgba(124,58,237,0.08))", border: "1px solid var(--outline-v)" }}
      >
        <i className="ti ti-face-id" style={{ fontSize: 20, color: "var(--primary)" }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: "var(--on-bg)" }}>{headline}</div>
          <div style={{ fontSize: 12, color: "var(--on-variant)" }}>{message}</div>
        </div>
        {canAct && (
          <button type="button" className="btn btn-primary btn-sm" suppressHydrationWarning onClick={() => setShowModal(true)}>
            <i className="ti ti-camera" /> Register My Face
          </button>
        )}
        <button
          type="button" aria-label="Dismiss" suppressHydrationWarning onClick={dismiss}
          className="w-7 h-7 flex items-center justify-center rounded-md hover:bg-black/5"
          style={{ color: "var(--on-variant)" }}
        >
          <i className="ti ti-x" style={{ fontSize: 16 }} />
        </button>
      </div>

      {showModal && (
        <FaceRegistrationModal
          mode={state === "rejected" ? "update" : "register"}
          onClose={() => { setShowModal(false); refetch(); }}
        />
      )}
    </>
  );
}

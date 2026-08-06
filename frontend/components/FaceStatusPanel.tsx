"use client";

// One reusable panel shape for every non-camera phase of any face-capture
// flow (intro, loading, denied, failed, submitting, submitted, error) — an
// icon, a headline, a message, and up to two actions. Keeps each modal
// (FaceRegistrationModal, FaceVerificationModal, ...) to a thin
// phase → props mapping.
interface StatusAction {
  label:   string;
  onClick: () => void;
}

interface FaceStatusPanelProps {
  icon:            string; // tabler icon name, e.g. "ti-camera-off"
  iconColor:       string;
  iconBg:          string;
  spinning?:       boolean;
  title:           string;
  message:         string;
  action?:         StatusAction;
  secondaryAction?: StatusAction;
}

export default function FaceStatusPanel({
  icon, iconColor, iconBg, spinning, title, message, action, secondaryAction,
}: FaceStatusPanelProps) {
  return (
    <div className="flex flex-col items-center text-center py-6 px-2">
      <div
        className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
        style={{ background: iconBg }}
      >
        <i className={`ti ${icon} ${spinning ? "animate-spin" : ""}`} style={{ fontSize: 28, color: iconColor }} />
      </div>
      <h3 className="text-base font-bold mb-1.5" style={{ color: "var(--on-bg)" }}>{title}</h3>
      <p className="text-sm mb-5 leading-relaxed" style={{ color: "var(--on-variant)", maxWidth: 320 }}>{message}</p>
      {(action || secondaryAction) && (
        <div className="flex gap-3">
          {secondaryAction && (
            <button className="btn btn-ghost btn-sm" suppressHydrationWarning onClick={secondaryAction.onClick}>
              {secondaryAction.label}
            </button>
          )}
          {action && (
            <button className="btn btn-primary btn-sm" suppressHydrationWarning onClick={action.onClick}>
              {action.label}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

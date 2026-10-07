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
  /** 0–1; renders a progress bar under the message when set. */
  progress?:       number;
}

export default function FaceStatusPanel({
  icon, iconColor, iconBg, spinning, title, message, action, secondaryAction, progress,
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
      {progress !== undefined && (
        <div className="mb-5 w-full" style={{ maxWidth: 260 }}>
          <div className="h-1.5 rounded-full overflow-hidden" style={{ background: "rgba(30,78,140,0.12)" }}>
            <div
              className="h-full rounded-full transition-all duration-200"
              style={{ width: `${Math.round(progress * 100)}%`, background: "var(--primary)" }}
            />
          </div>
          <p className="text-xs mt-1.5" style={{ color: "var(--on-variant)" }}>{Math.round(progress * 100)}%</p>
        </div>
      )}
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

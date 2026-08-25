"use client";

// One tap submits the phrase exactly like a typed command (onSubmitText),
// so it goes through the real /voice/parse/ pipeline — not a shortcut, not
// a different code path. Every phrase here is copied verbatim from
// backend/apps/voice_commands/registry/intents_en.yaml so a tap is
// guaranteed to match, and every one of these intents has
// required_permission: null — available to literally every authenticated
// employee, so the chips never need per-user permission filtering.
//
// Extracted out of VoiceConversationPanel.tsx (which only ever renders
// this one list) so the label/labelHi/phrase/icon tuple lives in exactly
// one place — the single source of truth for what a chip says, in either
// language, and what it actually does when tapped. Bilingual on purpose
// (VC-2): labelHi shows alongside label on every chip, not behind a
// language toggle — the backend's own Hindi response strings (registry of
// bilingual dicts across conversation_*.py/executor_*.py, Phases 3/3.1)
// have no equivalent for a UI button label (that rollout only ever
// produced spoken/displayed RESPONSE text), so these are new translations,
// not reused ones — chosen to match that existing vocabulary where the
// concepts overlap (क्लॉक-इन/क्लॉक-आउट, छुट्टी, उपस्थिति, आवेदन करना all
// appear verbatim in the backend's own Hindi strings already) rather than
// inventing different wording for the same thing. Flagged for the same
// native-speaker review Phases 3/3.1 already stood for their own new
// Hindi text — nobody on this project has confirmed these specific labels
// against a native speaker yet.
export interface QuickAction {
  label: string;
  labelHi: string;
  phrase: string;
  icon: string;
}

export const QUICK_ACTIONS: QuickAction[] = [
  { label: "Clock In",        labelHi: "क्लॉक-इन",                 phrase: "clock in",                   icon: "ti-login-2" },
  { label: "Clock Out",       labelHi: "क्लॉक-आउट",                phrase: "clock out",                  icon: "ti-logout-2" },
  { label: "Leave Balance",   labelHi: "छुट्टी का शेष",             phrase: "check my leave balance",     icon: "ti-calendar-stats" },
  { label: "Apply for Leave", labelHi: "छुट्टी के लिए आवेदन करें",   phrase: "apply for leave",            icon: "ti-calendar-plus" },
  { label: "My Attendance",   labelHi: "मेरी उपस्थिति",             phrase: "show my attendance summary", icon: "ti-clipboard-list" },
];

interface QuickActionChipsProps {
  onPick: (phrase: string) => void;
}

export default function QuickActionChips({ onPick }: QuickActionChipsProps) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {QUICK_ACTIONS.map(action => (
        <button
          key={action.phrase}
          onClick={() => onPick(action.phrase)}
          data-testid={`voice-quick-action-${action.phrase.replace(/\s+/g, "-")}`}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "5px 10px", borderRadius: 16, border: "1px solid var(--outline-v)",
            background: "var(--surface)", color: "var(--on-bg)", fontWeight: 500,
            cursor: "pointer", whiteSpace: "nowrap", textAlign: "left",
          }}
        >
          <i className={`ti ${action.icon}`} style={{ fontSize: 13, color: "var(--primary)" }} />
          {/* Stacked, not side-by-side ("Clock In / क्लॉक-इन") — at this
              chip's compact width, five side-by-side bilingual chips in a
              flex-wrap row would either force most onto their own line
              anyway (defeating the wrap layout) or need shrinking one
              language to stay narrow, which is exactly what this must NOT
              do. Two short lines keeps each language at a legible size and
              the chip's footprint close to its original single-line width. */}
          <span style={{ display: "flex", flexDirection: "column", lineHeight: 1.3 }}>
            <span style={{ fontSize: 11.5 }}>{action.label}</span>
            <span style={{ fontSize: 11, color: "var(--on-variant)" }}>{action.labelHi}</span>
          </span>
        </button>
      ))}
    </div>
  );
}

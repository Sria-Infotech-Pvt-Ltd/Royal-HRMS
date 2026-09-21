export interface VoiceParseResult {
  intent: string;
  confidence: number;
  result: unknown;
  message: string;
  // TTS confidentiality: the redacted stand-in for `message` that speech
  // synthesis should actually speak — null for almost every intent (speak
  // `message` unchanged, same as before this field existed). Set only for
  // intents whose `message` carries figures or a third party's personal
  // details (payslip amounts, leave balances/dates, another employee's
  // leave type) — see backend apps/voice_commands/executor_result.py's
  // ExecutionResult.speech_message. `message` itself is never redacted —
  // the panel/toast always shows full detail regardless of what's spoken.
  speech_message: string | null;
  // Always present. conversational: true for a multi-turn intent (apply_leave
  // today) on every one of its responses, including an immediate one-shot
  // submission — false for every other intent and for no-match. awaiting_input:
  // true only when this specific response is a clarification question expecting
  // a follow-up answer (pending state now exists server-side); false once a
  // conversational flow has completed, or whenever the intent was never
  // conversational to begin with. See backend apps/voice_commands/conversation.py.
  conversational: boolean;
  awaiting_input: boolean;
  // Whether the recognized intent's own action succeeded — false for a
  // genuinely terminal negative outcome (no-match, a rejected clock_in/out,
  // permission denied, etc.), true for everything else including a normal
  // mid-dialogue continuation (see conversation.py's _payload docstring).
  // Distinct from the HTTP call succeeding, which is a precondition for this
  // field existing at all.
  success: boolean;
  // The detected input language for THIS response — "en" or "hi" — present
  // on every response, not just ones with a Hindi counterpart to select
  // (see backend apps/voice_commands/conversation.py's _payload docstring).
  // Phase 4: drives which language POST /api/voice/speak/ is asked to
  // synthesize this response's spoken text in.
  language: "en" | "hi";
  // True only when this response is a low/mid-confidence "did you mean X?"
  // clarification question (backend apps/voice_commands/conversation_clarification.py)
  // — nothing has executed yet, so it's safe to silently discard the mic
  // transcript that produced it and retry through Hindi STT. False for every
  // other awaiting_input turn (ordinary slot-filling questions already ran
  // real logic and shouldn't be retried) and for every terminal outcome.
  is_clarification: boolean;
}

export type VoiceCommandStatus = "idle" | "listening" | "processing";

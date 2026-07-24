export interface VoiceParseResult {
  intent: string;
  confidence: number;
  result: unknown;
  message: string;
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
}

export type VoiceCommandStatus = "idle" | "listening" | "processing";

// Ambient types for the Web Speech API (window.SpeechRecognition /
// window.webkitSpeechRecognition). Not part of lib.dom.d.ts — Chromium-only,
// vendor-prefixed API — so declared here instead of using `any`.
//
// Everything must live inside `declare global` — this file has `export {}`
// at the bottom (making it a module), and once a .d.ts file is a module,
// only declarations inside `declare global` are visible outside it.

declare global {
  interface SpeechRecognitionResultLike {
    readonly isFinal: boolean;
    readonly length: number;
    [index: number]: {
      readonly transcript: string;
      // Per spec always present (0 when the engine does not estimate one), but kept optional because Chromium's
      // real-world behavior is not verified across engines/OS: callers must treat a missing value as "no
      // confidence signal", never as confidence 0 (see lib/voiceHindiRecovery.ts).
      readonly confidence?: number;
    };
  }

  interface SpeechRecognitionResultListLike {
    readonly length: number;
    [index: number]: SpeechRecognitionResultLike;
  }

  interface SpeechRecognitionEventLike extends Event {
    readonly resultIndex: number;
    readonly results: SpeechRecognitionResultListLike;
  }

  interface SpeechRecognitionErrorEventLike extends Event {
    readonly error: string;
  }

  interface SpeechRecognitionLike extends EventTarget {
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    start: () => void;
    stop: () => void;
    abort: () => void;
    onresult: ((event: SpeechRecognitionEventLike) => void) | null;
    onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
    onend: (() => void) | null;
  }

  type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

export {};

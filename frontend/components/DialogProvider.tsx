"use client";

// The app's own replacement for window.confirm() and window.prompt(): the same call shape (await it, get an answer), but a real
// modal that can be styled, tested and read by a screen reader. Mounted once in the root layout.
//
//   const confirm = useConfirm();
//   if (!(await confirm("Delete this draft?"))) return;
//
//   const ask = usePromptDialog();
//   const url = await ask({ title: "Insert link", inputLabel: "URL" });   // null when cancelled

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import ConfirmModal from "@/components/ConfirmModal";
import Modal from "@/components/Modal";

export interface ConfirmOptions {
  title?: string;
  body: string;
  confirmLabel?: string;
  /** Red confirm button: for deleting or otherwise irreversible actions. */
  danger?: boolean;
}

export interface PromptOptions {
  title: string;
  inputLabel: string;
  initialValue?: string;
  confirmLabel?: string;
}

const DESTRUCTIVE_WORDING = /delete|remove|permanently|can.?t be undone|cannot be undone/i;

type ConfirmFn = (options: ConfirmOptions | string) => Promise<boolean>;
type PromptFn = (options: PromptOptions) => Promise<string | null>;

interface DialogContextValue { confirm: ConfirmFn; ask: PromptFn }

const DialogContext = createContext<DialogContextValue | null>(null);

function useDialogContext(): DialogContextValue {
  const context = useContext(DialogContext);
  if (!context) throw new Error("useConfirm / usePromptDialog must be used inside DialogProvider");
  return context;
}

export function useConfirm(): ConfirmFn {
  return useDialogContext().confirm;
}

export function usePromptDialog(): PromptFn {
  return useDialogContext().ask;
}

// Plain functions for code that is not inside a component's render (event handlers, helpers): same dialogs, no hook needed.
// They work once DialogProvider has mounted; before that (or in a unit test without it) the answer is "no" / null.
let handlers: DialogContextValue | null = null;

export function confirmDialog(options: ConfirmOptions | string): Promise<boolean> {
  return handlers ? handlers.confirm(options) : Promise.resolve(false);
}

export function promptDialog(options: PromptOptions): Promise<string | null> {
  return handlers ? handlers.ask(options) : Promise.resolve(null);
}

type PendingDialog =
  | { kind: "confirm"; options: ConfirmOptions; resolve: (answer: boolean) => void }
  | { kind: "prompt"; options: PromptOptions; resolve: (answer: string | null) => void };

export function DialogProvider({ children }: { children: React.ReactNode }) {
  const [pending, setPending] = useState<PendingDialog | null>(null);
  const [inputValue, setInputValue] = useState("");
  const pendingRef = useRef<PendingDialog | null>(null);

  const open = useCallback((dialog: PendingDialog) => {
    pendingRef.current = dialog;
    setPending(dialog);
  }, []);

  const confirm = useCallback<ConfirmFn>(
    options => new Promise<boolean>(resolve => {
      // A plain string is a quick question; wording about deleting or undoing gets the red, careful button.
      const normalised = typeof options === "string" ? { body: options, danger: DESTRUCTIVE_WORDING.test(options) } : options;
      open({ kind: "confirm", options: normalised, resolve });
    }),
    [open],
  );

  const ask = useCallback<PromptFn>(
    options => new Promise<string | null>(resolve => {
      setInputValue(options.initialValue ?? "");
      open({ kind: "prompt", options, resolve });
    }),
    [open],
  );

  function finish(answer: boolean | string | null) {
    const dialog = pendingRef.current;
    pendingRef.current = null;
    setPending(null);
    if (!dialog) return;
    if (dialog.kind === "confirm") dialog.resolve(answer === true);
    else dialog.resolve(typeof answer === "string" ? answer : null);
  }

  const value = useMemo(() => ({ confirm, ask }), [confirm, ask]);
  useEffect(() => {
    handlers = value;
    return () => { if (handlers === value) handlers = null; };
  }, [value]);

  return (
    <DialogContext.Provider value={value}>
      {children}
      {pending?.kind === "confirm" && (
        <ConfirmModal
          title={pending.options.title ?? "Please confirm"}
          body={pending.options.body}
          confirmLabel={pending.options.confirmLabel ?? "Confirm"}
          danger={pending.options.danger}
          onConfirm={() => finish(true)}
          onCancel={() => finish(false)}
        />
      )}
      {pending?.kind === "prompt" && (
        <Modal
          title={<div className="text-[16px] font-bold">{pending.options.title}</div>}
          onClose={() => finish(null)}
          maxWidth={420}
          footer={
            <>
              <button className="btn btn-ghost" type="button" onClick={() => finish(null)}>Cancel</button>
              <button className="btn btn-filled" type="button" onClick={() => finish(inputValue)}>{pending.options.confirmLabel ?? "OK"}</button>
            </>
          }
        >
          <form onSubmit={event => { event.preventDefault(); finish(inputValue); }}>
            <label className="field-label" htmlFor="dialog-prompt-input">{pending.options.inputLabel}</label>
            <input
              id="dialog-prompt-input" className="field-input" value={inputValue} autoFocus
              onChange={event => setInputValue(event.target.value)}
            />
          </form>
        </Modal>
      )}
    </DialogContext.Provider>
  );
}

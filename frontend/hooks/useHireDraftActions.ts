"use client";

// The hire wizard's draft buttons, with one clear meaning each:
//   Save draft   keeps the draft and stays on the page
//   Save & exit  keeps the draft and closes the wizard
//   Discard      deletes the draft (after the app's own confirmation modal) and closes the wizard
// Every outcome is a toast; a failed save shows the server's message instead of being swallowed.

import { useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useToast } from "@/components/ToastProvider";
import { useApiErrors } from "@/hooks/useApiErrors";

interface UseHireDraftActionsArgs {
  hireActionId: string;
  /** Saves the wizard's current fields to the draft; rejects with the API error when it fails. */
  save: () => Promise<unknown>;
  onClose: () => void;
}

export function useHireDraftActions({ hireActionId, save, onClose }: UseHireDraftActionsArgs) {
  const { showToast } = useToast();
  const { handleError } = useApiErrors();
  const [isSaving, setIsSaving] = useState(false);
  const [isDiscardOpen, setIsDiscardOpen] = useState(false);
  const [isDiscarding, setIsDiscarding] = useState(false);

  async function saveDraft(): Promise<boolean> {
    setIsSaving(true);
    try {
      await save();
      showToast("Draft saved.", "success");
      return true;
    } catch (err: unknown) {
      handleError(err, "Could not save the draft.");
      return false;
    } finally {
      setIsSaving(false);
    }
  }

  async function saveAndExit() {
    if (await saveDraft()) onClose();
  }

  async function confirmDiscard() {
    setIsDiscarding(true);
    try {
      await clientApi.delete(API.hireActions.detail(hireActionId));
      showToast("Draft discarded.", "success");
      setIsDiscardOpen(false);
      onClose();
    } catch (err: unknown) {
      handleError(err, "Could not discard the draft.");
    } finally {
      setIsDiscarding(false);
    }
  }

  return {
    isSaving, isDiscardOpen, isDiscarding,
    saveDraft, saveAndExit, confirmDiscard,
    openDiscard: () => setIsDiscardOpen(true),
    closeDiscard: () => setIsDiscardOpen(false),
  };
}

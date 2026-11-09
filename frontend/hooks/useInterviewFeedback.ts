"use client";

import { useCallback, useState } from "react";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { FeedbackInput, MyInterview } from "@/types/interviewFeedback";

export const FEEDBACK_MIN_COMMENT_LENGTH = 10;

interface FeedbackDraft {
  rating: number;
  recommendation: string;
  comments: string;
}

/** Client-side mirror of the server's rules; the server stays the authority. Returns a message, or "" when valid. */
export function feedbackProblem(input: FeedbackDraft): string {
  if (!(input.rating >= 1 && input.rating <= 5)) return "Choose a rating from 1 to 5.";
  if (!input.recommendation) return "Choose Recommend, Undecided or Do not recommend.";
  if (input.comments.trim().length < FEEDBACK_MIN_COMMENT_LENGTH) {
    return `Write at least ${FEEDBACK_MIN_COMMENT_LENGTH} characters of comments.`;
  }
  return "";
}

/** Submits (or updates) the signed-in interviewer's feedback on one assigned interview. */
export function useSubmitFeedback() {
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");

  const submit = useCallback(async (interviewId: number, input: FeedbackInput): Promise<MyInterview | null> => {
    setIsSaving(true);
    setError("");
    try {
      const response = await clientApi.put<{ data: MyInterview }>(API.recruitment.myInterviewFeedback(interviewId), input);
      return response.data.data;
    } catch (err: unknown) {
      setError((err as { message?: string })?.message || "Could not save your feedback.");
      return null;
    } finally {
      setIsSaving(false);
    }
  }, []);

  return { submit, isSaving, error };
}

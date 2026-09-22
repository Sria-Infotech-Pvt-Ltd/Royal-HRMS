"use client";

// ESS "Documents" self-service submission list — a small, metadata-only
// "submit a document for verification" record. Deliberately separate from
// the org-wide Document Center (app/dashboard/documents), which keeps its
// own data layer in that route's _data.ts untouched.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";

export type DocumentCategory = "identity" | "education" | "employment" | "tax_proof" | "benefits" | "other";
export type DocumentStatus = "pending" | "verified" | "rejected";

export interface ApiDocumentSubmission {
  id: string;
  category: DocumentCategory;
  category_display: string;
  file_name: string;
  expiry_date: string | null;
  status: DocumentStatus;
  status_display: string;
  submitted_at: string;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

interface PagedResponse<T> { results: T[]; count: number }

export interface DocumentSubmissionInput {
  category: DocumentCategory;
  file_name: string;
  expiry_date: string | null;
}

export function useMyDocuments() {
  const { data, loading, error, refetch } =
    useFetch<PagedResponse<ApiDocumentSubmission>>(`${API.myDocuments.submissions}?page_size=20`);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  async function submit(input: DocumentSubmissionInput): Promise<boolean> {
    setSubmitError(null);
    setSubmitting(true);
    try {
      await clientApi.post(API.myDocuments.submissions, input);
      refetch();
      return true;
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setSubmitError(msg ?? "Failed to submit document. Please try again.");
      return false;
    } finally {
      setSubmitting(false);
    }
  }

  return {
    submissions: data?.results ?? [],
    loading,
    error,
    submitting,
    submitError,
    submit,
  };
}

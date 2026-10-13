"use client";

// ESS "Documents" self-service submission list — an employee submits a
// document (category, optional expiry, the file itself) for HR to verify, can
// view it again afterwards, and can delete it until HR has verified it.
// Deliberately separate from the org-wide Document Center
// (app/dashboard/documents), which keeps its own data layer in that route's
// _data.ts untouched.

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
  /** Short-lived signed link; null for submissions made before files were stored. */
  file_url: string | null;
  expiry_date: string | null;
  /** Key of the tax declaration item this document is proof for ("" for ordinary documents). */
  tax_item: string;
  reference_number: string;
  status: DocumentStatus;
  status_display: string;
  submitted_at: string;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

interface PagedResponse<T> { results: T[]; count: number }

export interface DocumentSubmissionInput {
  /** Not needed for tax proofs — giving a tax_item makes it a tax proof. */
  category?: DocumentCategory;
  file: File;
  expiry_date?: string | null;
  tax_item?: string;
  reference_number?: string;
}

function extractMessage(err: unknown, fallback: string): string {
  const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
  return message ?? fallback;
}

export function useMyDocuments() {
  const { data, loading, error, refetch } =
    useFetch<PagedResponse<ApiDocumentSubmission>>(`${API.myDocuments.submissions}?page_size=100`);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function submit(input: DocumentSubmissionInput): Promise<boolean> {
    setSubmitError(null);
    setSubmitting(true);
    try {
      const formData = new FormData();
      if (input.category) formData.append("category", input.category);
      formData.append("file", input.file);
      if (input.expiry_date) formData.append("expiry_date", input.expiry_date);
      if (input.tax_item) formData.append("tax_item", input.tax_item);
      if (input.reference_number) formData.append("reference_number", input.reference_number);
      await clientApi.post(API.myDocuments.submissions, formData);
      refetch();
      return true;
    } catch (err: unknown) {
      setSubmitError(extractMessage(err, "Failed to submit document. Please try again."));
      return false;
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(id: string): Promise<boolean> {
    setDeleteError(null);
    setDeletingId(id);
    try {
      await clientApi.delete(API.myDocuments.submissionDetail(id));
      refetch();
      return true;
    } catch (err: unknown) {
      setDeleteError(extractMessage(err, "Failed to delete document. Please try again."));
      return false;
    } finally {
      setDeletingId(null);
    }
  }

  return {
    submissions: data?.results ?? [],
    loading,
    error,
    refetch,
    submitting,
    submitError,
    submit,
    remove,
    deletingId,
    deleteError,
  };
}

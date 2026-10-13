"use client";

// ESS tax declaration — the form definition (items + limits, from the server) and
// the save / submit actions. Reading the employee's own declaration stays in TaxTab.

import { useState } from "react";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import type { TaxDeclarationSchema, TaxDeclaredInvestments, TaxRegime } from "@/types/taxDeclaration";

export function useTaxDeclarationSchema() {
  return useFetch<TaxDeclarationSchema>(API.payroll.taxDeclarationSchema, { cache: true });
}

export interface TaxDeclarationSaveInput {
  tax_regime: TaxRegime;
  declared_investments: TaxDeclaredInvestments;
}

export function useTaxDeclarationActions() {
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(action: () => Promise<unknown>, fallbackMessage: string): Promise<boolean> {
    setError(null);
    setIsBusy(true);
    try {
      await action();
      return true;
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setError(message ?? fallbackMessage);
      return false;
    } finally {
      setIsBusy(false);
    }
  }

  /** Saves the declaration as a draft (not yet sent to payroll). */
  function save(input: TaxDeclarationSaveInput): Promise<boolean> {
    return run(() => clientApi.patch(API.payroll.myTaxDeclaration, input), "Failed to save the declaration.");
  }

  /** Saves, then sends the declaration to payroll for review with the employee's confirmation. */
  function saveAndSubmit(input: TaxDeclarationSaveInput): Promise<boolean> {
    return run(async () => {
      await clientApi.patch(API.payroll.myTaxDeclaration, input);
      await clientApi.post(API.payroll.submitTaxDeclaration, { confirm: true });
    }, "Failed to submit the declaration.");
  }

  return { isBusy, error, setError, save, saveAndSubmit };
}

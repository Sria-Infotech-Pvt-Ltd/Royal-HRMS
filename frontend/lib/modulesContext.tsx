"use client";

// The company's modules (subscription) for any client component inside the
// dashboard, provided once by DashboardShell from the session. Widgets use it
// to leave out what belongs to a module the company doesn't have — the API
// enforces the same thing on its side.

import { createContext, useContext } from "react";
import { hasModule, type Modules } from "./modules";

const ModulesContext = createContext<Modules>(undefined);

export const ModulesProvider = ModulesContext.Provider;

export function useModules(): Modules {
  return useContext(ModulesContext);
}

/** True when the company has `key` (or the module list is unknown — older token). */
export function useHasModule(key: string): boolean {
  return hasModule(useContext(ModulesContext), key);
}

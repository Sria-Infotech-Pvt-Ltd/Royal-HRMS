"use client";

// Named per the CLAUDE.md-aligned spec (components/dashboard/StatCard.tsx).
// Re-exports the existing KpiTile implementation from ModuleOverviewKit —
// that same tile is already shared across every module's overview page
// (Leave/Payroll/Performance/Reports/Settings/Organization), so this is a
// naming alias, not a second implementation.
export { KpiTile as StatCard } from "./ModuleOverviewKit";

"use client";

// Print-only copy of a payslip, rendered directly under <body> so the print
// stylesheet can hide the rest of the app (navigation, sidebar, buttons) — the
// same approach as the ID card. Shared by My Payslips and the HR payslip view.
// "Save as PDF" comes from the browser's print dialog.

import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

export const PAYSLIP_PRINT_CSS = `
  @media screen { .payslip-print-root { display: none; } }
  @media print {
    @page { size: A4; margin: 10mm; }
    body > *:not(.payslip-print-root) { display: none !important; }
    .payslip-print-root { display: block !important; }
    .payslip-print-root, .payslip-print-root * { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
    .payslip-print-root .payslip-doc { box-shadow: none !important; max-width: none !important; margin: 0 !important; }
    .payslip-print-root .payslip-earn-ded,
    .payslip-print-root .payslip-net { break-inside: avoid; page-break-inside: avoid; }
  }
`;

export default function PayslipPrintCopy({ children }: { children: ReactNode }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return null;
  return createPortal(
    <div className="payslip-print-root"><style>{PAYSLIP_PRINT_CSS}</style>{children}</div>,
    document.body,
  );
}

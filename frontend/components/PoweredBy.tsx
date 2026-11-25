"use client";

import { useT } from "@/hooks/useI18n";
import { PRODUCT } from "@/lib/brand";

/** A small "Powered by AIRA" with the AIRA mark: where the screen belongs to the company, this says which software it is. */
export default function PoweredBy() {
  const t = useT();
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11.5, color: "var(--muted)" }}>
      {/* eslint-disable-next-line @next/next/no-img-element -- a 16px project asset: next/image adds nothing here */}
      <img src={PRODUCT.logo} alt="" width={16} height={16} style={{ height: 16, width: "auto" }} />
      {t("Powered by {brand}", { brand: PRODUCT.name })}
    </span>
  );
}

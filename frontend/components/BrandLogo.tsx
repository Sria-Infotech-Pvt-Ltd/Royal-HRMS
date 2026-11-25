"use client";

import { useBranding } from "@/hooks/useBranding";

/** The logo of the company that uses the app (the AIRA mark until one is uploaded), as a plain image of a given height. */
export default function BrandLogo({ height }: { height: number }) {
  const { companyLogo, companyName, productName, productLogo } = useBranding();
  const alt = companyLogo ? (companyName ?? productName) : productName;
  // eslint-disable-next-line @next/next/no-img-element -- the company's own uploaded file, any size and host, not a project asset
  return <img src={companyLogo ?? productLogo} alt={alt} style={{ height, width: "auto", objectFit: "contain" }} />;
}

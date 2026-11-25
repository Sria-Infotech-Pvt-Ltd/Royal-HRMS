"use client";

import { useBranding } from "@/hooks/useBranding";

function ProductMark() {
  return (
    <>
      <span className="sq">
        <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}>
          <path d="M12 3 21 8v8l-9 5-9-5V8z" />
        </svg>
      </span>
      <div className="brandcopy">
        <strong>AIRA</strong>
      </div>
    </>
  );
}

/** The top-left corner of the app: the COMPANY's logo (Settings > Company Info), because this is the company's workspace. Until a logo is
 *  uploaded it is the AIRA mark. While the first answer loads the corner holds its place, so the AIRA mark never flashes before the logo. */
export default function BrandMark() {
  const { companyLogo, companyName, productName, isLoading } = useBranding();
  if (isLoading) return <div className="brandmark" aria-hidden="true" style={{ visibility: "hidden" }}><ProductMark /></div>;
  if (!companyLogo) return <div className="brandmark"><ProductMark /></div>;
  return (
    <div className="brandmark">
      {/* eslint-disable-next-line @next/next/no-img-element -- the company's own uploaded file, any size and host, not a project asset */}
      <img src={companyLogo} alt={companyName ?? productName} style={{ height: 34, width: "auto", maxWidth: 190, objectFit: "contain" }} />
    </div>
  );
}

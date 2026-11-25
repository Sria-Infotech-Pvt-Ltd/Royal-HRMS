"use client";

import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import { PRODUCT } from "@/lib/brand";

interface PublicBranding { company_name: string | null; logo_url: string | null }

export interface Branding {
  /** The company that uses the product, from Settings > Company Info; null until it loads or when none is set up. */
  companyName: string | null;
  companyLogo: string | null;
  productName: string;
  productLogo: string;
  /** True only while the very first answer is on its way, so a screen can hold its place instead of flashing the wrong logo. */
  isLoading: boolean;
}

/** Who is who on the screen: the company's name and logo (white label) and the product's own (AIRA). One cached public request, no sign-in needed. */
export function useBranding(): Branding {
  const { data, loading } = useFetch<PublicBranding>(API.companyPublicBranding, { cache: true, asSignedInUser: true });
  return {
    companyName: data?.company_name ?? null,
    companyLogo: data?.logo_url ?? null,
    productName: PRODUCT.name,
    productLogo: PRODUCT.logo,
    isLoading: loading && !data,
  };
}

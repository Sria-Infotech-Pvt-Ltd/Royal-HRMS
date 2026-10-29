"use client";

// Employee Dashboard: documents (e.g. Company Policy) the signed-in employee
// still has to read and acknowledge. Renders nothing when there are none.

import Link from "next/link";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";

interface PendingDoc { id: number; title: string; category: string; version: number }

export default function PendingAcknowledgementsBanner() {
  const { data } = useFetch<PendingDoc[]>(API.companyPolicy.pendingAcknowledgements);
  if (!data || data.length === 0) return null;
  return (
    <div className="alert alert-warn mb-16" role="status" style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <i className="ti ti-signature" />
      <span>
        Please read and acknowledge: <strong>{data.map(d => d.title).join(", ")}</strong>
      </span>
      <Link href="/dashboard/documents?category=policy" className="btn btn-outline btn-sm" style={{ marginLeft: "auto" }}>
        Open
      </Link>
    </div>
  );
}

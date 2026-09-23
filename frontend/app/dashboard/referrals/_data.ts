import type { Candidate, CandidateStatus } from "@/app/dashboard/interview-list/_data";

export interface ReferralRule {
  id:        number;
  icon:      string;
  title:     string;
  body:      string;
  order:     number;
  is_active: boolean;
}

export interface ReferralStats {
  total_referred: number;
  in_pipeline:    number;
  selected:       number;
  converted:      number;
}

export interface ReferralListResponse {
  results:     Candidate[];
  count:       number;
  stats:       ReferralStats;
}

export const STATUS_META: Record<CandidateStatus, { label: string; cls: string }> = {
  pending:             { label: "Pending",        cls: "badge-neutral" },
  screening:           { label: "Screening",      cls: "badge-info"    },
  interview_scheduled: { label: "Scheduled",      cls: "badge-info"    },
  interview_done:      { label: "Interview Done", cls: "badge-warn"    },
  selected:            { label: "Selected",       cls: "badge-success" },
  offer_sent:          { label: "Offer Sent",     cls: "badge-success" },
  rejected:            { label: "Rejected",       cls: "badge-error"   },
  converted:           { label: "Converted",      cls: "badge-neutral" },
};

export const RELATIONSHIP_OPTIONS = [
  "Friend / Acquaintance",
  "Former Colleague",
  "Professional Contact",
  "Family Member",
  "Ex-Employee at Previous Company",
  "Other",
];

export const EMPTY_FORM = {
  name: "", email: "", phone: "", position_applied: "", branch: "", relationship: "", notes: "",
};

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { useOnboardingQueue } from "@/hooks/useOnboardingQueue";
import { usePermission } from "@/hooks/usePermission";
import { useCurrentUser } from "@/hooks/useCurrentUser";
import OnboardingDrawer, { ApprovalUser } from "./_components/OnboardingDrawer";
import ApprovalsHeader from "./ApprovalsHeader";
import ApprovalStatCards from "./ApprovalStatCards";
import ApprovalToolbar from "./ApprovalToolbar";
import ApprovalsTable from "./ApprovalsTable";
import { tr } from "@/lib/i18n/tr";

export default function CandidateReviewPage() {
  const router       = useRouter();
  const currentUser  = useCurrentUser();
  const canApproveEmployees  = usePermission("employees.approve");
  const canApproveOnboarding = usePermission("onboarding.approve");
  const canApprove           = canApproveEmployees || canApproveOnboarding;
  const isSystemAdmin        = currentUser?.is_superuser === true;

  const queue = useOnboardingQueue();

  const [drawer,    setDrawer]    = useState<ApprovalUser | null>(null);
  const [remarks,   setRemarks]   = useState("");
  const [acting,    setActing]    = useState(false);
  const [actionErr, setActionErr] = useState<string | null>(null);

  async function handleOnboardingAction(
    userId: string,
    decision: "approve" | "reject",
    extras?: { position?: string; assessmentId?: string; uanNumber?: string; aadharName?: string; panNumber?: string },
  ) {
    setActing(true); setActionErr(null);
    try {
      // The approval endpoint already assigns default assessments and honors an
      // explicit assessment_id for a non-default pick in the same request — a
      // separate /assessments/assign/ call here would just 409 on anything that
      // was already auto-assigned as a default.
      await clientApi.post(API.onboarding.approve(userId), {
        decision,
        remarks,
        position:           extras?.position      || undefined,
        assessment_id:      extras?.assessmentId,
        uan_number:         extras?.uanNumber    || undefined,
        name_as_per_aadhar: extras?.aadharName   || undefined,
        pan_number:         extras?.panNumber    || undefined,
      });
      setDrawer(null); setRemarks("");
      if (decision === "approve") {
        router.push("/dashboard/employees");
      } else {
        queue.reload();
      }
    } catch (err: unknown) {
      setActionErr((err as { message?: string })?.message ?? tr("Action failed."));
    } finally {
      setActing(false);
    }
  }

  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push("/dashboard");
  };

  return (
    <div className="cand-page">
      <ApprovalsHeader onBack={goBack} onRefresh={queue.reload} isLoading={queue.isLoading} />
      <ApprovalStatCards counts={queue.counts} activeStatus={queue.status} onSelect={queue.setStatus} />
      <ApprovalToolbar
        search={queue.searchText} onSearch={queue.setSearch} status={queue.status} onStatus={queue.setStatus}
        hasFilters={queue.hasFilters} onClear={queue.clearFilters}
      />
      <ApprovalsTable
        rows={queue.rows} matching={queue.matching} page={queue.page} pageSize={queue.pageSize} totalPages={queue.totalPages}
        onPageChange={queue.setPage} isLoading={queue.isLoading} error={queue.error} onRetry={queue.reload}
        hasFilters={queue.hasFilters} onClearFilters={queue.clearFilters}
        canApprove={canApprove} showBranch={isSystemAdmin}
        onReview={row => { setDrawer(row); setRemarks(""); setActionErr(null); }}
      />

      <style>{`
        @media (max-width: 768px) { .col-hide-md { display: none; } }
        @media (max-width: 560px) { .col-hide-sm { display: none; } }
      `}</style>

      {drawer && (
        <OnboardingDrawer
          user={drawer}
          remarks={remarks}
          acting={acting}
          actionErr={actionErr}
          onRemarksChange={setRemarks}
          onAction={handleOnboardingAction}
          onClose={() => setDrawer(null)}
        />
      )}
    </div>
  );
}

"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { confirmDialog } from "@/components/DialogProvider";
import { usePerformanceHub } from "@/hooks/usePerformanceHub";
import { filterReviews, needsHr, reviewStage, type StageFilter } from "@/lib/performanceHub";
import type { ApiReview } from "@/types/performanceHub";
import PerformanceHeader, { type HubTab } from "./PerformanceHeader";
import OverviewTab from "./OverviewTab";
import ReviewQueueTab from "./ReviewQueueTab";
import CyclesTab from "./CyclesTab";
import CreateCycleModal from "./CreateCycleModal";
import ReviewActionModal from "./ReviewActionModal";

/** Performance, as HR runs it: an overview, the review queue, and the cycles. */
export default function PerformanceHub() {
  const router = useRouter();
  const hub = usePerformanceHub();
  const [tab, setTab] = useState<HubTab>("overview");
  const [search, setSearch] = useState("");
  const [stage, setStage] = useState<StageFilter>("");
  const [showCreate, setShowCreate] = useState(false);
  const [reviewing, setReviewing] = useState<ApiReview | null>(null);
  const [today] = useState(() => new Date());

  const reviews = useMemo(() => hub.data?.reviews ?? [], [hub.data]);
  const visible = useMemo(() => filterReviews(reviews, search, stage), [reviews, search, stage]);
  const needsHrCount = useMemo(() => reviews.filter(review => needsHr(reviewStage(review))).length, [reviews]);

  const goBack = () => {
    if (window.history.length > 1) router.back();
    else router.push("/dashboard");
  };
  const openQueue = (nextStage: StageFilter) => { setStage(nextStage); setSearch(""); setTab("queue"); };
  const closeCycle = async (id: string) => {
    if (await confirmDialog("Close this review cycle? Closed cycles cannot be reopened.")) hub.close(id);
  };

  return (
    <div className="cand-page">
      <PerformanceHeader tab={tab} onTab={setTab} onBack={goBack} needsHrCount={needsHrCount} cycleCount={hub.cycles.length} />

      {hub.error && (
        <div className="alert alert-error"><i className="ti ti-alert-circle" /><div>{hub.error}</div>
          <button type="button" className="btn-link" style={{ marginLeft: "auto" }} onClick={hub.reload}>Try again</button>
        </div>
      )}

      <div id="perf-panel" role="tabpanel" aria-labelledby={`perf-tab-${tab}`} className="perf-panel">
        {tab === "overview" && (
          <OverviewTab
            data={hub.data} cycles={hub.cycles} today={today} isLoading={hub.isLoading} busyId={hub.busyId}
            onOpenQueue={openQueue} onOpenCycles={() => setTab("cycles")} onCreate={() => setShowCreate(true)}
            onActivate={hub.activate} onReview={setReviewing} onChanged={hub.reload}
          />
        )}
        {tab === "queue" && (
          <ReviewQueueTab
            cycle={hub.data?.cycle ?? null} reviews={reviews} visible={visible} today={today} isLoading={hub.isLoading}
            search={search} onSearch={setSearch} stage={stage} onStage={setStage} onClear={() => { setSearch(""); setStage(""); }}
            onReview={setReviewing} onChanged={hub.reload}
          />
        )}
        {tab === "cycles" && (
          <CyclesTab
            cycles={hub.cycles} today={today} isLoading={hub.isLoading} busyId={hub.busyId} error={hub.actionError} onDismissError={hub.clearActionError}
            onCreate={() => setShowCreate(true)} onActivate={hub.activate} onClose={closeCycle}
          />
        )}
      </div>

      {showCreate && <CreateCycleModal onClose={() => setShowCreate(false)} onCreated={() => { setShowCreate(false); hub.reload(); setTab("cycles"); }} />}
      {reviewing && <ReviewActionModal review={reviewing} onClose={() => setReviewing(null)} onSaved={() => { setReviewing(null); hub.reload(); }} />}
    </div>
  );
}

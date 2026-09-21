"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import clientApi from "@/lib/clientApi";
import { API } from "@/lib/api/endpoints";
import { setAssessmentStatus, clearAuth } from "@/lib/auth";

// ── Types ─────────────────────────────────────────────────────────────────────

type ItemType    = "video" | "quiz";
type AssignStatus = "pending" | "in_progress" | "complete";

interface AssignmentItem {
  id: string; item_type: ItemType; title: string; order: number;
  section_id: string | null; section_title: string | null;
  video_url: string; duration_secs: number | null;
  question: string; option_a: string; option_b: string; option_c: string; option_d: string;
  correct_option: string; pass_score: number; created_at: string;
}
interface ItemResponse {
  item_id: string; item_type: ItemType; is_watched: boolean;
  selected_option: string; is_correct: boolean | null; score_awarded: number; responded_at: string;
}
interface AttemptRecord {
  attempt_number: number; score: number; max_score: number; passed: boolean; completed_at: string;
}
interface Assignment {
  id: string; assessment_title: string; status: AssignStatus;
  score: number; max_score: number; passed?: boolean;
  total_items: number; completed_items: number; completed_at: string | null;
  attempt_number: number; items: AssignmentItem[]; responses: ItemResponse[]; attempts: AttemptRecord[];
  attempt_count:          number;
  effective_max_attempts: number;   // 0 = unlimited
  attempts_remaining:     number | null;
  started_at:             string | null;
  time_limit_mins:        number | null;
  time_remaining_secs:    number | null;
}
interface MyAssessmentsData { all_complete: boolean; assignments: Assignment[]; }
interface RespondData {
  item_id: string; item_type: ItemType; is_correct: boolean | null;
  score_awarded: number; assignment_score: number;
}
interface CompleteData { score: number; max_score: number; passed: boolean; }
interface PanelState {
  item: AssignmentItem; assignmentId: string;
  itemIndex: number; totalItems: number; maxScore: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const OPTIONS: { key: "a" | "b" | "c" | "d"; field: keyof AssignmentItem }[] = [
  { key: "a", field: "option_a" }, { key: "b", field: "option_b" },
  { key: "c", field: "option_c" }, { key: "d", field: "option_d" },
];

function isItemDone(item: AssignmentItem, responses: ItemResponse[]): boolean {
  const r = responses.find(x => x.item_id === item.id);
  if (!r) return false;
  return item.item_type === "video" ? r.is_watched : r.selected_option !== "";
}

function toEmbedUrl(url: string): string | null {
  // Already an embed URL — pass through
  const already = url.match(/youtube\.com\/embed\/([^?&/]+)/);
  if (already) return `https://www.youtube.com/embed/${already[1]}`;
  const alreadyV = url.match(/player\.vimeo\.com\/video\/(\d+)/);
  if (alreadyV) return `https://player.vimeo.com/video/${alreadyV[1]}`;

  // youtu.be share link
  const short = url.match(/youtu\.be\/([^?&/]+)/);
  if (short) return `https://www.youtube.com/embed/${short[1]}`;

  // Standard watch URL
  const watch = url.match(/[?&]v=([^?&]+)/);
  if (watch) return `https://www.youtube.com/embed/${watch[1]}`;

  // Shorts and Live
  const shorts = url.match(/youtube\.com\/shorts\/([^?&/]+)/);
  if (shorts) return `https://www.youtube.com/embed/${shorts[1]}`;
  const live = url.match(/youtube\.com\/live\/([^?&/]+)/);
  if (live) return `https://www.youtube.com/embed/${live[1]}`;

  // Vimeo
  const vimeo = url.match(/vimeo\.com\/(\d+)/);
  if (vimeo) return `https://player.vimeo.com/video/${vimeo[1]}`;

  return null;
}

// ── Completion Modal ──────────────────────────────────────────────────────────

function CompletionModal({ result, title, attemptNumber, isLastPending, retaking, onRetake, onContinue, onDashboard }: {
  result: CompleteData; title: string; attemptNumber: number; isLastPending: boolean;
  retaking: boolean; onRetake: () => void; onContinue: () => void; onDashboard: () => void;
}) {
  const pct = result.max_score > 0 ? Math.round((result.score / result.max_score) * 100) : 0;
  const R = 52; const C = 2 * Math.PI * R;
  const passed = result.passed;
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(15,23,42,0.75)", backdropFilter: "blur(4px)", zIndex: 60, display: "flex", alignItems: "center", justifyContent: "center", padding: 16 }}>
      <div style={{ background: "var(--surface)", borderRadius: 20, width: "100%", maxWidth: 380, boxShadow: "0 25px 60px rgba(0,0,0,0.25)", overflow: "hidden" }}>
        <div style={{ height: 4, background: passed ? "linear-gradient(90deg,#16a34a,#22c55e)" : "linear-gradient(90deg,#dc2626,#ef4444)" }} />
        <div style={{ padding: "32px 32px 28px", textAlign: "center" }}>
          <div style={{ position: "relative", width: 136, height: 136, margin: "0 auto 20px" }}>
            <svg width="136" height="136" style={{ transform: "rotate(-90deg)" }}>
              <circle cx="68" cy="68" r={R} fill="none" stroke="#f1f5f9" strokeWidth="10" />
              <circle cx="68" cy="68" r={R} fill="none" stroke={passed ? "#16a34a" : "#ef4444"} strokeWidth="10" strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C - (pct / 100) * C} style={{ transition: "stroke-dashoffset 0.8s ease" }} />
            </svg>
            <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
              <span style={{ fontSize: 28, fontWeight: 800, color: "#0f172a", lineHeight: 1 }}>{result.score}</span>
              <span style={{ fontSize: 12, color: "#94a3b8" }}>/ {result.max_score}</span>
            </div>
          </div>
          <div style={{ display: "inline-flex", alignItems: "center", gap: 6, background: passed ? "#dcfce7" : "#fee2e2", borderRadius: 20, padding: "4px 14px", marginBottom: 8 }}>
            <i className={`ti ${passed ? "ti-circle-check" : "ti-circle-x"}`} style={{ color: passed ? "#16a34a" : "#dc2626", fontSize: 14 }} />
            <span style={{ fontSize: 13, fontWeight: 700, color: passed ? "#15803d" : "#dc2626" }}>{passed ? "Passed" : "Not Passed"}</span>
          </div>
          <p style={{ fontSize: 20, fontWeight: 700, color: "#0f172a", margin: "0 0 4px" }}>{pct}% Score</p>
          <p style={{ fontSize: 13, color: "#64748b", margin: "0 0 24px" }}>{title} · Attempt #{attemptNumber}</p>
          {passed && isLastPending ? (
            <button suppressHydrationWarning onClick={onDashboard} style={{ width: "100%", padding: "12px 0", borderRadius: 10, background: "#7c3aed", color: "#fff", fontWeight: 600, fontSize: 14, border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              Go to Dashboard <i className="ti ti-arrow-right" />
            </button>
          ) : passed ? (
            <button suppressHydrationWarning onClick={onContinue} style={{ width: "100%", padding: "12px 0", borderRadius: 10, background: "#7c3aed", color: "#fff", fontWeight: 600, fontSize: 14, border: "none", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              Continue to Next Assessment <i className="ti ti-arrow-right" />
            </button>
          ) : (
            <button suppressHydrationWarning onClick={onRetake} disabled={retaking} style={{ width: "100%", padding: "12px 0", borderRadius: 10, background: retaking ? "#94a3b8" : "#dc2626", color: "#fff", fontWeight: 600, fontSize: 14, border: "none", cursor: retaking ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              {retaking ? <><i className="ti ti-loader-2 spin" />Starting…</> : <><i className="ti ti-refresh" />Re-take Assessment</>}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function AssessmentsPage() {
  const router = useRouter();
  const { data, loading, error, refetch } = useFetch<MyAssessmentsData>(API.assessments.my);

  // Panel (inline content area) state
  const [selectedPanel, setSelectedPanel]   = useState<PanelState | null>(null);
  const [panelResult, setPanelResult]       = useState<RespondData | null>(null);
  const [panelSaving, setPanelSaving]       = useState(false);
  const [panelError, setPanelError]         = useState("");
  const [panelSelected, setPanelSelected]   = useState("");
  const [panelRunScore, setPanelRunScore]   = useState(0);

  // Sidebar section collapse — key: `${assignmentId}|${sectionId}`, all open by default
  const [openSections, setOpenSections] = useState<Set<string>>(new Set());

  function toggleSection(key: string) {
    setOpenSections(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  // Countdown timers (seconds remaining per assignment, initialised from API)
  const [timers, setTimers]         = useState<Record<string, number>>({});
  const timerRef                    = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoSubmitting              = useRef<Set<string>>(new Set());

  // Initialise timers once data arrives (only for timed assignments that have started)
  useEffect(() => {
    if (!data) return;
    setTimers(prev => {
      const next = { ...prev };
      for (const a of data.assignments) {
        if (a.time_remaining_secs != null && !(a.id in next)) {
          next[a.id] = a.time_remaining_secs;
        }
      }
      return next;
    });
  }, [data]);

  // Tick every second; auto-submit any assignment whose timer hits 0
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setTimers(prev => {
        const next = { ...prev };
        let changed = false;
        for (const id of Object.keys(next)) {
          if (next[id] > 0) { next[id]--; changed = true; }
          if (next[id] === 0 && !autoSubmitting.current.has(id)) {
            autoSubmitting.current.add(id);
            // fire-and-forget auto-submit
            clientApi.post(API.assessments.complete(id))
              .then(() => refetch())
              .catch(() => { /* silent — user sees completed state on next refetch */ });
          }
        }
        return changed ? next : prev;
      });
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [refetch]);

  function fmtTimer(secs: number): string {
    const m = Math.floor(secs / 60).toString().padStart(2, "0");
    const s = (secs % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  }

  // Completion/retake state
  const [completing, setCompleting]           = useState<string | null>(null);
  const [finalResults, setFinalResults]       = useState<Record<string, CompleteData>>({});
  const [completeError, setCompleteError]     = useState<Record<string, string>>({});
  const [completionModal, setCompletionModal] = useState<{ result: CompleteData; title: string; assignmentId: string; attemptNumber: number; isLastPending: boolean } | null>(null);
  const [retaking, setRetaking]               = useState<string | null>(null);
  const [retakeError, setRetakeError]         = useState<Record<string, string>>({});

  const assignments = data?.assignments ?? [];

  // Only mark complete when the backend confirms AND there is at least one assignment.
  // all_complete is vacuously true when assignments is empty — do not unlock the proxy in that case.
  const allComplete = data?.all_complete === true && assignments.length > 0;

  useEffect(() => { if (allComplete) setAssessmentStatus("complete"); }, [allComplete]);

  const [loggingOut, setLoggingOut] = useState(false);
  async function handleLogout() {
    setLoggingOut(true);
    try { await clientApi.post(API.auth.logout, {}); } catch { /* ignore */ }
    clearAuth();
    router.push("/login");
  }

  // ── Panel helpers ──

  function openItem(item: AssignmentItem, assignment: Assignment) {
    setPanelResult(null); setPanelSelected(""); setPanelError("");
    const sorted = [...assignment.items].sort((a, b) => a.order - b.order);
    const idx    = sorted.findIndex(i => i.id === item.id);
    setPanelRunScore(assignment.score);
    setSelectedPanel({ item, assignmentId: assignment.id, itemIndex: idx + 1, totalItems: sorted.length, maxScore: assignment.max_score });
  }

  function goToNextItem() {
    if (!selectedPanel) return;
    const assignment = assignments.find(a => a.id === selectedPanel.assignmentId);
    if (!assignment) return;
    const sorted = [...assignment.items].sort((a, b) => a.order - b.order);
    const idx    = sorted.findIndex(i => i.id === selectedPanel.item.id);
    const next   = sorted[idx + 1];
    if (next) {
      setPanelResult(null); setPanelSelected(""); setPanelError("");
      setSelectedPanel({ item: next, assignmentId: assignment.id, itemIndex: idx + 2, totalItems: sorted.length, maxScore: assignment.max_score });
    } else {
      setSelectedPanel(null);
    }
  }

  async function handlePanelSubmit() {
    if (!selectedPanel) return;
    const { item, assignmentId } = selectedPanel;
    setPanelSaving(true); setPanelError("");
    try {
      const body = item.item_type === "quiz" ? { selected_option: panelSelected } : {};
      const response = await clientApi.post(API.assessments.respond(assignmentId, item.id), body);
      const result = (response.data?.data ?? response.data) as RespondData;
      setPanelResult(result);
      setPanelRunScore(result.assignment_score);
      refetch();
    } catch {
      setPanelError("Could not save your response. Please try again.");
    } finally {
      setPanelSaving(false);
    }
  }

  async function handleRetake(assignmentId: string) {
    setRetaking(assignmentId);
    setRetakeError(prev => ({ ...prev, [assignmentId]: "" }));
    try {
      await clientApi.post(API.assessments.retake(assignmentId));
      setFinalResults(prev => { const n = { ...prev }; delete n[assignmentId]; return n; });
      setCompletionModal(null); setSelectedPanel(null); refetch();
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Could not start retake.";
      setRetakeError(prev => ({ ...prev, [assignmentId]: message }));
    } finally { setRetaking(null); }
  }

  async function handleComplete(assignmentId: string) {
    setCompleting(assignmentId);
    setCompleteError(prev => ({ ...prev, [assignmentId]: "" }));
    try {
      const response = await clientApi.post(API.assessments.complete(assignmentId));
      const result   = (response.data?.data ?? response.data) as CompleteData;
      setFinalResults(prev => ({ ...prev, [assignmentId]: result }));
      const assignment = assignments.find(a => a.id === assignmentId);
      // Other assessments still pending/in_progress besides this one? If so,
      // the dashboard must stay locked — only offer it once this was truly
      // the last one, otherwise the proxy will immediately bounce the
      // employee back here anyway (assessment_status is still "pending").
      const isLastPending = !assignments.some(a =>
        a.id !== assignmentId && (a.status === "pending" || a.status === "in_progress")
      );
      setCompletionModal({ result, title: assignment?.assessment_title ?? "Assessment", assignmentId, attemptNumber: (assignment?.attempt_number ?? 0) + 1, isLastPending });
      setSelectedPanel(null); refetch();
    } catch (err: unknown) {
      const message = (err as { response?: { data?: { message?: string } } })?.response?.data?.message ?? "Could not submit assessment.";
      setCompleteError(prev => ({ ...prev, [assignmentId]: message }));
    } finally { setCompleting(null); }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  const selectedAssignment = selectedPanel ? assignments.find(a => a.id === selectedPanel.assignmentId) : null;
  const selectedItemResponse = selectedAssignment?.responses.find(r => r.item_id === selectedPanel?.item.id);
  // The "Submit Assessment" action otherwise only ever appeared in the sidebar,
  // below the item list — after answering the LAST item, the main panel showed
  // just the result card with no button at all (Next Item hides itself once
  // there's nothing left), so finishing required noticing a button elsewhere
  // on the screen. Mirror that same completion check here so the main panel
  // can offer it directly.
  const selectedSortedItems = selectedAssignment ? [...selectedAssignment.items].sort((a, b) => a.order - b.order) : [];
  const selectedAllAnswered = selectedAssignment
    ? selectedSortedItems.filter(i => isItemDone(i, selectedAssignment.responses)).length === selectedSortedItems.length
      && selectedSortedItems.length > 0
    : false;
  const selectedIsDone = selectedAssignment
    ? selectedAssignment.status === "complete" || !!finalResults[selectedAssignment.id]
    : false;
  const isLastItemInPanel = !!selectedPanel && selectedPanel.itemIndex >= selectedPanel.totalItems;

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: "#f0f4f8" }}>

      {/* Top accent */}
      <div style={{ height: 3, background: "linear-gradient(90deg,#7c3aed,#3b82f6)", flexShrink: 0 }} />

      {/* Header */}
      <header style={{ background: "var(--surface)", borderBottom: "1px solid #e2e8f0", padding: "12px 24px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0, boxShadow: "0 1px 3px rgba(0,0,0,0.05)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: "#7c3aed", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <i className="ti ti-clipboard-check" style={{ color: "#fff", fontSize: 17 }} />
          </div>
          <div>
            <h1 style={{ fontSize: 15, fontWeight: 700, color: "#0f172a", margin: 0 }}>Assessment Portal</h1>
            <p style={{ fontSize: 11, color: "#64748b", margin: 0 }}>Aira HRMS — Pre-Onboarding</p>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {allComplete && (
            <button suppressHydrationWarning onClick={() => router.push("/dashboard")}
              style={{ padding: "8px 18px", borderRadius: 9, background: "#7c3aed", color: "#fff", fontWeight: 600, fontSize: 13, border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 7 }}>
              Go to Dashboard <i className="ti ti-arrow-right" />
            </button>
          )}
          <button suppressHydrationWarning onClick={handleLogout} disabled={loggingOut}
            style={{ padding: "8px 16px", borderRadius: 9, background: "transparent", color: "#64748b", fontWeight: 500, fontSize: 13, border: "1px solid #e2e8f0", cursor: loggingOut ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: 6, opacity: loggingOut ? 0.6 : 1 }}>
            {loggingOut ? <i className="ti ti-loader-2 spin" /> : <i className="ti ti-logout" />}
            {loggingOut ? "Logging out…" : "Logout"}
          </button>
        </div>
      </header>

      {/* Body: sidebar + main */}
      <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>

        {/* ── SIDEBAR ── */}
        <aside style={{ width: 280, background: "var(--surface)", borderRight: "1px solid #e2e8f0", display: "flex", flexDirection: "column", flexShrink: 0, overflowY: "auto" }}>

          {/* Sidebar header */}
          <div style={{ padding: "16px 18px 12px", borderBottom: "1px solid #f1f5f9", background: "#fafafa" }}>
            <p style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.08em", margin: "0 0 2px" }}>Assessments</p>
            <p style={{ fontSize: 13, fontWeight: 600, color: "#334155", margin: 0 }}>
              {loading ? "Loading…" : `${assignments.length} test${assignments.length !== 1 ? "s" : ""} assigned`}
            </p>
          </div>

          {/* Loading */}
          {loading && (
            <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 10 }}>
              {[1, 2, 3].map(n => <div key={n} style={{ height: 40, borderRadius: 8, background: "#f1f5f9", animation: "pulse 1.5s infinite" }} />)}
            </div>
          )}

          {/* Error / empty */}
          {!loading && error && (
            <div style={{ padding: 16, fontSize: 12, color: "#dc2626" }}><i className="ti ti-alert-circle mr-1" />Failed to load.</div>
          )}
          {!loading && !error && assignments.length === 0 && (
            <div style={{ padding: 24, textAlign: "center" }}>
              <i className="ti ti-clipboard" style={{ fontSize: 28, color: "#cbd5e1", display: "block", marginBottom: 8 }} />
              <p style={{ fontSize: 12, color: "#94a3b8", margin: 0 }}>No assessments assigned yet.</p>
            </div>
          )}

          {/* Assignment sections */}
          {assignments.map((assignment, aIdx) => {
            const finalResult  = finalResults[assignment.id];
            const isDone       = assignment.status === "complete" || !!finalResult;
            const isPassed     = finalResult != null ? finalResult.passed : (assignment.passed ?? null);
            const sortedItems  = [...assignment.items].sort((a, b) => a.order - b.order);
            const doneCount    = sortedItems.filter(i => isItemDone(i, assignment.responses)).length;
            const allAnswered  = doneCount === sortedItems.length && sortedItems.length > 0;
            const currentScore = finalResult?.score ?? assignment.score;

            return (
              <div key={assignment.id} style={{ borderBottom: aIdx < assignments.length - 1 ? "1px solid #f1f5f9" : "none" }}>
                {/* Assessment section header — clicking opens the first available item */}
                <div
                  onClick={() => {
                    const target = sortedItems.find((item, idx) => {
                      const done     = isItemDone(item, assignment.responses);
                      const prevDone = idx === 0 || isItemDone(sortedItems[idx - 1], assignment.responses);
                      return !done && (idx === 0 || prevDone);
                    }) ?? sortedItems[0];
                    if (target) openItem(target, assignment);
                  }}
                  style={{ padding: "12px 18px 8px", cursor: sortedItems.length > 0 ? "pointer" : "default" }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: 13, fontWeight: 700, color: "#0f172a", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>{assignment.assessment_title}</span>
                    {isDone && (
                      <span style={{ fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 20, background: isPassed === false ? "#fee2e2" : "#dcfce7", color: isPassed === false ? "#dc2626" : "#16a34a", flexShrink: 0 }}>
                        {isPassed === false ? "Failed" : "Done"}
                      </span>
                    )}
                  </div>
                  {/* Attempts remaining + countdown */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4, fontSize: 11, color: "#64748b" }}>
                    {assignment.effective_max_attempts > 0 && (
                      <span>
                        <i className="ti ti-refresh" style={{ fontSize: 9, marginRight: 3 }} />
                        {assignment.attempts_remaining != null
                          ? `${assignment.attempts_remaining} attempt${assignment.attempts_remaining !== 1 ? "s" : ""} left`
                          : `${assignment.effective_max_attempts} max`}
                      </span>
                    )}
                    {timers[assignment.id] != null && !isDone && (
                      <span style={{ fontWeight: 700, color: timers[assignment.id] < 60 ? "#dc2626" : "#d97706", marginLeft: "auto" }}>
                        <i className="ti ti-clock" style={{ fontSize: 9, marginRight: 3 }} />
                        {fmtTimer(timers[assignment.id])}
                      </span>
                    )}
                  </div>
                  {/* Mini progress bar */}
                  <div style={{ height: 3, background: "#f1f5f9", borderRadius: 99, overflow: "hidden", marginBottom: 4 }}>
                    <div style={{ height: "100%", width: `${sortedItems.length > 0 ? (doneCount / sortedItems.length) * 100 : 0}%`, background: isDone && isPassed === false ? "#ef4444" : "#7c3aed", borderRadius: 99, transition: "width 0.4s" }} />
                  </div>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>{doneCount}/{sortedItems.length} items</span>
                    {assignment.max_score > 0 && <span style={{ fontSize: 11, fontWeight: 600, color: "#7c3aed" }}>{currentScore}/{assignment.max_score} pts</span>}
                  </div>
                </div>

                {/* Item list — grouped by section */}
                {(() => {
                  // Build ordered section groups from items
                  const sectionOrder: string[] = [];
                  const sectionMap = new Map<string, { title: string | null; items: AssignmentItem[] }>();
                  for (const item of sortedItems) {
                    const key = item.section_id ?? "__none__";
                    if (!sectionMap.has(key)) {
                      sectionOrder.push(key);
                      sectionMap.set(key, { title: item.section_title ?? null, items: [] });
                    }
                    sectionMap.get(key)!.items.push(item);
                  }
                  const hasAnySections = sectionOrder.some(k => k !== "__none__");

                  return sectionOrder.map(sectionKey => {
                    const group = sectionMap.get(sectionKey)!;
                    const collapseKey = `${assignment.id}|${sectionKey}`;
                    const isOpen = !openSections.has(collapseKey);
                    const sectionDone = group.items.every(i => isItemDone(i, assignment.responses));

                    return (
                      <div key={sectionKey}>
                        {/* Section header — only shown when there are named sections */}
                        {hasAnySections && sectionKey !== "__none__" && (
                          <div
                            onClick={() => toggleSection(collapseKey)}
                            style={{
                              display: "flex", alignItems: "center", gap: 8,
                              padding: "7px 18px 7px 14px", cursor: "pointer",
                              background: "#f8fafc",
                              borderTop: "1px solid #f1f5f9",
                              borderLeft: `3px solid ${sectionDone ? "#86efac" : "#bfdbfe"}`,
                              userSelect: "none",
                            }}>
                            <i
                              className={`ti ${isOpen ? "ti-chevron-down" : "ti-chevron-right"}`}
                              style={{ fontSize: 12, color: "#94a3b8", flexShrink: 0, transition: "transform 0.15s" }}
                            />
                            <span style={{ flex: 1, fontSize: 11, fontWeight: 700, color: "#334155", textTransform: "uppercase", letterSpacing: "0.05em", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {group.title ?? "Section"}
                            </span>
                            <span style={{ fontSize: 10, color: "#94a3b8", flexShrink: 0 }}>
                              {group.items.filter(i => isItemDone(i, assignment.responses)).length}/{group.items.length}
                            </span>
                          </div>
                        )}

                        {/* Items — hidden when section collapsed */}
                        {isOpen && group.items.map((item) => {
                          const globalIdx = sortedItems.findIndex(i => i.id === item.id);
                          const done     = isItemDone(item, assignment.responses);
                          const prevDone = globalIdx === 0 || isItemDone(sortedItems[globalIdx - 1], assignment.responses);
                          const locked   = !prevDone && !done;
                          const isActive = selectedPanel?.item.id === item.id;
                          const isVideo  = item.item_type === "video";
                          const itemResp = assignment.responses.find(r => r.item_id === item.id);
                          const indent   = hasAnySections && sectionKey !== "__none__" ? 28 : 18;

                          return (
                            <div key={item.id}
                              onClick={() => !locked && openItem(item, assignment)}
                              style={{
                                display: "flex", alignItems: "center", gap: 10,
                                padding: `8px 18px 8px ${indent}px`,
                                cursor: locked ? "not-allowed" : "pointer",
                                opacity: locked ? 0.45 : 1,
                                background: isActive ? "rgba(124,58,237,0.07)" : "transparent",
                                borderLeft: `3px solid ${isActive ? "#7c3aed" : "transparent"}`,
                                transition: "all 0.15s",
                              }}>
                              <div style={{ width: 24, height: 24, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, background: done ? "#dcfce7" : locked ? "#f1f5f9" : isActive ? "#7c3aed" : "#eff6ff", color: done ? "#16a34a" : locked ? "#94a3b8" : isActive ? "#fff" : "#7c3aed", border: `1.5px solid ${done ? "#86efac" : locked ? "#e2e8f0" : isActive ? "#7c3aed" : "#bfdbfe"}` }}>
                                {done ? <i className="ti ti-check" style={{ fontSize: 11 }} /> : locked ? <i className="ti ti-lock" style={{ fontSize: 9 }} /> : (globalIdx + 1)}
                              </div>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <p style={{ fontSize: 12, fontWeight: isActive ? 600 : 500, color: locked ? "#94a3b8" : isActive ? "#7c3aed" : "#334155", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.title}</p>
                                <p style={{ fontSize: 10, color: "#94a3b8", margin: 0, display: "flex", alignItems: "center", gap: 3 }}>
                                  <i className={`ti ${isVideo ? "ti-player-play" : "ti-help-circle"}`} style={{ fontSize: 9 }} />
                                  {isVideo ? "Video" : "Quiz"}
                                  {done && itemResp && !isVideo && itemResp.is_correct != null && (
                                    <span style={{ color: itemResp.is_correct ? "#16a34a" : "#dc2626", fontWeight: 600 }}>
                                      {" "}· {itemResp.is_correct ? `+${itemResp.score_awarded}pts` : "✗"}
                                    </span>
                                  )}
                                </p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    );
                  });
                })()}

                {/* Submit / retake actions inside sidebar */}
                {(allAnswered && !isDone) || isDone ? (
                  <div style={{ padding: "8px 18px 14px" }}>
                    {allAnswered && !isDone && (
                      <>
                        {completeError[assignment.id] && (
                          <p style={{ fontSize: 11, color: "#dc2626", margin: "0 0 6px" }}>{completeError[assignment.id]}</p>
                        )}
                        <button suppressHydrationWarning onClick={() => handleComplete(assignment.id)} disabled={completing === assignment.id}
                          style={{ width: "100%", padding: "9px 0", borderRadius: 9, background: completing === assignment.id ? "#94a3b8" : "#7c3aed", color: "#fff", fontWeight: 600, fontSize: 12, border: "none", cursor: completing === assignment.id ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 7 }}>
                          {completing === assignment.id ? <><i className="ti ti-loader-2 spin" />Submitting…</> : <><i className="ti ti-send" />Submit Assessment</>}
                        </button>
                      </>
                    )}
                    {isDone && isPassed === false && (
                      <>
                        {retakeError[assignment.id] && (
                          <p style={{ fontSize: 11, color: "#dc2626", margin: "0 0 6px" }}>{retakeError[assignment.id]}</p>
                        )}
                        <button suppressHydrationWarning onClick={() => handleRetake(assignment.id)} disabled={retaking === assignment.id}
                          style={{ width: "100%", padding: "9px 0", borderRadius: 9, background: "transparent", color: "#dc2626", fontWeight: 600, fontSize: 12, border: "1.5px solid #fca5a5", cursor: retaking === assignment.id ? "not-allowed" : "pointer", display: "flex", alignItems: "center", justifyContent: "center", gap: 7, opacity: retaking === assignment.id ? 0.6 : 1 }}>
                          {retaking === assignment.id ? <><i className="ti ti-loader-2 spin" />Starting…</> : <><i className="ti ti-refresh" />Retake Assessment</>}
                        </button>
                      </>
                    )}

                    {/* Attempt history mini */}
                    {assignment.attempts && assignment.attempts.length > 0 && (
                      <div style={{ marginTop: 10 }}>
                        <p style={{ fontSize: 10, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 6px" }}>History</p>
                        {[...assignment.attempts].sort((a, b) => a.attempt_number - b.attempt_number).map(attempt => (
                          <div key={attempt.attempt_number} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "4px 0", fontSize: 11, borderBottom: "1px solid #f1f5f9" }}>
                            <span style={{ color: "#64748b" }}>#{attempt.attempt_number}</span>
                            <span style={{ fontWeight: 700, color: attempt.passed ? "#16a34a" : "#dc2626" }}>{attempt.score}/{attempt.max_score}</span>
                            <span style={{ color: "#94a3b8" }}>{new Date(attempt.completed_at).toLocaleDateString("en-IN", { day: "2-digit", month: "short" })}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ) : null}
              </div>
            );
          })}
        </aside>

        {/* ── MAIN CONTENT AREA ── */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

          {/* Top bar with context */}
          {selectedPanel && selectedAssignment && (
            <div style={{ background: "var(--surface)", borderBottom: "1px solid #e2e8f0", padding: "10px 28px", display: "flex", alignItems: "center", gap: 14, flexShrink: 0 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 11, color: "#94a3b8", margin: 0, fontWeight: 500 }}>{selectedAssignment.assessment_title}</p>
                <p style={{ fontSize: 14, fontWeight: 700, color: "#0f172a", margin: 0, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {selectedPanel.item.item_type === "video" ? <><i className="ti ti-player-play" style={{ color: "#1d4ed8", marginRight: 6 }} /></> : <><i className="ti ti-help-circle" style={{ color: "#7c3aed", marginRight: 6 }} /></>}
                  {selectedPanel.item.title}
                </p>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 16, flexShrink: 0 }}>
                <span style={{ fontSize: 12, color: "#64748b" }}>Item {selectedPanel.itemIndex} of {selectedPanel.totalItems}</span>
                {selectedPanel.maxScore > 0 && (
                  <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8, padding: "3px 12px", textAlign: "center" }}>
                    <span style={{ fontSize: 11, fontWeight: 600, color: "#1d4ed8" }}>Score: </span>
                    <span style={{ fontSize: 14, fontWeight: 800, color: "#7c3aed" }}>{panelRunScore}</span>
                    <span style={{ fontSize: 11, color: "#64748b" }}>/{selectedPanel.maxScore}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Content */}
          <div style={{ flex: 1, overflowY: "auto", padding: "24px 28px" }}>

            {/* Loading */}
            {loading && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
                <div style={{ textAlign: "center" }}>
                  <i className="ti ti-loader-2 spin" style={{ fontSize: 36, color: "#94a3b8", display: "block", marginBottom: 12 }} />
                  <p style={{ fontSize: 14, color: "#94a3b8" }}>Loading assessments…</p>
                </div>
              </div>
            )}

            {/* Error */}
            {!loading && error && (
              <div style={{ background: "#fff1f2", border: "1px solid #fecdd3", borderRadius: 12, padding: "16px 20px", color: "#dc2626", fontSize: 14 }}>
                <i className="ti ti-alert-circle mr-2" />Could not load assessments. Please refresh.
              </div>
            )}

            {/* Landing — nothing selected */}
            {!loading && !error && !selectedPanel && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
                <div style={{ textAlign: "center", maxWidth: 360 }}>
                  <div style={{ width: 72, height: 72, borderRadius: 20, background: "#eff6ff", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 20px" }}>
                    <i className="ti ti-arrow-left" style={{ fontSize: 32, color: "#7c3aed" }} />
                  </div>
                  <h2 style={{ fontSize: 20, fontWeight: 700, color: "#0f172a", margin: "0 0 8px" }}>
                    {assignments.length === 0 ? "No Assessments Yet" : "Select an Item to Begin"}
                  </h2>
                  <p style={{ fontSize: 14, color: "#64748b", margin: 0, lineHeight: 1.6 }}>
                    {assignments.length === 0
                      ? "Your HR team will assign assessments before you can proceed to the dashboard."
                      : "Click on any question or video in the sidebar on the left to start your assessment."}
                  </p>
                  {allComplete && (
                    <button suppressHydrationWarning onClick={() => router.push("/dashboard")}
                      style={{ marginTop: 24, padding: "11px 28px", borderRadius: 10, background: "#16a34a", color: "#fff", fontWeight: 700, fontSize: 14, border: "none", cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 8 }}>
                      All Done — Go to Dashboard <i className="ti ti-arrow-right" />
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* ── Active item content ── */}
            {!loading && selectedPanel && selectedAssignment && (() => {
              const item = selectedPanel.item;
              const isVideo = item.item_type === "video";
              const alreadyDone = isItemDone(item, selectedAssignment.responses);

              return (
                <div style={{ maxWidth: isVideo ? "100%" : 720, margin: "0 auto" }}>

                  {/* ── VIDEO ── */}
                  {isVideo && (
                    <div>
                      {/* Player — fills the available content area, min-height so it's never tiny on small screens */}
                      <div style={{ background: "#000", borderRadius: 14, overflow: "hidden", marginBottom: 16, width: "100%", aspectRatio: "16/9", minHeight: 220 }}>
                        {(() => {
                          const embedUrl = toEmbedUrl(item.video_url);
                          if (embedUrl) {
                            return <iframe src={embedUrl ?? undefined} allow="autoplay; fullscreen" allowFullScreen style={{ width: "100%", height: "100%", border: "none", display: "block" }} />;
                          }
                          // Direct video file (mp4, webm, etc.)
                          if (/\.(mp4|webm|ogg|mov)(\?|$)/i.test(item.video_url)) {
                            return <video src={item.video_url} controls style={{ width: "100%", height: "100%", display: "block" }} />;
                          }
                          // Unrecognised URL — show a fallback link
                          return (
                            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "100%", gap: 12, padding: 24 }}>
                              <i className="ti ti-video-off" style={{ fontSize: 40, color: "#64748b" }} />
                              <p style={{ color: "#94a3b8", fontSize: 13, margin: 0 }}>Preview not available</p>
                              <a href={item.video_url} target="_blank" rel="noopener noreferrer" style={{ display: "inline-flex", alignItems: "center", gap: 6, background: "#1e293b", color: "#e2e8f0", borderRadius: 8, padding: "8px 16px", fontSize: 13, textDecoration: "none" }}>
                                <i className="ti ti-external-link" /> Open video
                              </a>
                            </div>
                          );
                        })()}
                      </div>

                      {item.duration_secs && (
                        <p style={{ fontSize: 12, color: "#64748b", display: "flex", alignItems: "center", gap: 5, marginBottom: 20 }}>
                          <i className="ti ti-clock" /> Duration: {Math.ceil(item.duration_secs / 60)} min
                        </p>
                      )}

                      {/* Watched result */}
                      {panelResult && (
                        <div style={{ background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 14, padding: "20px 24px", display: "flex", alignItems: "center", gap: 16, marginBottom: 20 }}>
                          <div style={{ width: 44, height: 44, borderRadius: "50%", background: "#dcfce7", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                            <i className="ti ti-check" style={{ fontSize: 22, color: "#16a34a" }} />
                          </div>
                          <div>
                            <p style={{ fontWeight: 700, color: "#15803d", margin: "0 0 2px" }}>Video marked as watched!</p>
                            <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>Your progress has been saved.</p>
                          </div>
                        </div>
                      )}

                      {alreadyDone && !panelResult && (
                        <div style={{ background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 14, padding: "14px 20px", display: "flex", alignItems: "center", gap: 10, marginBottom: 20, fontSize: 13, color: "#15803d", fontWeight: 600 }}>
                          <i className="ti ti-circle-check" style={{ fontSize: 18 }} /> You have already watched this video.
                        </div>
                      )}

                      {/* Action buttons */}
                      <div style={{ display: "flex", gap: 12 }}>
                        {!alreadyDone && !panelResult && (
                          <button suppressHydrationWarning onClick={handlePanelSubmit} disabled={panelSaving}
                            style={{ padding: "12px 28px", borderRadius: 10, background: panelSaving ? "#94a3b8" : "#7c3aed", color: "#fff", fontWeight: 700, fontSize: 14, border: "none", cursor: panelSaving ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: 8, boxShadow: "0 2px 8px rgba(124,58,237,0.3)" }}>
                            {panelSaving ? <><i className="ti ti-loader-2 spin" />Saving…</> : <><i className="ti ti-circle-check" />Mark as Watched</>}
                          </button>
                        )}
                        {(panelResult || alreadyDone) && selectedPanel.itemIndex < selectedPanel.totalItems && (
                          <button suppressHydrationWarning onClick={goToNextItem}
                            style={{ padding: "12px 28px", borderRadius: 10, background: "#7c3aed", color: "#fff", fontWeight: 700, fontSize: 14, border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}>
                            Next Item <i className="ti ti-arrow-right" />
                          </button>
                        )}
                        {(panelResult || alreadyDone) && isLastItemInPanel && selectedAllAnswered && !selectedIsDone && (
                          <button suppressHydrationWarning onClick={() => handleComplete(selectedPanel.assignmentId)} disabled={completing === selectedPanel.assignmentId}
                            style={{ padding: "12px 28px", borderRadius: 10, background: completing === selectedPanel.assignmentId ? "#94a3b8" : "#16a34a", color: "#fff", fontWeight: 700, fontSize: 14, border: "none", cursor: completing === selectedPanel.assignmentId ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: 8, boxShadow: "0 2px 8px rgba(22,163,74,0.3)" }}>
                            {completing === selectedPanel.assignmentId ? <><i className="ti ti-loader-2 spin" />Submitting…</> : <><i className="ti ti-send" />Submit Assessment</>}
                          </button>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ── QUIZ ── */}
                  {!isVideo && (
                    <div>
                      {/* Question card */}
                      <div style={{ background: "var(--surface)", border: "1px solid #e2e8f0", borderRadius: 14, padding: "24px 28px", marginBottom: 20, boxShadow: "0 1px 4px rgba(0,0,0,0.05)" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
                          <span style={{ fontSize: 10, fontWeight: 700, color: "#7c3aed", textTransform: "uppercase", letterSpacing: "0.08em", background: "#f5f3ff", padding: "3px 10px", borderRadius: 20 }}>Question</span>
                          {item.pass_score > 0 && <span style={{ fontSize: 11, color: "#64748b" }}><i className="ti ti-target mr-1" />{item.pass_score} point{item.pass_score !== 1 ? "s" : ""}</span>}
                        </div>
                        <p style={{ fontSize: 17, fontWeight: 600, color: "#0f172a", margin: 0, lineHeight: 1.65 }}>{item.question}</p>
                      </div>

                      {/* Options — before answering */}
                      {!panelResult && !alreadyDone && (
                        <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 24 }}>
                          {OPTIONS.filter(o => item[o.field]).map(o => (
                            <div key={o.key} onClick={() => setPanelSelected(o.key)}
                              style={{ display: "flex", alignItems: "center", gap: 16, padding: "16px 20px", borderRadius: 12, border: `2px solid ${panelSelected === o.key ? "#7c3aed" : "#e2e8f0"}`, background: panelSelected === o.key ? "rgba(124,58,237,0.04)" : "#fff", cursor: "pointer", transition: "all 0.15s", boxShadow: panelSelected === o.key ? "0 0 0 3px rgba(124,58,237,0.12)" : "none" }}>
                              <div style={{ width: 38, height: 38, borderRadius: "50%", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 800, fontSize: 14, background: panelSelected === o.key ? "#7c3aed" : "#f1f5f9", color: panelSelected === o.key ? "#fff" : "#64748b", transition: "all 0.15s" }}>
                                {o.key.toUpperCase()}
                              </div>
                              <span style={{ fontSize: 15, color: "#1e293b", lineHeight: 1.5 }}>{item[o.field] as string}</span>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Already done state */}
                      {alreadyDone && !panelResult && (() => {
                        const resp = selectedItemResponse;
                        return (
                          <div style={{ background: resp?.is_correct ? "#f0fdf4" : "#fff1f2", border: `1px solid ${resp?.is_correct ? "#86efac" : "#fca5a5"}`, borderRadius: 14, padding: "20px 24px", marginBottom: 20 }}>
                            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                              <div style={{ width: 44, height: 44, borderRadius: "50%", background: resp?.is_correct ? "#dcfce7" : "#fee2e2", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                                <i className={`ti ${resp?.is_correct ? "ti-check" : "ti-x"}`} style={{ fontSize: 22, color: resp?.is_correct ? "#16a34a" : "#dc2626" }} />
                              </div>
                              <div>
                                <p style={{ fontWeight: 700, color: resp?.is_correct ? "#15803d" : "#dc2626", margin: "0 0 2px", fontSize: 15 }}>{resp?.is_correct ? "Correct Answer" : "Incorrect"}</p>
                                <p style={{ fontSize: 13, color: "#64748b", margin: 0 }}>You answered: Option {resp?.selected_option?.toUpperCase() ?? "—"}{resp?.score_awarded ? ` · +${resp.score_awarded} pts` : ""}</p>
                              </div>
                            </div>
                          </div>
                        );
                      })()}

                      {/* Result after submitting */}
                      {panelResult && (
                        <div style={{ background: panelResult.is_correct ? "#f0fdf4" : "#fff1f2", border: `1px solid ${panelResult.is_correct ? "#86efac" : "#fca5a5"}`, borderRadius: 14, padding: "24px 28px", marginBottom: 20, textAlign: "center" }}>
                          <div style={{ width: 56, height: 56, borderRadius: "50%", background: panelResult.is_correct ? "#dcfce7" : "#fee2e2", display: "flex", alignItems: "center", justifyContent: "center", margin: "0 auto 14px" }}>
                            <i className={`ti ${panelResult.is_correct ? "ti-check" : "ti-x"}`} style={{ fontSize: 26, color: panelResult.is_correct ? "#16a34a" : "#dc2626" }} />
                          </div>
                          <p style={{ fontSize: 20, fontWeight: 800, color: "#0f172a", margin: "0 0 4px" }}>{panelResult.is_correct ? "Correct!" : "Incorrect"}</p>
                          {panelResult.score_awarded > 0 && <p style={{ fontSize: 14, color: "#16a34a", fontWeight: 600, margin: "0 0 12px" }}>+{panelResult.score_awarded} point{panelResult.score_awarded !== 1 ? "s" : ""} awarded</p>}
                          {selectedPanel.maxScore > 0 && (
                            <div style={{ display: "inline-flex", alignItems: "center", gap: 8, background: "var(--surface)", border: "1px solid #e2e8f0", borderRadius: 10, padding: "8px 18px", fontSize: 13 }}>
                              <i className="ti ti-chart-bar" style={{ color: "#7c3aed" }} />
                              Running total: <strong style={{ color: "#7c3aed" }}>{panelResult.assignment_score} / {selectedPanel.maxScore}</strong>
                            </div>
                          )}
                        </div>
                      )}

                      {panelError && (
                        <div style={{ background: "#fff1f2", border: "1px solid #fecdd3", borderRadius: 10, padding: "10px 14px", marginBottom: 16, fontSize: 13, color: "#dc2626" }}>
                          <i className="ti ti-alert-circle mr-1" />{panelError}
                        </div>
                      )}

                      {/* Action buttons */}
                      <div style={{ display: "flex", gap: 12 }}>
                        {!alreadyDone && !panelResult && (
                          <button suppressHydrationWarning onClick={handlePanelSubmit} disabled={panelSaving || !panelSelected}
                            style={{ padding: "12px 28px", borderRadius: 10, background: panelSaving || !panelSelected ? "#94a3b8" : "#7c3aed", color: "#fff", fontWeight: 700, fontSize: 14, border: "none", cursor: panelSaving || !panelSelected ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: 8, boxShadow: panelSelected ? "0 2px 8px rgba(124,58,237,0.3)" : "none" }}>
                            {panelSaving ? <><i className="ti ti-loader-2 spin" />Saving…</> : <><i className="ti ti-send" />Submit Answer</>}
                          </button>
                        )}
                        {(panelResult || alreadyDone) && selectedPanel.itemIndex < selectedPanel.totalItems && (
                          <button suppressHydrationWarning onClick={goToNextItem}
                            style={{ padding: "12px 28px", borderRadius: 10, background: "#7c3aed", color: "#fff", fontWeight: 700, fontSize: 14, border: "none", cursor: "pointer", display: "flex", alignItems: "center", gap: 8 }}>
                            Next Item <i className="ti ti-arrow-right" />
                          </button>
                        )}
                        {(panelResult || alreadyDone) && isLastItemInPanel && selectedAllAnswered && !selectedIsDone && (
                          <button suppressHydrationWarning onClick={() => handleComplete(selectedPanel.assignmentId)} disabled={completing === selectedPanel.assignmentId}
                            style={{ padding: "12px 28px", borderRadius: 10, background: completing === selectedPanel.assignmentId ? "#94a3b8" : "#16a34a", color: "#fff", fontWeight: 700, fontSize: 14, border: "none", cursor: completing === selectedPanel.assignmentId ? "not-allowed" : "pointer", display: "flex", alignItems: "center", gap: 8, boxShadow: "0 2px 8px rgba(22,163,74,0.3)" }}>
                            {completing === selectedPanel.assignmentId ? <><i className="ti ti-loader-2 spin" />Submitting…</> : <><i className="ti ti-send" />Submit Assessment</>}
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        </div>
      </div>

      {completionModal && (
        <CompletionModal
          result={completionModal.result}
          title={completionModal.title}
          attemptNumber={completionModal.attemptNumber}
          isLastPending={completionModal.isLastPending}
          retaking={retaking === completionModal.assignmentId}
          onRetake={() => handleRetake(completionModal.assignmentId)}
          onContinue={() => setCompletionModal(null)}
          onDashboard={() => {
            // Set explicitly rather than waiting on the allComplete effect —
            // that depends on the refetch() from handleComplete resolving
            // first, which can lose the race against this click. The proxy
            // gate reads assessment_status straight from this cookie, so an
            // immediate navigation right after refetch fires needs it to
            // already be correct, not eventually-correct.
            setAssessmentStatus("complete");
            setCompletionModal(null);
            router.push("/dashboard");
          }}
        />
      )}
    </div>
  );
}

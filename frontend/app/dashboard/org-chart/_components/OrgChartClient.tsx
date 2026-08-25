"use client";

import { useLayoutEffect, useRef, useState } from "react";
import Link from "next/link";
import { useFetch } from "@/hooks/useFetch";
import { useOrgChart } from "@/hooks/useOrgChart";
import { API } from "@/lib/api/endpoints";
import type { OrgChartDepartment, OrgChartGroup, OrgChartPerson } from "@/types/orgChart";

interface BranchOption { branch_name: string }

const LINE = "var(--outline-v)";
const DEPT_COLOR = "var(--secondary)";

// Employee Profile is keyed by employee_id (e.g. "RSS000183"), not the
// internal UUID — a person with no employee_id (data gap) renders as plain
// text rather than a link to a page that would 404.
function PersonName({ person, style }: { person: OrgChartPerson; style: React.CSSProperties }) {
  if (!person.employee_id) return <span style={style}>{person.name}</span>;
  return (
    <Link href={`/dashboard/employees/${person.employee_id}`} style={{ ...style, textDecoration: "none" }}
      className="org-chart-person-link">
      {person.name}
    </Link>
  );
}

interface DeptColProps {
  dept:    OrgChartDepartment;
  isFirst: boolean;
  isLast:  boolean;
}

function DeptCol({ dept, isFirst, isLast }: DeptColProps) {
  return (
    <div style={{
      flex: "1 0 160px",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      paddingTop: 28,
      paddingLeft: 10,
      paddingRight: 10,
      position: "relative",
    }}>
      {/* Horizontal bar segment connecting siblings */}
      <div style={{
        position: "absolute",
        top: 0,
        left:  isFirst ? "50%" : 0,
        right: isLast  ? "50%" : 0,
        height: 1,
        background: LINE,
      }} />

      {/* Vertical drop from bar to dept card */}
      <div style={{ width: 1, height: 28, background: LINE, flexShrink: 0 }} />

      {/* Dept head card */}
      <div style={{
        background: "var(--surface)",
        border: "1px solid var(--outline-v)",
        borderRadius: "var(--radius-lg)",
        padding: "16px 18px",
        textAlign: "center",
        width: "100%",
        boxShadow: "var(--shadow)",
      }}>
        <div style={{
          fontSize: 10,
          fontWeight: 700,
          letterSpacing: "0.08em",
          color: DEPT_COLOR,
          textTransform: "uppercase",
          marginBottom: 8,
        }}>
          {dept.label}
        </div>
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--on-bg)", marginBottom: 3 }}>
          {dept.head ? <PersonName person={dept.head} style={{ fontWeight: 700 }} /> : "Not assigned"}
        </div>
        <div style={{ fontSize: 12, color: "var(--on-variant)" }}>
          {dept.head?.designation || " "}
        </div>
      </div>

      {/* Vertical drop to team card */}
      <div style={{ width: 1, height: 18, background: LINE, flexShrink: 0 }} />

      {/* Team members card — full vertical list so every name fits */}
      <div style={{
        background: "var(--bg-low)",
        border: "1px solid var(--outline-v)",
        borderRadius: "var(--radius-lg)",
        padding: "12px 16px",
        width: "100%",
      }}>
        <div style={{ fontSize: 11, color: "var(--on-variant)", marginBottom: 6, textAlign: "center" }}>
          Team members
        </div>
        {dept.members.length === 0 ? (
          <div style={{ fontSize: 13, color: "var(--on-bg)", textAlign: "center" }}>–</div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {dept.members.map(m => (
              <PersonName key={m.id} person={m} style={{ fontSize: 13, fontWeight: 500, color: "var(--on-bg)", display: "block" }} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// A single branch's own root + department columns — no outer card, no
// connector to siblings. Used both standalone (one branch selected, or a
// branch-scoped viewer with only one branch to show) and nested inside
// BranchNode below (part of the "All Branches" tree).
function BranchBody({ group }: { group: OrgChartGroup }) {
  if (group.departments.length === 0) {
    return (
      <div style={{ color: "var(--on-variant)", fontSize: 13, textAlign: "center" }}>
        No departments with employees found yet.
      </div>
    );
  }
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      {/* Root node */}
      <div style={{
        background: "var(--surface)",
        border: "1.5px solid var(--outline-v)",
        borderRadius: "var(--radius-lg)",
        padding: "16px 40px",
        textAlign: "center",
        boxShadow: "var(--shadow)",
      }}>
        <div style={{ fontSize: 12, color: "var(--on-variant)", marginBottom: 6 }}>
          {group.root?.designation || "Top of chart"}
        </div>
        <div style={{ fontSize: 18, fontWeight: 700, color: "var(--on-bg)" }}>
          {group.root ? <PersonName person={group.root} style={{ fontWeight: 700 }} /> : "Not set"}
        </div>
      </div>

      {/* Vertical line from root to children row */}
      <div style={{ width: 1, height: 28, background: LINE }} />

      {/* Department columns row */}
      <div style={{ display: "flex", alignItems: "flex-start" }}>
        {group.departments.map((dept, i) => (
          <DeptCol
            key={dept.id}
            dept={dept}
            isFirst={i === 0}
            isLast={i === group.departments.length - 1}
          />
        ))}
      </div>
    </div>
  );
}

// One branch as a sibling under the shared company node — the horizontal
// bar + vertical drop is the exact same connector DeptCol uses to link
// sibling departments, reused here one level up so every branch visibly
// hangs off the one company box instead of floating as an unrelated card.
function BranchNode({ group, isFirst, isLast }: { group: OrgChartGroup; isFirst: boolean; isLast: boolean }) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      position: "relative",
      paddingTop: 28,
      paddingLeft: 16,
      paddingRight: 16,
      width: 700,
      flexShrink: 0,
    }}>
      <div style={{
        position: "absolute", top: 0,
        left:  isFirst ? "50%" : 0,
        right: isLast  ? "50%" : 0,
        height: 1, background: LINE,
      }} />
      <div style={{ width: 1, height: 28, background: LINE, flexShrink: 0 }} />
      <div style={{ fontSize: 13, fontWeight: 700, color: "var(--on-bg)", marginBottom: 16 }}>
        {group.branch}
      </div>
      <BranchBody group={group} />
    </div>
  );
}

const ZOOM_MIN  = 50;
const ZOOM_MAX  = 150;
const ZOOM_STEP = 10;

// Scales chart content with the outer scrollable box resized to match —
// a plain CSS transform:scale leaves the box's own layout size unchanged,
// which at low zoom would leave a large dead scroll area around the
// visually-shrunk content. Measuring the natural (unscaled) size and
// setting the scroll box to natural * zoom keeps the scrollbars matching
// what's actually visible, so zooming out to see a big chart's overall
// shape also shrinks how much you need to scroll to see all of it.
function ZoomableChart({ zoom, children }: { zoom: number; children: React.ReactNode }) {
  const contentRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);

  useLayoutEffect(() => {
    const el = contentRef.current;
    if (!el) return;
    // transform: scale doesn't change scrollWidth/scrollHeight — they
    // always reflect the untransformed, natural layout size.
    setSize({ w: el.scrollWidth, h: el.scrollHeight });
  }, [children]);

  const scale = zoom / 100;
  return (
    <div style={{ overflow: "auto", WebkitOverflowScrolling: "touch" }}>
      <div style={size ? { width: size.w * scale, height: size.h * scale } : undefined}>
        <div ref={contentRef} style={{ transform: `scale(${scale})`, transformOrigin: "top left" }}>
          {children}
        </div>
      </div>
    </div>
  );
}

export default function OrgChartClient() {
  const [selectedBranch, setSelectedBranch] = useState("");
  const [zoom, setZoom] = useState(100);
  const { orgChart, loading, error, refetch } = useOrgChart(selectedBranch || undefined);
  const groups = orgChart?.groups ?? [];
  const canPickBranch = orgChart?.scope === "company";

  // Branch options for the dropdown come from the existing branches list
  // endpoint — the one place in the app that already answers "what branches
  // exist" — rather than the org-chart endpoint duplicating that list.
  // Only fetched once we know the viewer is unrestricted (canPickBranch);
  // a branch-scoped viewer never sees the dropdown, so never needs it.
  const { data: branchData } = useFetch<{ results: BranchOption[] }>(
    canPickBranch ? `${API.branches.list}?page_size=100` : null,
  );
  const branchOptions = branchData?.results?.map(b => b.branch_name) ?? [];

  return (
    <>
      <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", flexWrap: "wrap", gap: 12 }}>
        <div>
          <div className="page-title">Organisation Chart</div>
          <div className="page-sub">Company structure by branch</div>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
          <div style={{
            display: "flex", alignItems: "center", gap: 2,
            border: "1px solid var(--outline-v)", borderRadius: "var(--radius-lg)",
            background: "var(--surface)", padding: 2,
          }}>
            <button
              type="button"
              onClick={() => setZoom(z => Math.max(ZOOM_MIN, z - ZOOM_STEP))}
              disabled={zoom <= ZOOM_MIN}
              title="Zoom out"
              suppressHydrationWarning
              style={{
                width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center",
                borderRadius: "var(--radius-lg)", border: "none", background: "transparent",
                color: "var(--on-bg)", fontSize: 16, cursor: zoom <= ZOOM_MIN ? "default" : "pointer",
                opacity: zoom <= ZOOM_MIN ? 0.4 : 1,
              }}
            >
              −
            </button>
            <button
              type="button"
              onClick={() => setZoom(100)}
              title="Reset zoom"
              suppressHydrationWarning
              style={{
                minWidth: 44, height: 28, border: "none", background: "transparent",
                color: "var(--on-variant)", fontSize: 12, cursor: "pointer", textAlign: "center",
              }}
            >
              {zoom}%
            </button>
            <button
              type="button"
              onClick={() => setZoom(z => Math.min(ZOOM_MAX, z + ZOOM_STEP))}
              disabled={zoom >= ZOOM_MAX}
              title="Zoom in"
              suppressHydrationWarning
              style={{
                width: 28, height: 28, display: "flex", alignItems: "center", justifyContent: "center",
                borderRadius: "var(--radius-lg)", border: "none", background: "transparent",
                color: "var(--on-bg)", fontSize: 16, cursor: zoom >= ZOOM_MAX ? "default" : "pointer",
                opacity: zoom >= ZOOM_MAX ? 0.4 : 1,
              }}
            >
              +
            </button>
          </div>
          {canPickBranch && (
            <select
              value={selectedBranch}
              onChange={e => setSelectedBranch(e.target.value)}
              suppressHydrationWarning
              style={{
                padding: "8px 12px",
                borderRadius: "var(--radius-lg)",
                border: "1px solid var(--outline-v)",
                background: "var(--surface)",
                color: "var(--on-bg)",
                fontSize: 13,
                minWidth: 180,
              }}
            >
              <option value="">All Branches</option>
              {branchOptions.map(b => (
                <option key={b} value={b}>{b}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Mobile hint — visible below sm breakpoint via injected style */}
      <div
        className="org-mobile-hint alert alert-info mb-16"
        style={{ display: "none" }}
        suppressHydrationWarning
      >
        <i className="ti ti-arrows-horizontal" /> Scroll horizontally to view the full chart.
      </div>

      {error && (
        <div className="bg-white rounded-xl border border-[var(--outline-v)] p-14 text-center">
          <div className="w-14 h-14 rounded-2xl bg-[var(--error-c)] flex items-center justify-center mx-auto mb-4">
            <i className="ti ti-alert-triangle text-[26px]" style={{ color: "var(--error)" }} />
          </div>
          <h3 className="text-[16px] font-semibold text-[var(--on-bg)] mb-1.5">
            Couldn&apos;t load the organisation chart
          </h3>
          <p className="text-[13px] text-[var(--on-variant)] max-w-sm mx-auto mb-5">
            {error}
          </p>
          <button
            type="button"
            onClick={refetch}
            suppressHydrationWarning
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-lg text-[13px] font-semibold bg-[var(--primary)] text-white hover:bg-[#163d72] transition-colors"
          >
            <i className="ti ti-refresh text-[15px]" />
            Try again
          </button>
        </div>
      )}

      {loading && !orgChart && !error && (
        <div className="flex items-center justify-center py-20 gap-2 text-[13px] text-[var(--on-variant)]">
          <i className="ti ti-loader-2 animate-spin text-[22px]" style={{ color: "var(--primary)" }} />
          Loading organisation chart…
        </div>
      )}

      {!loading && orgChart && groups.length === 0 && !error && (
        <div className="card" style={{ padding: 32, textAlign: "center", color: "var(--on-variant)" }}>
          No departments with employees found yet.
        </div>
      )}

      {orgChart && groups.length === 1 && (
        <div className="card" style={{ padding: "32px 16px" }}>
          <ZoomableChart zoom={zoom}>
            <div style={{ minWidth: 640 }}>
              <BranchBody group={groups[0]} />
            </div>
          </ZoomableChart>
        </div>
      )}

      {/* Multiple branches: one shared company box at the top, with every
          branch hanging off it as a sibling — makes clear they're all the
          same company, not unrelated separate charts. */}
      {orgChart && groups.length > 1 && (
        <div className="card" style={{ padding: "32px 16px" }}>
          <ZoomableChart zoom={zoom}>
            <div style={{ minWidth: groups.length * 720, display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div style={{
                background: "var(--primary)",
                borderRadius: "var(--radius-lg)",
                padding: "14px 32px",
                textAlign: "center",
                boxShadow: "var(--shadow)",
              }}>
                <div style={{ fontSize: 16, fontWeight: 700, color: "#fff" }}>
                  Company
                </div>
              </div>
              <div style={{ width: 1, height: 28, background: LINE }} />
              <div style={{ display: "flex", width: "100%", alignItems: "flex-start" }}>
                {groups.map((group, i) => (
                  <BranchNode
                    key={group.branch || "unassigned"}
                    group={group}
                    isFirst={i === 0}
                    isLast={i === groups.length - 1}
                  />
                ))}
              </div>
            </div>
          </ZoomableChart>
        </div>
      )}

      {/* Mobile-only: vertical card list */}
      <style>{`
        @media (max-width: 768px) {
          .org-mobile-hint { display: flex !important; }
        }
        .org-chart-person-link:hover { text-decoration: underline !important; }
      `}</style>
    </>
  );
}

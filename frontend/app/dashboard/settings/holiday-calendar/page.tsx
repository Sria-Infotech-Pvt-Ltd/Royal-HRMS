"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useFetch } from "@/hooks/useFetch";
import { API } from "@/lib/api/endpoints";
import clientApi from "@/lib/clientApi";
import type { Holiday, HolidayListData, HolidayType } from "@/types/holidays";
import HolidayFormModal from "./_components/HolidayFormModal";
import HolidayViewModal from "./_components/HolidayViewModal";
import DeleteHolidayModal from "./_components/DeleteHolidayModal";
import HolidayListView, { TYPE_STYLES } from "./_components/HolidayListView";
import SearchableSelect from "@/components/SearchableSelect";
import HolidayCalendarView from "./_components/HolidayCalendarView";

// ─── Types ────────────────────────────────────────────────────────────────────

type FilterTab = HolidayType | "all" | "optional";
type ViewMode  = "list" | "calendar";
interface BranchOption { id: number; branch_name: string }

// ─── Constants ────────────────────────────────────────────────────────────────

const YEARS       = [2024, 2025, 2026, 2027, 2028];
const MONTH_NAMES = ["January","February","March","April","May","June","July","August","September","October","November","December"];
const PAGE_SIZE   = 10;

// ─── Component ────────────────────────────────────────────────────────────────

export default function HolidayCalendarPage() {
  const router = useRouter();

  const [year,      setYear]      = useState(new Date().getFullYear());
  const [view,      setView]      = useState<ViewMode>("list");
  const [filterTab, setFilterTab] = useState<FilterTab>("all");
  const [fBranch,   setFBranch]   = useState("All Branches");
  const [fType,     setFType]     = useState<HolidayType | "all">("all");
  const [fMonth,    setFMonth]    = useState<number | "all">("all");
  const [search,    setSearch]    = useState("");
  const [calMonth,  setCalMonth]  = useState(0);
  const [page,      setPage]      = useState(1);

  const [modal,        setModal]        = useState<"add" | "edit" | "view" | null>(null);
  const [editing,       setEditing]      = useState<Holiday | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Holiday | null>(null);

  // Calendar view needs the full year in one shot — fetched once per year and
  // filtered by month client-side, so navigating months never re-calls the API.
  const { data: yearData, refetch: refetchYear } = useFetch<HolidayListData>(`${API.leave.holidays}?year=${year}`);
  const yearHolidays = useMemo(() => yearData?.holidays ?? [], [yearData]);

  // List view instead sends type/optional/month straight to the backend —
  // the effective type comes from whichever of the type tab / type dropdown
  // is more specific, and "Optional" is its own tab, not a type value.
  const effectiveType     = fType !== "all" ? fType : (filterTab !== "all" && filterTab !== "optional" ? filterTab : null);
  const effectiveOptional = filterTab === "optional";

  const listUrl = useMemo(() => {
    const params = new URLSearchParams({ year: String(year) });
    if (fMonth !== "all")   params.set("month", String(fMonth + 1));
    if (effectiveType)      params.set("type", effectiveType);
    if (effectiveOptional)  params.set("optional", "true");
    return `${API.leave.holidays}?${params.toString()}`;
  }, [year, fMonth, effectiveType, effectiveOptional]);

  const { data: listData, loading, refetch: refetchList } = useFetch<HolidayListData>(listUrl);
  const listHolidays = useMemo(() => listData?.holidays ?? [], [listData]);

  const { data: branchData } = useFetch<BranchOption[] | { results: BranchOption[] }>(`${API.branches.list}?page_size=100`);
  const branches = Array.isArray(branchData) ? branchData : (branchData?.results ?? []);

  // Stats/tab counts always reflect the whole year, independent of the
  // currently-applied filters — that's what the tab counters are for.
  const stats = useMemo(() => ({
    total:    yearHolidays.length,
    national: yearHolidays.filter(h => h.holiday_type === "national").length,
    regional: yearHolidays.filter(h => h.holiday_type === "regional").length,
    company:  yearHolidays.filter(h => h.holiday_type === "company").length,
    optional: yearHolidays.filter(h => h.is_optional).length,
  }), [yearHolidays]);

  // Branch and search aren't part of the given query contract, so they still
  // filter client-side on top of whatever the server already returned.
  const filtered = useMemo(() => {
    let list = listHolidays;
    if (fBranch !== "All Branches") list = list.filter(h => h.branch === null || h.branch_name === fBranch);
    if (search.trim()) list = list.filter(h => h.name.toLowerCase().includes(search.toLowerCase()));
    return [...list].sort((a, b) => a.date.localeCompare(b.date));
  }, [listHolidays, fBranch, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const pageRows   = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  const calHolidays = useMemo(() =>
    yearHolidays.filter(h => parseInt(h.date.split("-")[1]) - 1 === calMonth),
    [yearHolidays, calMonth]
  );

  function refetch() { refetchList(); refetchYear(); }

  // The "All Months" dropdown (List view's server filter) and the Calendar
  // view's displayed month are otherwise two independent pieces of state —
  // keep them in sync in both directions so picking a month moves the
  // calendar there, and navigating the calendar updates the dropdown too.
  function changeFMonth(value: number | "all") {
    setFMonth(value);
    setPage(1);
    if (value !== "all") setCalMonth(value);
  }
  function changeCalMonth(month: number) {
    setCalMonth(month);
    setFMonth(month);
  }

  function openAdd()            { setEditing(null); setModal("add"); }
  function openEdit(h: Holiday) { setEditing(h); setModal("edit"); }
  function openView(h: Holiday) { setEditing(h); setModal("view"); }
  function closeModal()         { setModal(null); setEditing(null); }

  async function toggleActive(h: Holiday) {
    try {
      await clientApi.patch(API.leave.holidayDetail(h.id), { is_active: !h.is_active });
      refetch();
    } catch { /* list stays as-is; user can retry */ }
  }

  const filterTabs: Array<{ id: FilterTab; label: string; count: number }> = [
    { id: "all",      label: "All",      count: stats.total    },
    { id: "national", label: "National", count: stats.national },
    { id: "regional", label: "Regional", count: stats.regional },
    { id: "company",  label: "Company",  count: stats.company  },
    { id: "optional", label: "Optional", count: stats.optional },
  ];

  return (
    <>
      {/* ── Page header ──────────────────────────────────────────────────── */}
      <div className="page-header">
        <div>
          <div className="page-title">Holiday Calendar</div>
          <div className="page-sub">Manage national, regional, and company holidays</div>
        </div>
        <div className="page-actions">
          <button className="btn btn-ghost" onClick={() => router.push("/dashboard/settings")}>
            <i className="ti ti-arrow-left" /> Back
          </button>
          <button className="btn btn-filled" onClick={openAdd}>
            <i className="ti ti-plus" /> Add Holiday
          </button>
        </div>
      </div>

      {/* ── Year navigator + quick filters ───────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5">
        <div className="flex items-center gap-1 bg-[var(--surface)] border border-[var(--outline-v)] rounded-xl px-2 py-1.5 shadow-sm">
          <button onClick={() => { setYear(y => y - 1); setPage(1); }} aria-label="Previous year"
            className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-[var(--bg-mid)] text-[var(--on-variant)] transition-colors">
            <i className="ti ti-chevron-left text-sm" />
          </button>
          <select
            value={year} onChange={e => { setYear(Number(e.target.value)); setPage(1); }}
            className="text-sm font-bold text-[var(--on-bg)] bg-transparent border-none outline-none px-1 cursor-pointer"
          >
            {YEARS.map(y => <option key={y} value={y}>{y}</option>)}
          </select>
          <button onClick={() => { setYear(y => y + 1); setPage(1); }} aria-label="Next year"
            className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-[var(--bg-mid)] text-[var(--on-variant)] transition-colors">
            <i className="ti ti-chevron-right text-sm" />
          </button>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <SearchableSelect
            value={fBranch} onChange={v => { setFBranch(v); setPage(1); }}
            inputClassName="text-sm border border-[var(--outline-v)] rounded-lg px-3 py-2 bg-[var(--surface)] outline-none focus:border-[var(--primary)] text-[var(--on-bg)] cursor-pointer"
            placeholder="All Company Codes"
            options={[
              { value: "All Branches", label: "All Company Codes" },
              ...branches.map(b => ({ value: b.branch_name, label: b.branch_name })),
            ]}
          />
          <div className="relative">
            <i className="ti ti-search absolute left-3 top-1/2 -translate-y-1/2 text-[var(--on-variant)] text-sm" />
            <input
              value={search} onChange={e => { setSearch(e.target.value); setPage(1); }}
              placeholder="Search holidays…"
              aria-label="Search holidays"
              className="pl-8 pr-3 py-2 text-sm border border-[var(--outline-v)] rounded-lg bg-[var(--surface)] outline-none focus:border-[var(--primary)] text-[var(--on-bg)] w-48"
            />
          </div>
        </div>
      </div>

      {/* ── Stats cards ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-5">
        {[
          { icon: "ti-calendar-event", si: "si-primary", label: "Total Holidays",   value: stats.total    },
          { icon: "ti-flag",           si: "si-info",    label: "National",         value: stats.national },
          { icon: "ti-map-pin",        si: "si-success", label: "Regional",         value: stats.regional },
          { icon: "ti-building",       si: "si-warn",     label: "Company",          value: stats.company  },
          { icon: "ti-calendar-check", si: "bg-[rgba(167,139,250,0.15)] text-[var(--purple)]", label: "Optional", value: stats.optional },
        ].map(s => (
          <div key={s.label} className="bg-[var(--surface)] rounded-2xl border border-[var(--outline-v)] shadow-sm px-4 py-4 flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl ${s.si} flex items-center justify-center flex-shrink-0`}>
              <i className={`ti ${s.icon} text-lg`} />
            </div>
            <div>
              <div className="text-2xl font-extrabold text-[var(--on-bg)] leading-none">{s.value}</div>
              <div className="text-xs text-[var(--on-variant)] mt-0.5">{s.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Filter tabs ───────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 flex-wrap mb-4">
        {filterTabs.map(t => (
          <button
            key={t.id}
            onClick={() => { setFilterTab(t.id); setPage(1); }}
            className={[
              "px-4 py-1.5 rounded-full text-sm font-medium border transition-all",
              filterTab === t.id
                ? "bg-[var(--primary)] text-[var(--on-primary)] border-[var(--primary)]"
                : "bg-[var(--surface)] text-[var(--on-variant)] border-[var(--outline-v)] hover:border-[var(--primary)] hover:text-[var(--primary)]",
            ].join(" ")}
          >
            {t.label}
            <span className={[
              "ml-1.5 inline-flex items-center justify-center min-w-[18px] h-[18px] rounded-full text-xs font-bold px-1",
              filterTab === t.id ? "bg-[var(--surface)] text-[var(--primary)]" : "bg-[var(--bg-mid)] text-[var(--on-variant)]",
            ].join(" ")}>
              {t.count}
            </span>
          </button>
        ))}

        <div className="ml-auto flex items-center gap-1 bg-[var(--bg-mid)] rounded-xl p-1">
          <button onClick={() => setView("list")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 ${view === "list" ? "bg-[var(--surface)] shadow-sm text-[var(--primary)]" : "text-[var(--on-variant)] hover:text-[var(--on-bg)]"}`}>
            <i className="ti ti-list text-sm" /> List
          </button>
          <button onClick={() => setView("calendar")}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-all flex items-center gap-1.5 ${view === "calendar" ? "bg-[var(--surface)] shadow-sm text-[var(--primary)]" : "text-[var(--on-variant)] hover:text-[var(--on-bg)]"}`}>
            <i className="ti ti-calendar-month text-sm" /> Calendar
          </button>
        </div>
      </div>

      {/* ── Additional filters row ────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2 mb-4">
        <select value={fType} onChange={e => { setFType(e.target.value as HolidayType | "all"); setPage(1); }}
          className="text-xs border border-[var(--outline-v)] rounded-lg px-3 py-1.5 bg-[var(--surface)] outline-none focus:border-[var(--primary)] text-[var(--on-variant)] cursor-pointer field-select">
          <option value="all">All Types</option>
          <option value="national">National</option>
          <option value="regional">Regional</option>
          <option value="company">Company</option>
        </select>
        <select value={fMonth === "all" ? "all" : fMonth} onChange={e => changeFMonth(e.target.value === "all" ? "all" : parseInt(e.target.value))}
          className="text-xs border border-[var(--outline-v)] rounded-lg px-3 py-1.5 bg-[var(--surface)] outline-none focus:border-[var(--primary)] text-[var(--on-variant)] cursor-pointer field-select">
          <option value="all">All Months</option>
          {MONTH_NAMES.map((m, i) => <option key={i} value={i}>{m}</option>)}
        </select>
        {(search || fBranch !== "All Branches" || fType !== "all" || fMonth !== "all") && (
          <button onClick={() => { setSearch(""); setFBranch("All Branches"); setFType("all"); setFMonth("all"); setPage(1); }}
            className="text-xs px-3 py-1.5 rounded-lg border border-[var(--error)] text-[var(--error)] bg-[var(--error-c)] hover:opacity-80 transition-colors flex items-center gap-1">
            <i className="ti ti-x text-xs" /> Clear Filters
          </button>
        )}
        <span className="ml-auto text-xs text-[var(--on-variant)] self-center">
          {loading ? "Loading…" : `${filtered.length} holiday${filtered.length !== 1 ? "s" : ""}`}
        </span>
      </div>

      {/* ── LIST / CALENDAR VIEW ─────────────────────────────────────────── */}
      {view === "list" ? (
        <HolidayListView
          loading={loading} filtered={filtered} pageRows={pageRows}
          page={page} totalPages={totalPages} pageSize={PAGE_SIZE} year={year}
          onPageChange={setPage} onAdd={openAdd} onView={openView} onEdit={openEdit}
          onDelete={setDeleteTarget} onToggleActive={toggleActive}
        />
      ) : (
        <HolidayCalendarView
          year={year} calMonth={calMonth} holidays={calHolidays}
          onMonthChange={changeCalMonth} onView={openView}
        />
      )}

      {/* ── Type legend ───────────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-4 mt-4 px-1">
        {(["national","regional","company"] as HolidayType[]).map(t => (
          <div key={t} className="flex items-center gap-1.5 text-xs text-[var(--on-variant)]">
            <span className={`w-2.5 h-2.5 rounded-full ${TYPE_STYLES[t].dot}`} />
            <span className="capitalize font-medium">{t}</span>
          </div>
        ))}
        <div className="flex items-center gap-1.5 text-xs text-[var(--on-variant)]">
          <span className="w-2.5 h-2.5 rounded-full bg-[var(--purple)]" />
          <span className="font-medium">Optional</span>
        </div>
      </div>

      {/* ── Modals ────────────────────────────────────────────────────────── */}
      {modal === "view" && editing && (
        <HolidayViewModal holiday={editing} onClose={closeModal} onEdit={() => setModal("edit")} />
      )}
      {(modal === "add" || modal === "edit") && (
        <HolidayFormModal mode={modal} editing={editing} branches={branches} onClose={closeModal} onSaved={refetch} />
      )}
      {deleteTarget && (
        <DeleteHolidayModal holiday={deleteTarget} onClose={() => setDeleteTarget(null)} onDeleted={refetch} />
      )}
    </>
  );
}

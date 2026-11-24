"use client";

import { useRef, useState, type ReactNode } from "react";
import { useDragScroll } from "@/hooks/useDragScroll";
import { useT } from "@/hooks/useI18n";
import { CHART_CSS } from "./orgChartStyles";

const MIN_ZOOM = 0.3;
const MAX_ZOOM = 1.5;
const ZOOM_STEP = 0.15;
const FIT_MARGIN_PX = 32;

interface Props {
  query: string;
  onQueryChange: (query: string) => void;
  searchPlaceholder: string;
  onExpandAll: () => void;
  onCollapseAll: () => void;
  isEmpty: boolean;
  emptyText: string;
  /** Extra controls, placed after the search box. */
  tools?: ReactNode;
  /** The chart itself: a `<ul>` of nested `<li>` boxes. */
  children: ReactNode;
}

const clampZoom = (value: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, Math.round(value * 100) / 100));

/** What every org chart shares: search, expand/collapse, zoom, fit to screen, drag to pan, and print. */
export default function OrgChartFrame({ query, onQueryChange, searchPlaceholder, onExpandAll, onCollapseAll, isEmpty, emptyText, tools, children }: Props) {
  const t = useT();
  const [zoom, setZoom] = useState(1);
  const scrollRef = useDragScroll<HTMLDivElement>();
  const chartRef = useRef<HTMLDivElement>(null);

  function fitToScreen() {
    const area = scrollRef.current;
    const root = chartRef.current?.firstElementChild;
    if (!area || !root) return;
    // The chart's size on screen divided by the current zoom is its natural width.
    const naturalWidth = root.getBoundingClientRect().width / zoom;
    if (naturalWidth <= 0) return;
    setZoom(clampZoom((area.clientWidth - FIT_MARGIN_PX) / naturalWidth));
    area.scrollTo({ left: 0, top: 0 });
  }

  return (
    <div>
      <div className="oc-toolbar">
        <div className="oc-search">
          <i className="ti ti-search" />
          <input className="field-input" value={query} placeholder={searchPlaceholder} aria-label={t("Search the chart")} onChange={event => onQueryChange(event.target.value)} />
        </div>
        {tools}
        <button type="button" className="btn btn-ghost btn-sm" onClick={onExpandAll}><i className="ti ti-arrows-diagonal" /> {t("Expand all")}</button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={onCollapseAll}><i className="ti ti-arrows-diagonal-minimize-2" /> {t("Collapse all")}</button>
        <span className="oc-spacer" />
        <button type="button" className="btn btn-ghost btn-sm" aria-label={t("Zoom out")} disabled={zoom <= MIN_ZOOM} onClick={() => setZoom(clampZoom(zoom - ZOOM_STEP))}><i className="ti ti-minus" /></button>
        <span className="oc-zoom">{Math.round(zoom * 100)}%</span>
        <button type="button" className="btn btn-ghost btn-sm" aria-label={t("Zoom in")} disabled={zoom >= MAX_ZOOM} onClick={() => setZoom(clampZoom(zoom + ZOOM_STEP))}><i className="ti ti-plus" /></button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={fitToScreen}><i className="ti ti-arrows-maximize" /> {t("Fit")}</button>
        <button type="button" className="btn btn-ghost btn-sm" onClick={() => window.print()} title={t("Print, or save as PDF")}><i className="ti ti-printer" /> {t("Print")}</button>
      </div>
      <div className="oc-scroll" ref={scrollRef}>
        {isEmpty
          ? <div className="oc-empty">{emptyText}</div>
          : <div className="oc" ref={chartRef} style={{ zoom }}>{children}</div>}
      </div>
      <div style={{ fontSize: 11.5, color: "var(--on-variant)", marginTop: 6 }}>{t("Drag the chart to move around it.")}</div>
      <style>{CHART_CSS}</style>
    </div>
  );
}

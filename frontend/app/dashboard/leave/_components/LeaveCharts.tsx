import { tr } from "@/lib/i18n/tr";
// Small SVG charts for the Leave analytics screen (no chart library): monthly bars and a status donut.

export interface MonthPoint { month: number; requests: number; approved_days: number }
export interface DonutSlice { label: string; value: number; color: string }

const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const WIDTH = 560;
const HEIGHT = 220;
const PAD = { left: 30, right: 8, top: 12, bottom: 26 };

/** A round maximum for the y axis, so the grid lines land on whole numbers. */
function niceMax(value: number): number {
  if (value <= 4) return 4;
  const step = Math.pow(10, Math.floor(Math.log10(value)));
  return Math.ceil(value / step) * step;
}

function requestsText(count: number): string {
  return count === 1 ? tr("{count} request", { count }) : tr("{count} requests", { count });
}

function approvedDaysText(count: number): string {
  return count === 1 ? tr("{count} approved day", { count }) : tr("{count} approved days", { count });
}

function monthSummary(point: MonthPoint): string {
  return tr("{month}: {requests}, {days}", { month: tr(MONTH_NAMES[point.month - 1]), requests: requestsText(point.requests), days: approvedDaysText(point.approved_days) });
}

export function MonthlyBars({ data }: { data: MonthPoint[] }) {
  const top = niceMax(Math.max(...data.map(point => Math.max(point.requests, point.approved_days)), 0));
  const plotWidth = WIDTH - PAD.left - PAD.right;
  const plotHeight = HEIGHT - PAD.top - PAD.bottom;
  const slot = plotWidth / Math.max(data.length, 1);
  const barWidth = Math.min(14, slot / 2.6);
  const baseline = PAD.top + plotHeight;
  const y = (value: number) => baseline - (value / top) * plotHeight;
  const summary = data.map(monthSummary).join("; ");

  return (
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} style={{ width: "100%", height: "auto", display: "block" }} role="img" aria-label={tr("Leave requests and approved days for each month. {summary}", { summary })}>
      {[0, 0.25, 0.5, 0.75, 1].map(fraction => {
        const value = top * fraction;
        return (
          <g key={fraction}>
            <line x1={PAD.left} x2={WIDTH - PAD.right} y1={y(value)} y2={y(value)} stroke="currentColor" strokeOpacity={0.12} />
            <text x={PAD.left - 6} y={y(value) + 3.5} textAnchor="end" fontSize={10} fill="currentColor" fillOpacity={0.6}>{Math.round(value * 10) / 10}</text>
          </g>
        );
      })}
      {data.map((point, index) => {
        const centre = PAD.left + slot * index + slot / 2;
        return (
          <g key={point.month}>
            <title>{monthSummary(point)}</title>
            <rect x={centre - barWidth - 1} y={y(point.requests)} width={barWidth} height={baseline - y(point.requests)} rx={3} fill="var(--brand)" fillOpacity={0.35} />
            <rect x={centre + 1} y={y(point.approved_days)} width={barWidth} height={baseline - y(point.approved_days)} rx={3} fill="#16a34a" />
            <text x={centre} y={HEIGHT - 8} textAnchor="middle" fontSize={10} fill="currentColor" fillOpacity={0.65}>{tr(MONTH_NAMES[point.month - 1])}</text>
          </g>
        );
      })}
    </svg>
  );
}

export function StatusDonut({ slices, total }: { slices: DonutSlice[]; total: number }) {
  const radius = 52;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;
  return (
    <svg viewBox="0 0 140 140" style={{ width: 150, height: 150, flex: "none" }} role="img" aria-label={tr("Requests by status, {total} in total. {list}", { total, list: slices.map(s => `${s.label}: ${s.value}`).join(", ") })}>
      <circle cx={70} cy={70} r={radius} fill="none" stroke="currentColor" strokeOpacity={0.1} strokeWidth={16} />
      {slices.filter(slice => slice.value > 0).map(slice => {
        const length = (slice.value / total) * circumference;
        const arc = (
          <circle
            key={slice.label} cx={70} cy={70} r={radius} fill="none" stroke={slice.color} strokeWidth={16}
            strokeDasharray={`${length} ${circumference - length}`} strokeDashoffset={-offset} transform="rotate(-90 70 70)"
          >
            <title>{`${slice.label}: ${slice.value}`}</title>
          </circle>
        );
        offset += length;
        return arc;
      })}
      <text x={70} y={68} textAnchor="middle" fontSize={26} fontWeight={800} fill="currentColor">{total}</text>
      <text x={70} y={86} textAnchor="middle" fontSize={10} fill="currentColor" fillOpacity={0.6}>{tr("requests")}</text>
    </svg>
  );
}

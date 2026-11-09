// Small pure helpers for the Reports screen: the filter values a report starts with, and how they become a query string.
import type { ReportDefinition, ReportFilterValues } from "@/types/reports";

/** Each filter's own default (the server's allowed value), so a report can be run straight away. */
export function defaultFilters(report: ReportDefinition): ReportFilterValues {
  return Object.fromEntries(report.filters.map(filter => [filter.key, filter.default]));
}

/** Only filters with a value, as a query string (no leading "?"). The server re-validates every one. */
export function filtersToQuery(filters: ReportFilterValues): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) params.set(key, value);
  }
  return params.toString();
}

/** What a download or preview URL looks like for a report and its current filters. */
export function withQuery(path: string, filters: ReportFilterValues): string {
  const query = filtersToQuery(filters);
  return query ? `${path}?${query}` : path;
}

/** The "Contact details are left out of the email" notice, or "" when the report has no such columns. */
export function emailOmitsNotice(report: ReportDefinition): string {
  return report.email_omits.length > 0
    ? `The emailed copy leaves out: ${report.email_omits.join(", ")}.`
    : "";
}

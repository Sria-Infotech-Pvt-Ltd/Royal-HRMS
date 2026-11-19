import { fillParams, type TranslateParams } from "@/lib/i18n/translate";

// What to tell someone when today's numbers on the Attendance page could not be loaded, by the HTTP status of the failed request.
// null means the request never got an answer (network down, server unreachable).

export function describeStatsFailure(status: number | null, t: (text: string, params?: TranslateParams) => string = fillParams): string {
  if (status === 401) return t("Your session has ended. Sign out and sign in again.");
  if (status === 403) return t("Your login does not have permission to view attendance numbers. Ask HR or an admin to grant Attendance view.");
  if (status !== null && status >= 500) return t("The server had a problem while counting. Try again in a moment; if it keeps happening, tell your admin.");
  if (status === null) return t("The server could not be reached. Check your internet connection and try again.");
  return t("The numbers could not be loaded (error {code}).", { code: status });
}

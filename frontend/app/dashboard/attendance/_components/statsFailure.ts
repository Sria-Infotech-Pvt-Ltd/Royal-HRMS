// What to tell someone when today's numbers on the Attendance page could not be loaded, by the HTTP status of the failed request.
// null means the request never got an answer (network down, server unreachable).

export function describeStatsFailure(status: number | null): string {
  if (status === 401) return "Your session has ended. Sign out and sign in again.";
  if (status === 403) return "Your login does not have permission to view attendance numbers. Ask HR or an admin to grant Attendance view.";
  if (status !== null && status >= 500) return "The server had a problem while counting. Try again in a moment; if it keeps happening, tell your admin.";
  if (status === null) return "The server could not be reached. Check your internet connection and try again.";
  return `The numbers could not be loaded (error ${status}).`;
}

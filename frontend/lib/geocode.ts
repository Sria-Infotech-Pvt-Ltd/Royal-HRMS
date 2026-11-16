// Address -> coordinates lookup for the work-from-home form, using OpenStreetMap Nominatim.
//
// Nominatim's usage policy allows about one request per second and forbids search-as-you-type: call this only on an explicit
// press of a Search button. Heavy or automated use should go through a backend endpoint (with a proper User-Agent, caching and
// rate limiting) instead of the browser.

export interface GeocodeResult {
  label: string;
  latitude: number;
  longitude: number;
}

interface NominatimRow {
  display_name: string;
  lat: string;
  lon: string;
}

const NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search";
const MAX_RESULTS = 5;

function isNominatimRow(value: unknown): value is NominatimRow {
  if (typeof value !== "object" || value === null) return false;
  const row = value as Record<string, unknown>; // narrowed field by field below
  return typeof row.display_name === "string" && typeof row.lat === "string" && typeof row.lon === "string";
}

export async function searchAddress(query: string, signal?: AbortSignal): Promise<GeocodeResult[]> {
  const params = new URLSearchParams({ q: query.trim(), format: "jsonv2", limit: String(MAX_RESULTS) });
  const response = await fetch(`${NOMINATIM_SEARCH_URL}?${params.toString()}`, { signal, headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("The address search is unavailable right now. Please try again in a moment.");

  const body: unknown = await response.json();
  if (!Array.isArray(body)) return [];

  const results: GeocodeResult[] = [];
  for (const row of body) {
    if (!isNominatimRow(row)) continue;
    const latitude = Number(row.lat);
    const longitude = Number(row.lon);
    if (Number.isFinite(latitude) && Number.isFinite(longitude)) results.push({ label: row.display_name, latitude, longitude });
  }
  return results;
}
